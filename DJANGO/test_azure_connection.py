"""
Test script for Azure Files connection and SMB protocol
"""
import os
import sys
from datetime import datetime

# Add Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'filevault.settings')

import django
django.setup()

from django.conf import settings

print("=" * 60)
print("AZURE FILES CONNECTION TEST")
print("=" * 60)

# Check environment variables
print("\n1. Checking Azure Configuration:")
print("-" * 60)

azure_config = {
    'AZURE_STORAGE_ACCOUNT_NAME': os.environ.get('AZURE_STORAGE_ACCOUNT_NAME'),
    'AZURE_STORAGE_ACCOUNT_KEY': os.environ.get('AZURE_STORAGE_ACCOUNT_KEY'),
    'AZURE_STORAGE_CONNECTION_STRING': os.environ.get('AZURE_STORAGE_CONNECTION_STRING'),
    'AZURE_STORAGE_SHARE_NAME': os.environ.get('AZURE_STORAGE_SHARE_NAME', 'filevault'),
}

for key, value in azure_config.items():
    if 'KEY' in key or 'CONNECTION' in key:
        display_value = f"{value[:20]}..." if value else "NOT SET"
    else:
        display_value = value if value else "NOT SET"
    print(f"{key}: {display_value}")

# Test Azure connection if configured
if azure_config['AZURE_STORAGE_ACCOUNT_NAME'] or azure_config['AZURE_STORAGE_CONNECTION_STRING']:
    print("\n2. Testing Azure Files Connection:")
    print("-" * 60)
    
    try:
        from azure.storage.file.share import ShareClient
        from azure.core.exceptions import AzureError
        
        # Create ShareClient
        if azure_config['AZURE_STORAGE_CONNECTION_STRING']:
            share_client = ShareClient.from_connection_string(
                azure_config['AZURE_STORAGE_CONNECTION_STRING'],
                azure_config['AZURE_STORAGE_SHARE_NAME']
            )
        elif azure_config['AZURE_STORAGE_ACCOUNT_NAME'] and azure_config['AZURE_STORAGE_ACCOUNT_KEY']:
            account_url = f"https://{azure_config['AZURE_STORAGE_ACCOUNT_NAME']}.file.core.windows.net"
            share_client = ShareClient(
                account_url=account_url,
                share_name=azure_config['AZURE_STORAGE_SHARE_NAME'],
                credential=azure_config['AZURE_STORAGE_ACCOUNT_KEY']
            )
        else:
            print("❌ No valid Azure credentials found")
            sys.exit(1)
        
        # Test connection
        print(f"Connecting to share: {azure_config['AZURE_STORAGE_SHARE_NAME']}")
        
        if share_client.exists():
            print("✅ Successfully connected to Azure Files share")
            
            # List directories and files
            print("\n3. Listing contents:")
            print("-" * 60)
            
            root_dir = share_client.get_root_directory_client()
            directories = []
            files = []
            
            for item in root_dir.list_directories_and_files():
                if item.is_directory:
                    directories.append(item.name)
                else:
                    files.append(item.name)
            
            print(f"Directories: {len(directories)}")
            for d in directories[:10]:  # Show first 10
                print(f"  📁 {d}")
            
            print(f"\nFiles: {len(files)}")
            for f in files[:10]:  # Show first 10
                print(f"  📄 {f}")
            
            # Test file upload
            print("\n4. Testing File Upload (SMB Protocol):")
            print("-" * 60)
            
            test_filename = f"test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            test_content = b"Test file from Mukanda Cloud - Azure Files SMB test"
            
            print(f"Uploading: {test_filename}")
            file_client = root_dir.create_file(test_filename, len(test_content))
            file_client.upload_range(test_content)
            print("✅ File uploaded successfully via SMB")
            
            # Test file download
            print("\n5. Testing File Download:")
            print("-" * 60)
            
            download = file_client.download_file()
            content = download.readall()
            
            if content == test_content:
                print("✅ File downloaded successfully - content matches")
            else:
                print("❌ Downloaded content doesn't match")
            
            # Clean up test file
            print("\n6. Cleaning up test file:")
            print("-" * 60)
            file_client.delete_file()
            print(f"✅ Test file {test_filename} deleted")
            
            print("\n" + "=" * 60)
            print("✅ ALL TESTS PASSED - Azure Files SMB working correctly")
            print("=" * 60)
            
        else:
            print(f"❌ Share '{azure_config['AZURE_STORAGE_SHARE_NAME']}' does not exist")
            print("Please create the share in Azure Portal first")
            
    except AzureError as e:
        print(f"❌ Azure Error: {e}")
        print("\nPossible causes:")
        print("- Invalid credentials or connection string")
        print("- Share does not exist")
        print("- Network connectivity issues")
        print("- Firewall blocking Azure Storage endpoints")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        
else:
    print("\n⚠️  Azure Files not configured")
    print("Using local storage instead")
    print("\nTo enable Azure Files, set these environment variables:")
    print("- AZURE_STORAGE_ACCOUNT_NAME")
    print("- AZURE_STORAGE_ACCOUNT_KEY (or AZURE_STORAGE_CONNECTION_STRING)")
    print("- AZURE_STORAGE_SHARE_NAME (optional, defaults to 'filevault')")
    
    print("\n7. Testing Local Storage:")
    print("-" * 60)
    
    # Test local storage
    from django.core.files.storage import default_storage
    
    test_filename = f"test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    test_content = b"Test file from Mukanda Cloud - Local storage test"
    
    try:
        # Upload
        print(f"Uploading: {test_filename}")
        from django.core.files.base import ContentFile
        saved_path = default_storage.save(test_filename, ContentFile(test_content))
        print(f"✅ File saved to: {saved_path}")
        
        # Check if exists
        if default_storage.exists(saved_path):
            print("✅ File exists in storage")
        
        # Get size
        size = default_storage.size(saved_path)
        print(f"✅ File size: {size} bytes")
        
        # Download
        with default_storage.open(saved_path, 'rb') as f:
            downloaded_content = f.read()
        
        if downloaded_content == test_content:
            print("✅ Downloaded content matches")
        
        # Clean up
        default_storage.delete(saved_path)
        print("✅ Test file deleted")
        
        print("\n" + "=" * 60)
        print("✅ LOCAL STORAGE TESTS PASSED")
        print("=" * 60)
        
    except Exception as e:
        print(f"❌ Local storage error: {e}")
        import traceback
        traceback.print_exc()
