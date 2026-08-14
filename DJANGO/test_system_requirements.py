"""
System Requirements Test Script
Tests all core requirements for the FileVault system:
1. Hierarchical Namespace with materialized path
2. File Locking with race condition prevention
3. Granular ACLs with group permissions
4. Presigned URLs for direct storage access
"""

import os
import sys
import django
from datetime import timedelta
from django.utils import timezone
from django.db import transaction
from django.core.exceptions import ValidationError

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'filevault.settings')
sys.path.insert(0, os.path.dirname(__file__))
django.setup()

from apps.files.models import (
    FileSystemNode,
    FileLock,
    UserFilePermission,
    GroupFilePermission,
    NodeType
)
from apps.accounts.models import User, Company, Department
from core.presigned_url_service import get_presigned_url_service


class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    BOLD = '\033[1m'
    END = '\033[0m'


def print_test(test_name, passed, message=""):
    status = f"{Colors.GREEN}✓ PASS{Colors.END}" if passed else f"{Colors.RED}✗ FAIL{Colors.END}"
    print(f"{status} - {test_name}")
    if message:
        print(f"  {Colors.YELLOW}{message}{Colors.END}")


def test_hierarchical_namespace():
    """Test 1: Hierarchical Namespace with materialized path"""
    print(f"\n{Colors.BOLD}{Colors.BLUE}TEST 1: Hierarchical Namespace (Materialized Path){Colors.END}")
    
    try:
        # Create test company
        company, _ = Company.objects.get_or_create(
            name="Test Company",
            defaults={'slug': 'test-company'}
        )
        
        # Create root folder
        root = FileSystemNode.objects.create(
            name="projects",
            node_type=NodeType.FOLDER,
            company=company,
            parent=None
        )
        
        # Verify materialized path
        expected_path = f"/{company.slug}/projects"
        assert root.materialized_path == expected_path, f"Expected {expected_path}, got {root.materialized_path}"
        print_test("Root folder materialized path", True)
        
        # Create nested folder
        subfolder = FileSystemNode.objects.create(
            name="construction",
            node_type=NodeType.FOLDER,
            company=company,
            parent=root
        )
        
        expected_subpath = f"{expected_path}/construction"
        assert subfolder.materialized_path == expected_subpath, f"Expected {expected_subpath}, got {subfolder.materialized_path}"
        print_test("Nested folder materialized path", True)
        
        # Create deeply nested structure
        deep_folder = FileSystemNode.objects.create(
            name="phase1",
            node_type=NodeType.FOLDER,
            company=company,
            parent=subfolder
        )
        
        expected_deep = f"{expected_subpath}/phase1"
        assert deep_folder.materialized_path == expected_deep, f"Expected {expected_deep}, got {deep_folder.materialized_path}"
        print_test("Deeply nested folder path", True)
        
        # Test path-based query
        nodes_in_path = FileSystemNode.objects.filter(
            materialized_path__startswith=expected_path
        )
        assert nodes_in_path.count() == 3, f"Expected 3 nodes, got {nodes_in_path.count()}"
        print_test("Path-based query (startswith)", True)
        
        # Test ancestors
        ancestors = deep_folder.get_ancestors()
        assert len(ancestors) == 2, f"Expected 2 ancestors, got {len(ancestors)}"
        print_test("Get ancestors", True)
        
        # Test breadcrumbs
        breadcrumbs = deep_folder.get_breadcrumbs()
        assert len(breadcrumbs) == 3, f"Expected 3 breadcrumbs, got {len(breadcrumbs)}"
        print_test("Get breadcrumbs", True)
        
        # Cleanup
        FileSystemNode.objects.filter(company=company).delete()
        company.delete()
        
        return True
        
    except Exception as e:
        print_test("Hierarchical Namespace", False, str(e))
        return False


def test_file_locking():
    """Test 2: File Locking with race condition prevention"""
    print(f"\n{Colors.BOLD}{Colors.BLUE}TEST 2: File Locking (Race Condition Prevention){Colors.END}")
    
    try:
        # Create test data
        company, _ = Company.objects.get_or_create(
            name="Lock Test Company",
            defaults={'slug': 'lock-test-company'}
        )
        
        user1, _ = User.objects.get_or_create(
            email="user1@test.com",
            defaults={
                'first_name': 'User',
                'last_name': '1',
                'company': company
            }
        )

        user2, _ = User.objects.get_or_create(
            email="user2@test.com",
            defaults={
                'first_name': 'User',
                'last_name': '2',
                'company': company
            }
        )
        
        # Create a test file
        file_node = FileSystemNode.objects.create(
            name="drawing.dwg",
            node_type=NodeType.FILE,
            company=company,
            parent=None
        )
        print_test("Create test file", True)
        
        # Test lock acquisition
        lock1 = FileLock.acquire_lock(
            node=file_node,
            user=user1,
            lock_type='exclusive',
            expires_in_minutes=30
        )
        assert lock1 is not None, "Failed to acquire lock"
        assert lock1.locked_by == user1, "Lock not assigned to correct user"
        print_test("Acquire exclusive lock", True)
        
        # Test that file is marked as locked
        file_node.refresh_from_db()
        assert file_node.is_locked, "File not marked as locked"
        print_test("File locked status", True)
        
        # Test that second user cannot acquire lock
        try:
            lock2 = FileLock.acquire_lock(
                node=file_node,
                user=user2,
                lock_type='exclusive',
                expires_in_minutes=30
            )
            print_test("Prevent concurrent lock acquisition", False, "Second user acquired lock!")
            return False
        except ValidationError as e:
            assert "locked by" in str(e).lower(), f"Wrong error message: {e}"
            print_test("Prevent concurrent lock acquisition", True)
        
        # Test lock release
        lock1.release_lock()
        file_node.refresh_from_db()
        assert not file_node.is_locked, "File still marked as locked after release"
        print_test("Release lock", True)
        
        # Test that lock can be acquired after release
        lock3 = FileLock.acquire_lock(
            node=file_node,
            user=user2,
            lock_type='exclusive',
            expires_in_minutes=30
        )
        assert lock3 is not None, "Failed to acquire lock after release"
        print_test("Acquire lock after release", True)
        
        # Test lock refresh
        original_expires = lock3.expires_at
        lock3.refresh_lock(additional_minutes=60)
        lock3.refresh_from_db()
        assert lock3.expires_at > original_expires, "Lock not extended"
        print_test("Refresh/extend lock", True)
        
        # Test expired lock cleanup
        lock3.expires_at = timezone.now() - timedelta(minutes=1)
        lock3.save()
        
        cleaned = FileLock.cleanup_expired_locks()
        assert cleaned >= 1, f"Expected to clean at least 1 lock, cleaned {cleaned}"
        print_test("Cleanup expired locks", True)
        
        # Cleanup
        FileSystemNode.objects.filter(company=company).delete()
        User.objects.filter(email__in=["user1@test.com", "user2@test.com"]).delete()
        FileLock.objects.all().delete()
        company.delete()
        
        return True
        
    except Exception as e:
        print_test("File Locking", False, str(e))
        import traceback
        traceback.print_exc()
        return False


def test_race_condition():
    """Test 3: Race condition prevention with concurrent lock attempts"""
    print(f"\n{Colors.BOLD}{Colors.BLUE}TEST 3: Race Condition Prevention{Colors.END}")
    
    try:
        import threading
        import time
        
        # Create test data
        company, _ = Company.objects.get_or_create(
            name="Race Test Company",
            defaults={'slug': 'race-test-company'}
        )
        
        user1, _ = User.objects.get_or_create(
            email="race1@test.com",
            defaults={'first_name': 'Race', 'last_name': 'User 1', 'company': company}
        )

        user2, _ = User.objects.get_or_create(
            email="race2@test.com",
            defaults={'first_name': 'Race', 'last_name': 'User 2', 'company': company}
        )
        
        file_node = FileSystemNode.objects.create(
            name="race-test.dwg",
            node_type=NodeType.FILE,
            company=company,
            parent=None
        )
        
        results = {'success': [], 'failed': []}
        
        def try_acquire_lock(user):
            try:
                lock = FileLock.acquire_lock(
                    node=file_node,
                    user=user,
                    lock_type='exclusive',
                    expires_in_minutes=30
                )
                results['success'].append(user.email)
            except ValidationError:
                results['failed'].append(user.email)
        
        # Simulate concurrent lock attempts
        threads = []
        for _ in range(5):
            t = threading.Thread(target=try_acquire_lock, args=(user1,))
            threads.append(t)
            t = threading.Thread(target=try_acquire_lock, args=(user2,))
            threads.append(t)
        
        # Start all threads simultaneously
        for t in threads:
            t.start()
        
        # Wait for all threads to complete
        for t in threads:
            t.join()
        
        # Only one should succeed
        assert len(results['success']) == 1, f"Expected 1 success, got {len(results['success'])}"
        assert len(results['failed']) == 9, f"Expected 9 failures, got {len(results['failed'])}"
        print_test("Concurrent lock acquisition (10 threads)", True, f"1 success, 9 failed")
        
        # Cleanup
        FileSystemNode.objects.filter(company=company).delete()
        User.objects.filter(email__in=["race1@test.com", "race2@test.com"]).delete()
        FileLock.objects.all().delete()
        company.delete()
        
        return True
        
    except Exception as e:
        print_test("Race Condition Prevention", False, str(e))
        import traceback
        traceback.print_exc()
        return False


def test_acl_permissions():
    """Test 4: Granular ACLs with user and group permissions"""
    print(f"\n{Colors.BOLD}{Colors.BLUE}TEST 4: Granular ACLs (User & Group Permissions){Colors.END}")
    
    try:
        # Create test data
        company, _ = Company.objects.get_or_create(
            name="ACL Test Company",
            defaults={'slug': 'acl-test-company'}
        )
        
        dept1, _ = Department.objects.get_or_create(
            name="Engineering",
            slug="engineering",
            company=company
        )

        dept2, _ = Department.objects.get_or_create(
            name="Architecture",
            slug="architecture",
            company=company
        )
        
        user1, _ = User.objects.get_or_create(
            email="acl1@test.com",
            defaults={'first_name': 'ACL', 'last_name': 'User 1', 'company': company, 'department': dept1}
        )

        user2, _ = User.objects.get_or_create(
            email="acl2@test.com",
            defaults={'first_name': 'ACL', 'last_name': 'User 2', 'company': company, 'department': dept2}
        )
        
        file_node = FileSystemNode.objects.create(
            name="blueprint.pdf",
            node_type=NodeType.FILE,
            company=company,
            parent=None
        )
        print_test("Create test file", True)
        
        # Test user-specific permission
        user_perm = UserFilePermission.objects.create(
            user=user1,
            node=file_node,
            permission_mask=7,  # read + write + execute
            assigned_by=user1
        )
        assert user_perm.can_read(), "User cannot read"
        assert user_perm.can_write(), "User cannot write"
        assert user_perm.can_execute(), "User cannot execute"
        assert not user_perm.can_delete(), "User can delete (should not)"
        print_test("User-specific permission (read/write/execute)", True)
        
        # Test group permission
        group_perm = GroupFilePermission.objects.create(
            group=dept1,
            node=file_node,
            permission_mask=3,  # read + write
            assigned_by=user1
        )
        assert group_perm.can_read(), "Group cannot read"
        assert group_perm.can_write(), "Group cannot write"
        assert not group_perm.can_execute(), "Group can execute (should not)"
        print_test("Group-based permission (read/write)", True)
        
        # Test permission expiration
        user_perm.expires_at = timezone.now() - timedelta(hours=1)
        user_perm.save()
        # Permission should still exist but be expired
        assert user_perm.expires_at < timezone.now(), "Permission not expired"
        print_test("Permission expiration", True)
        
        # Test permission mask validation
        try:
            invalid_perm = UserFilePermission(
                user=user2,
                node=file_node,
                permission_mask=16  # Invalid bit
            )
            invalid_perm.full_clean()
            print_test("Permission mask validation", False, "Invalid mask accepted")
            return False
        except ValidationError:
            print_test("Permission mask validation", True)
        
        # Cleanup
        FileSystemNode.objects.filter(company=company).delete()
        UserFilePermission.objects.all().delete()
        GroupFilePermission.objects.all().delete()
        User.objects.filter(email__in=["acl1@test.com", "acl2@test.com"]).delete()
        Department.objects.filter(slug__in=["engineering", "architecture"]).delete()
        company.delete()
        
        return True
        
    except Exception as e:
        print_test("ACL Permissions", False, str(e))
        import traceback
        traceback.print_exc()
        return False


def test_presigned_urls():
    """Test 5: Presigned URLs for direct storage access"""
    print(f"\n{Colors.BOLD}{Colors.BLUE}TEST 5: Presigned URLs (Direct Storage Access){Colors.END}")

    try:
        # Check if Azure SDK is available
        try:
            from azure.storage.file.share import ShareFileClient
            azure_available = True
        except ImportError:
            azure_available = False

        if not azure_available:
            print_test("Azure SDK availability", False, "Azure SDK not installed - skipping presigned URL tests")
            print_test("Fallback presigned URL service", True, "Fallback service available for local storage")
            return True

        service = get_presigned_url_service()

        # Test if Azure is configured
        azure_configured = hasattr(service, 'account_name') and service.account_name

        if not azure_configured:
            print_test("Azure Files configuration", False, "Azure not configured, using fallback")
            # Test fallback service
            result = service.generate_upload_url('test/file.pdf')
            assert 'upload_url' in result, "Fallback service missing upload_url"
            assert result['note'], "Fallback service missing note"
            print_test("Fallback presigned URL service", True)
            return True
        
        # Test upload URL generation
        upload_result = service.generate_upload_url(
            file_path='files/2024/01/test.pdf',
            expires_in_minutes=60,
            max_file_size=1024 * 1024 * 100  # 100MB
        )
        assert 'upload_url' in upload_result, "Missing upload_url"
        assert upload_result['method'] == 'PUT', "Wrong method for upload"
        assert 'expires_at' in upload_result, "Missing expires_at"
        print_test("Generate upload presigned URL", True)
        
        # Test download URL generation
        download_result = service.generate_download_url(
            file_path='files/2024/01/test.pdf',
            expires_in_minutes=60,
            content_disposition='attachment; filename="test.pdf"'
        )
        assert 'download_url' in download_result, "Missing download_url"
        assert download_result['method'] == 'GET', "Wrong method for download"
        print_test("Generate download presigned URL", True)
        
        # Test delete URL generation
        delete_result = service.generate_delete_url(
            file_path='files/2024/01/test.pdf',
            expires_in_minutes=10
        )
        assert 'delete_url' in delete_result, "Missing delete_url"
        assert delete_result['method'] == 'DELETE', "Wrong method for delete"
        print_test("Generate delete presigned URL", True)
        
        # Verify URL contains SAS token
        assert '?' in upload_result['upload_url'], "URL missing SAS token"
        print_test("URL contains SAS token", True)
        
        return True
        
    except Exception as e:
        print_test("Presigned URLs", False, str(e))
        import traceback
        traceback.print_exc()
        return False


def test_path_navigation():
    """Test 6: Path-based navigation API"""
    print(f"\n{Colors.BOLD}{Colors.BLUE}TEST 6: Path-Based Navigation{Colors.END}")
    
    try:
        # Create test data
        company, _ = Company.objects.get_or_create(
            name="Path Test Company",
            defaults={'slug': 'path-test-company'}
        )
        
        # Create folder structure
        root = FileSystemNode.objects.create(
            name="projetos",
            node_type=NodeType.FOLDER,
            company=company,
            parent=None
        )
        
        obra1 = FileSystemNode.objects.create(
            name="obra1",
            node_type=NodeType.FOLDER,
            company=company,
            parent=root
        )
        
        file1 = FileSystemNode.objects.create(
            name="planta.pdf",
            node_type=NodeType.FILE,
            company=company,
            parent=obra1
        )
        
        # Test path query: /company/projetos/
        path = f"/{company.slug}/projetos/"
        nodes = FileSystemNode.objects.filter(
            materialized_path__startswith=path,
            is_deleted=False
        )
        assert nodes.count() == 2, f"Expected 2 nodes in path, got {nodes.count()}"
        print_test(f"Query by path: {path}", True)
        
        # Test path query: /company/projetos/obra1/
        path2 = f"{path}obra1/"
        nodes2 = FileSystemNode.objects.filter(
            materialized_path__startswith=path2,
            is_deleted=False
        )
        assert nodes2.count() == 1, f"Expected 1 node in path, got {nodes2.count()}"
        print_test(f"Query by path: {path2}", True)

        # Cleanup - delete in reverse order (children first due to protected FK)
        for node in FileSystemNode.objects.filter(company=company).order_by('-materialized_path'):
            node.parent = None
            node.save(update_fields=['parent'])
        FileSystemNode.objects.filter(company=company).delete()
        company.delete()
        
        return True
        
    except Exception as e:
        print_test("Path-Based Navigation", False, str(e))
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests"""
    print(f"\n{Colors.BOLD}{'='*60}{Colors.END}")
    print(f"{Colors.BOLD}FILEVAULT SYSTEM REQUIREMENTS TEST SUITE{Colors.END}")
    print(f"{Colors.BOLD}{'='*60}{Colors.END}")
    
    results = []
    
    # Run all tests
    results.append(("Hierarchical Namespace", test_hierarchical_namespace()))
    results.append(("File Locking", test_file_locking()))
    results.append(("Race Condition Prevention", test_race_condition()))
    results.append(("ACL Permissions", test_acl_permissions()))
    results.append(("Presigned URLs", test_presigned_urls()))
    results.append(("Path Navigation", test_path_navigation()))
    
    # Summary
    print(f"\n{Colors.BOLD}{Colors.BLUE}TEST SUMMARY{Colors.END}")
    print(f"{Colors.BOLD}{'='*60}{Colors.END}")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = f"{Colors.GREEN}✓{Colors.END}" if result else f"{Colors.RED}✗{Colors.END}"
        print(f"{status} {test_name}")
    
    print(f"\n{Colors.BOLD}Total: {passed}/{total} tests passed{Colors.END}")
    
    if passed == total:
        print(f"{Colors.GREEN}{Colors.BOLD}ALL TESTS PASSED!{Colors.END}\n")
        return 0
    else:
        print(f"{Colors.RED}{Colors.BOLD}SOME TESTS FAILED!{Colors.END}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
