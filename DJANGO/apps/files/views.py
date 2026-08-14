from django.db import transaction
from django.db.models import Q, F
from django.utils import timezone
from django.shortcuts import get_object_or_404
from django.http import FileResponse
from django.conf import settings

from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.parsers import (
    MultiPartParser,
    FormParser,
    JSONParser
)
from rest_framework.exceptions import (
    PermissionDenied,
    ValidationError
)

from .models import (
    FileSystemNode,
    UserFilePermission,
    FileLock,
    GroupFilePermission,
    NodeType
)

from .serializers import (
    FileSystemNodeSerializer,
    UserFilePermissionSerializer,
    FileLockSerializer,
    FileLockAcquireSerializer,
    GroupFilePermissionSerializer,
    PresignedURLSerializer,
    FileSystemNodePathSerializer
)

from apps.accounts.models import (
    Department,
    Company,
    Role,
    CrossDeptPermission
)

from apps.audit.models import (
    AuditLog,
    AuditAction
)

from core.permissions import (
    PermissionService,
    Bit
)

# Import IOPS tracking if Azure Files is enabled
if hasattr(settings, 'AZURE_STORAGE_ACCOUNT_NAME') or hasattr(settings, 'AZURE_STORAGE_CONNECTION_STRING'):
    from core.iops_middleware import IOPSCounter

# Import presigned URL service
from core.presigned_url_service import get_presigned_url_service

# Import network drive manager
from core.network_drive import drive_manager


class FileSystemNodeViewSet(viewsets.ModelViewSet):

    serializer_class = FileSystemNodeSerializer
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        qs = (
            FileSystemNode.objects
            .filter(is_deleted=False)
            .select_related(
                'company',
                'department',
                'parent',
                'created_by',
                'updated_by'
            )
        )

        parent = self.request.query_params.get('parent')
        if parent:
            qs = qs.filter(parent_id=parent)

        # Support path-based navigation
        path = self.request.query_params.get('path')
        if path:
            qs = qs.filter(materialized_path__startswith=path)

        if user.role == Role.SUPER_ADMIN:
            return qs

        # Company isolation: users can only see nodes in their company
        if user.company_id:
            qs = qs.filter(company_id=user.company_id)

        return qs

    @transaction.atomic
    def perform_create(self, serializer):
        user = self.request.user
        node = serializer.save(
            created_by=user,
            updated_by=user
        )

        if node.size_bytes:
            from apps.accounts.models import Company
            Company.objects.filter(id=node.company_id).update(
                used_bytes=F('used_bytes') + node.size_bytes
            )
            
            # Track IOPS for upload operation
            if 'IOPSCounter' in globals():
                IOPSCounter.track_operation(
                    'upload',
                    user_id=user.id,
                    company_id=user.company_id,
                    file_size=node.size_bytes
                )

        AuditLog.record(
            user=user,
            action=AuditAction.FILE_CREATE,
            node=node
        )

    def create(self, request, *args, **kwargs):
        upload = request.FILES.get('file_field') or request.FILES.get('file')
        mutable = request.data.copy()
        if upload:
            mutable['file_field'] = upload

        serializer = self.get_serializer(data=mutable)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def retrieve(self, request, *args, **kwargs):
        node = self.get_object()
        PermissionService.assert_op(
            request.user, node, Bit.READ, AuditAction.FILE_VIEW
        )
        serializer = self.get_serializer(node)
        return Response({
            **serializer.data,
            "permissions": PermissionService.get_user_permissions_summary(
                request.user, node
            )
        })

    def update(self, request, *args, **kwargs):
        node = self.get_object()
        PermissionService.assert_op(
            request.user, node, Bit.WRITE, AuditAction.FILE_EDIT
        )
        return super().update(request, *args, **kwargs)

    @action(detail=True, methods=['get'])
    def content(self, request, pk=None):
        """Get document content for editing"""
        node = self.get_object()
        PermissionService.assert_op(
            request.user, node, Bit.READ, AuditAction.FILE_VIEW
        )
        return Response({
            'content': node.content or '',
            'name': node.name
        })

    @action(detail=True, methods=['patch'])
    def save_content(self, request, pk=None):
        """Save document content"""
        node = self.get_object()
        PermissionService.assert_op(
            request.user, node, Bit.WRITE, AuditAction.FILE_EDIT
        )
        
        content = request.data.get('content', '')
        node.content = content
        node.updated_by = request.user
        node.save()
        
        AuditLog.record(
            user=request.user,
            action=AuditAction.FILE_EDIT,
            node=node,
            result="success"
        )
        
        return Response({
            'success': True,
            'message': 'Content saved successfully'
        })

    def perform_destroy(self, instance):
        PermissionService.assert_op(
            self.request.user, instance, Bit.DELETE, AuditAction.FILE_DELETE
        )
        instance.soft_delete(self.request.user)

    def download(self, request, pk=None):
        node = get_object_or_404(FileSystemNode, id=pk, is_deleted=False)
        PermissionService.assert_op(
            request.user, node, Bit.READ, AuditAction.FILE_DOWNLOAD
        )

        if node.node_type != NodeType.FILE or not node.file_field:
            return Response({"error": "Não é um ficheiro."}, status=400)

        response = FileResponse(
            node.file_field.open('rb'),
            content_type=node.mime_type or "application/octet-stream"
        )
        response['Content-Disposition'] = f'attachment; filename="{node.name}"'
        
        # Track IOPS for download operation
        if 'IOPSCounter' in globals():
            IOPSCounter.track_operation(
                'download',
                user_id=request.user.id,
                company_id=request.user.company_id,
                file_size=node.size_bytes
            )
        
        AuditLog.record(
            user=request.user,
            action=AuditAction.FILE_DOWNLOAD,
            node=node
        )
        return response


class UserFilePermissionViewSet(viewsets.ModelViewSet):

    serializer_class = UserFilePermissionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        qs = UserFilePermission.objects.select_related(
            'user', 'node', 'assigned_by'
        )

        if user.role == Role.SUPER_ADMIN:
            return qs

        # Company isolation: managers can only manage permissions in their company
        if user.role == Role.DEPT_MANAGER:
            return qs.filter(node__company=user.company)

        return qs.none()

    @transaction.atomic
    def perform_create(self, serializer):
        actor = self.request.user
        node = serializer.validated_data['node']
        target = serializer.validated_data['user']

        if actor.role != Role.SUPER_ADMIN:
            if not actor.company_id:
                raise PermissionDenied("Utilizador sem empresa associada.")
            if node.company_id != actor.company_id:
                raise PermissionDenied("Sem permissão para gerir permissões de outra empresa.")

        try:
            permission, _ = UserFilePermission.objects.update_or_create(
                user=target,
                node=node,
                defaults={
                    'permission_mask': serializer.validated_data['permission_mask'],
                    'assigned_by': actor,
                    'expires_at': serializer.validated_data.get('expires_at'),
                    'is_active': True
                }
            )
        except Exception as e:
            import logging
            import traceback
            logging.getLogger(__name__).error(f"Failed to create permission: {e}\n{traceback.format_exc()}")
            raise

        try:
            AuditLog.record(
                user=actor,
                action=AuditAction.PERM_GRANT,
                node=node
            )
        except Exception as e:
            # Log error but don't fail the permission creation
            import logging
            logging.getLogger(__name__).error(f"Failed to record audit log: {e}")

    def perform_destroy(self, instance):
        if self.request.user.role != Role.SUPER_ADMIN:
            if instance.node.company_id != self.request.user.company_id:
                raise PermissionDenied("Sem permissão.")
        instance.delete()


class FileLockViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing file locks.
    Provides lock acquisition, release, and refresh functionality.
    """
    serializer_class = FileLockSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        qs = FileLock.objects.select_related('node', 'locked_by')
        
        if user.role == Role.SUPER_ADMIN:
            return qs
        
        # Users can only see locks on files in their company
        if user.company_id:
            return qs.filter(node__company_id=user.company_id)
        
        return qs.none()

    @action(detail=True, methods=['post'])
    def release(self, request, pk=None):
        """Release a file lock."""
        lock = self.get_object()
        
        # Only the lock owner or admin can release
        if lock.locked_by != request.user and request.user.role != Role.SUPER_ADMIN:
            return Response(
                {'error': 'Only the lock owner can release this lock'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        lock.release_lock()
        
        AuditLog.record(
            user=request.user,
            action=AuditAction.FILE_EDIT,  # Using FILE_EDIT as proxy for lock release
            node=lock.node,
            result="lock_released"
        )
        
        return Response({'message': 'Lock released successfully'})

    @action(detail=True, methods=['post'])
    def refresh(self, request, pk=None):
        """Refresh/extend a file lock."""
        lock = self.get_object()
        
        # Only the lock owner can refresh
        if lock.locked_by != request.user:
            return Response(
                {'error': 'Only the lock owner can refresh this lock'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        additional_minutes = request.data.get('additional_minutes', 30)
        lock.refresh_lock(additional_minutes)
        
        return Response(FileLockSerializer(lock).data)

    @action(detail=False, methods=['post'])
    def acquire(self, request):
        """Acquire a new file lock."""
        serializer = FileLockAcquireSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        node_id = request.data.get('node')
        if not node_id:
            return Response(
                {'error': 'node_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            node = FileSystemNode.objects.get(id=node_id, node_type=NodeType.FILE)
        except FileSystemNode.DoesNotExist:
            return Response(
                {'error': 'File not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Check write permission
        try:
            PermissionService.assert_op(
                request.user, node, Bit.WRITE, AuditAction.FILE_EDIT
            )
        except PermissionDenied:
            return Response(
                {'error': 'No write permission on this file'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        try:
            lock = FileLock.acquire_lock(
                node=node,
                user=request.user,
                lock_type=serializer.validated_data['lock_type'],
                expires_in_minutes=serializer.validated_data['expires_in_minutes'],
                client_info=serializer.validated_data.get('client_info')
            )
            
            AuditLog.record(
                user=request.user,
                action=AuditAction.FILE_EDIT,
                node=node,
                result="lock_acquired"
            )
            
            return Response(FileLockSerializer(lock).data, status=status.HTTP_201_CREATED)
            
        except ValidationError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_409_CONFLICT
            )


class GroupFilePermissionViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing group-based file permissions.
    """
    serializer_class = GroupFilePermissionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        qs = GroupFilePermission.objects.select_related('group', 'node', 'assigned_by')
        
        if user.role == Role.SUPER_ADMIN:
            return qs
        
        # Department managers can manage permissions in their company
        if user.role == Role.DEPT_MANAGER:
            return qs.filter(node__company=user.company)
        
        return qs.none()

    def perform_destroy(self, instance):
        if self.request.user.role != Role.SUPER_ADMIN:
            if instance.node.company_id != self.request.user.company_id:
                raise PermissionDenied("Sem permissão.")
        instance.delete()


class PresignedURLViewSet(viewsets.ViewSet):
    """
    ViewSet for generating presigned URLs for direct storage access.
    """
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['post'])
    def upload_url(self, request):
        """Generate a presigned URL for file upload."""
        serializer = PresignedURLSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        service = get_presigned_url_service()
        
        try:
            result = service.generate_upload_url(
                file_path=serializer.validated_data['file_path'],
                expires_in_minutes=serializer.validated_data['expires_in_minutes'],
                max_file_size=serializer.validated_data.get('max_file_size')
            )
            return Response(result)
        except ValidationError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['post'])
    def download_url(self, request):
        """Generate a presigned URL for file download."""
        serializer = PresignedURLSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        service = get_presigned_url_service()
        
        try:
            result = service.generate_download_url(
                file_path=serializer.validated_data['file_path'],
                expires_in_minutes=serializer.validated_data['expires_in_minutes'],
                content_disposition=serializer.validated_data.get('content_disposition')
            )
            return Response(result)
        except ValidationError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['post'])
    def delete_url(self, request):
        """Generate a presigned URL for file deletion."""
        serializer = PresignedURLSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        service = get_presigned_url_service()
        
        try:
            result = service.generate_delete_url(
                file_path=serializer.validated_data['file_path'],
                expires_in_minutes=serializer.validated_data['expires_in_minutes']
            )
            return Response(result)
        except ValidationError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class NetworkDriveViewSet(viewsets.ViewSet):
    """
    ViewSet for managing Windows network drive mappings for Azure Files.
    Supports SMB 3.0 protocol for AutoCAD compatibility.
    """
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['get'])
    def list_drives(self, request):
        """List all currently mapped network drives."""
        try:
            drives = drive_manager.list_mapped_drives()
            return Response({
                'success': True,
                'drives': drives,
                'count': len(drives)
            })
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def drive_info(self, request):
        """Get information about a specific mapped drive."""
        drive_letter = request.query_params.get('drive_letter')
        if not drive_letter:
            return Response({
                'error': 'drive_letter parameter is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            info = drive_manager.get_drive_info(drive_letter)
            if info:
                return Response({
                    'success': True,
                    'drive': info
                })
            else:
                return Response({
                    'success': False,
                    'message': f'Drive {drive_letter}: is not mapped'
                }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def map_drive(self, request):
        """Map a network drive to Azure Files."""
        drive_letter = request.data.get('drive_letter')
        share_path = request.data.get('share_path')
        persistent = request.data.get('persistent', True)
        username = request.data.get('username')
        password = request.data.get('password')
        
        try:
            result = drive_manager.map_drive(
                drive_letter=drive_letter,
                share_path=share_path,
                persistent=persistent,
                username=username,
                password=password
            )
            
            if result['success']:
                return Response(result, status=status.HTTP_201_CREATED)
            else:
                return Response(result, status=status.HTTP_400_BAD_REQUEST)
                
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def unmap_drive(self, request):
        """Unmap a network drive."""
        drive_letter = request.data.get('drive_letter')
        force = request.data.get('force', False)
        
        if not drive_letter:
            return Response({
                'error': 'drive_letter parameter is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            result = drive_manager.unmap_drive(
                drive_letter=drive_letter,
                force=force
            )
            
            if result['success']:
                return Response(result)
            else:
                return Response(result, status=status.HTTP_400_BAD_REQUEST)
                
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def map_azure_files(self, request):
        """Map Azure Files to an available drive letter."""
        drive_letter = request.data.get('drive_letter')
        persistent = request.data.get('persistent', True)
        
        try:
            result = drive_manager.map_azure_files(
                drive_letter=drive_letter,
                persistent=persistent
            )
            
            if result['success']:
                return Response(result, status=status.HTTP_201_CREATED)
            else:
                return Response(result, status=status.HTTP_400_BAD_REQUEST)
                
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def map_smb_share(self, request):
        """Map any SMB share (NAS, Windows Server, local share, etc.) to a drive."""
        share_path = request.data.get('share_path')
        drive_letter = request.data.get('drive_letter')
        persistent = request.data.get('persistent', True)
        username = request.data.get('username')
        password = request.data.get('password')
        
        if not share_path:
            return Response({
                'error': 'share_path parameter is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            result = drive_manager.map_any_smb(
                share_path=share_path,
                drive_letter=drive_letter,
                persistent=persistent,
                username=username,
                password=password
            )
            
            if result['success']:
                return Response(result, status=status.HTTP_201_CREATED)
            else:
                return Response(result, status=status.HTTP_400_BAD_REQUEST)
                
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def available_drive(self, request):
        """Get an available drive letter."""
        start = request.query_params.get('start', 'Z')
        end = request.query_params.get('end', 'D')
        
        try:
            drive_letter = drive_manager.get_available_drive_letter(start=start, end=end)
            if drive_letter:
                return Response({
                    'success': True,
                    'drive_letter': drive_letter
                })
            else:
                return Response({
                    'success': False,
                    'message': 'No available drive letters in the specified range'
                }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def test_drive(self, request):
        """Test if a mapped drive is accessible."""
        drive_letter = request.query_params.get('drive_letter')
        if not drive_letter:
            return Response({
                'error': 'drive_letter parameter is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            result = drive_manager.test_drive_access(drive_letter)
            return Response(result)
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def azure_smb_path(self, request):
        """Get the SMB path for Azure Files configuration."""
        try:
            smb_path = drive_manager.get_azure_smb_path()
            return Response({
                'success': True,
                'smb_path': smb_path,
                'account_name': drive_manager.azure_account_name,
                'share_name': drive_manager.azure_share_name
            })
        except ValueError as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)