"""
Test script for File API endpoints
"""
import requests
import json
from datetime import datetime

BASE_URL = "http://127.0.0.1:8000/api"

print("=" * 60)
print("FILE API TEST")
print("=" * 60)

# 1. Login to get token
print("\n1. Login:")
print("-" * 60)
login_response = requests.post(f"{BASE_URL}/auth/token/", json={
    "email": "admin@mukanda.com",
    "password": "admin123"
})

if login_response.status_code == 200:
    token = login_response.json()['access']
    print("✅ Login successful")
    headers = {"Authorization": f"Bearer {token}"}
else:
    print("❌ Login failed")
    exit(1)

# 2. Get user info
print("\n2. Get User Info:")
print("-" * 60)
me_response = requests.get(f"{BASE_URL}/auth/me/", headers=headers)
if me_response.status_code == 200:
    user = me_response.json()
    print(f"✅ User: {user['email']}")
    print(f"   Role: {user['role']}")
    print(f"   ID: {user['id']}")
    print(f"   Company ID: {user.get('company_id', 'None')}")
    print(f"   Company Name: {user.get('company_name', 'None')}")
else:
    print("❌ Failed to get user info")
    exit(1)

# 3. Create a folder
print("\n3. Create Folder:")
print("-" * 60)
company_id = user.get('company_id')
if not company_id:
    print("⚠️  User has no company assigned. Skipping folder creation.")
    folder_id = None
else:
    folder_data = {
        "name": f"Test Folder {datetime.now().strftime('%Y%m%d_%H%M%S')}",
        "node_type": "folder",
        "parent": None,
        "company": company_id
    }

    create_folder_response = requests.post(f"{BASE_URL}/files/nodes/", json=folder_data, headers=headers)
    if create_folder_response.status_code in [200, 201]:
        folder = create_folder_response.json()
        print(f"✅ Folder created: {folder['name']}")
        print(f"   ID: {folder['id']}")
        folder_id = folder['id']
    else:
        print(f"❌ Failed to create folder: {create_folder_response.text}")
        folder_id = None

# 4. List files
print("\n4. List Files:")
print("-" * 60)
list_response = requests.get(f"{BASE_URL}/files/nodes/", headers=headers)
if list_response.status_code == 200:
    files = list_response.json()
    print(f"✅ Found {len(files.get('results', files))} items")
    for item in files.get('results', files)[:5]:
        icon = "📁" if item['node_type'] == 'folder' else "📄"
        print(f"   {icon} {item['name']} ({item['node_type']})")
else:
    print(f"❌ Failed to list files: {list_response.text}")

# 5. Upload a test file
print("\n5. Upload Test File:")
print("-" * 60)

# Create a temporary test file
import tempfile
import os

test_filename = f"test_file_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
test_content = b"This is a test file content from Mukanda Cloud API test"

with tempfile.NamedTemporaryFile(mode='wb', delete=False, suffix='.txt') as temp_file:
    temp_file.write(test_content)
    temp_file_path = temp_file.name

try:
    # Prepare multipart form data
    files = {
        'file_field': (test_filename, open(temp_file_path, 'rb'), 'text/plain')
    }
    
    data = {
        "name": test_filename,
        "node_type": "file",
        "parent": folder_id if folder_id else "",
        "company": user['company_id']
    }
    
    upload_response = requests.post(f"{BASE_URL}/files/nodes/", data=data, files=files, headers=headers)
    
    # Close the file
    files['file_field'][1].close()
finally:
    # Clean up temp file
    if os.path.exists(temp_file_path):
        os.unlink(temp_file_path)

if upload_response.status_code in [200, 201]:
    uploaded_file = upload_response.json()
    print(f"✅ File uploaded: {uploaded_file['name']}")
    print(f"   ID: {uploaded_file['id']}")
    print(f"   Size: {uploaded_file.get('size', 'N/A')} bytes")
    file_id = uploaded_file['id']
else:
    print(f"❌ Failed to upload file: {upload_response.text}")
    file_id = None

# 6. Test file lock
if file_id:
    print("\n6. Test File Lock:")
    print("-" * 60)
    
    # Acquire lock
    lock_data = {
        "node": file_id,
        "lock_type": "exclusive",
        "duration_minutes": 30,
        "client_info": {
            "hostname": "test-client",
            "user_agent": "API Test Script"
        }
    }
    
    lock_response = requests.post(f"{BASE_URL}/files/locks/", json=lock_data, headers=headers)
    if lock_response.status_code in [200, 201]:
        lock = lock_response.json()
        print(f"✅ Lock acquired: {lock['id']}")
        print(f"   Locked by: {lock.get('locked_by_name', 'N/A')}")
        lock_id = lock['id']
    else:
        print(f"❌ Failed to acquire lock: {lock_response.text}")
        lock_id = None
    
    # Refresh lock
    if lock_id:
        refresh_response = requests.patch(f"{BASE_URL}/files/locks/{lock_id}/", 
                                          json={"duration_minutes": 60}, 
                                          headers=headers)
        if refresh_response.status_code == 200:
            print("✅ Lock refreshed to 60 minutes")
        else:
            print(f"❌ Failed to refresh lock: {refresh_response.text}")
    
    # Release lock
    if lock_id:
        release_response = requests.delete(f"{BASE_URL}/files/locks/{lock_id}/", headers=headers)
        if release_response.status_code == 204:
            print("✅ Lock released")
        else:
            print(f"❌ Failed to release lock: {release_response.text}")

# 7. Test file download
if file_id:
    print("\n7. Test File Download:")
    print("-" * 60)
    download_response = requests.get(f"{BASE_URL}/files/nodes/{file_id}/download/", headers=headers)
    if download_response.status_code == 200:
        print(f"✅ File downloaded successfully")
        print(f"   Content length: {len(download_response.content)} bytes")
    else:
        print(f"❌ Failed to download file: {download_response.text}")

# 8. Test file permissions
if file_id:
    print("\n8. Test File Permissions:")
    print("-" * 60)
    
    perm_data = {
        "node": file_id,
        "user": user['id'],
        "permission": "write"
    }
    
    perm_response = requests.post(f"{BASE_URL}/files/permissions/", json=perm_data, headers=headers)
    if perm_response.status_code in [200, 201]:
        print("✅ Permission granted")
    else:
        print(f"❌ Failed to grant permission: {perm_response.text}")

# 9. Cleanup
print("\n9. Cleanup:")
print("-" * 60)
if file_id:
    delete_response = requests.delete(f"{BASE_URL}/files/nodes/{file_id}/", headers=headers)
    if delete_response.status_code == 204:
        print(f"✅ Test file deleted")
    else:
        print(f"❌ Failed to delete file: {delete_response.text}")

if folder_id:
    delete_folder_response = requests.delete(f"{BASE_URL}/files/nodes/{folder_id}/", headers=headers)
    if delete_folder_response.status_code == 204:
        print(f"✅ Test folder deleted")
    else:
        print(f"❌ Failed to delete folder: {delete_folder_response.text}")

print("\n" + "=" * 60)
print("✅ FILE API TEST COMPLETED")
print("=" * 60)
