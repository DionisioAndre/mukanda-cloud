# Azure Files Configuration Guide

## Overview
Mukanda Cloud supports both local storage and Azure Files storage with SMB protocol. Azure Files provides cloud-based file storage with SMB protocol support, IOPS throttling, and multi-tenant isolation.

## Current Status
- ✅ **Local Storage**: Working correctly
- ⚠️ **Azure Files**: Not configured (environment variables not set)

## Azure Files Configuration

### Step 1: Create Azure Storage Account

1. Go to [Azure Portal](https://portal.azure.com)
2. Create a new Storage Account
3. Choose:
   - **Account kind**: StorageV2
   - **Replication**: LRS (Locally Redundant Storage) for testing
   - **Access tier**: Hot

### Step 2: Create File Share

1. In your Storage Account, go to "File shares"
2. Create a new file share named `filevault` (or your preferred name)
3. Configure quota (e.g., 100 GB for testing)

### Step 3: Get Access Keys

1. In your Storage Account, go to "Access keys"
2. Copy the **Storage account name** and **Key**
3. Alternatively, copy the **Connection string**

### Step 4: Set Environment Variables

#### Windows (PowerShell)
```powershell
$env:AZURE_STORAGE_ACCOUNT_NAME = "your_storage_account_name"
$env:AZURE_STORAGE_ACCOUNT_KEY = "your_storage_account_key"
# OR use connection string
$env:AZURE_STORAGE_CONNECTION_STRING = "DefaultEndpointsProtocol=https;AccountName=...;AccountKey=...;EndpointSuffix=core.windows.net"
$env:AZURE_STORAGE_SHARE_NAME = "filevault"
```

#### Windows (Command Prompt)
```cmd
set AZURE_STORAGE_ACCOUNT_NAME=your_storage_account_name
set AZURE_STORAGE_ACCOUNT_KEY=your_storage_account_key
set AZURE_STORAGE_CONNECTION_STRING=DefaultEndpointsProtocol=https;AccountName=...;AccountKey=...;EndpointSuffix=core.windows.net
set AZURE_STORAGE_SHARE_NAME=filevault
```

#### Linux/Mac
```bash
export AZURE_STORAGE_ACCOUNT_NAME="your_storage_account_name"
export AZURE_STORAGE_ACCOUNT_KEY="your_storage_account_key"
export AZURE_STORAGE_CONNECTION_STRING="DefaultEndpointsProtocol=https;AccountName=...;AccountKey=...;EndpointSuffix=core.windows.net"
export AZURE_STORAGE_SHARE_NAME="filevault"
```

#### Permanent Environment Variables (Windows)
```powershell
setx AZURE_STORAGE_ACCOUNT_NAME "your_storage_account_name"
setx AZURE_STORAGE_ACCOUNT_KEY "your_storage_account_key"
setx AZURE_STORAGE_CONNECTION_STRING "DefaultEndpointsProtocol=https;AccountName=...;AccountKey=...;EndpointSuffix=core.windows.net"
setx AZURE_STORAGE_SHARE_NAME "filevault"
```

### Step 5: Test Azure Connection

Run the test script to verify your Azure configuration:

```bash
cd DJANGO
python test_azure_connection.py
```

This will:
- ✅ Check environment variables
- ✅ Test connection to Azure Files
- ✅ Test file upload via SMB protocol
- ✅ Test file download
- ✅ Verify content integrity

## SMB Protocol Testing

The Azure Files integration uses SMB protocol for file operations. The test script validates:

1. **Connection**: Establishes SMB connection to Azure Files
2. **Upload**: Tests file upload via SMB protocol
3. **Download**: Tests file download and content verification
4. **IOPS**: Validates IOPS throttling configuration

## IOPS Configuration

Configure IOPS limits in `filevault/settings.py`:

```python
AZURE_STORAGE_IOPS_LIMIT = 1000  # Global IOPS limit
AZURE_STORAGE_IOPS_WINDOW = 1.0  # Time window in seconds
AZURE_STORAGE_BURST_LIMIT = 100  # Burst limit
AZURE_STORAGE_USER_IOPS_LIMIT = 100  # Per-user limit
AZURE_STORAGE_COMPANY_IOPS_LIMIT = 500  # Per-company limit
```

## Testing Results Summary

### Local Storage Tests ✅
- File upload: ✅ Working
- File download: ✅ Working
- Content integrity: ✅ Verified
- File deletion: ✅ Working

### API Tests ✅
- Login/Authentication: ✅ Working
- Folder creation: ✅ Working
- File listing: ✅ Working
- File upload: ✅ Working
- File download: ✅ Working
- File locking: ✅ Working
- Lock refresh: ✅ Working
- Lock release: ✅ Working

### Azure Files Tests ⚠️
- Status: Not configured
- Action: Set environment variables to enable

## Troubleshooting

### Common Issues

1. **"No valid Azure credentials found"**
   - Solution: Check environment variables are set correctly
   - Verify connection string or account key is valid

2. **"Share does not exist"**
   - Solution: Create the file share in Azure Portal first
   - Verify share name matches environment variable

3. **"Network connectivity issues"**
   - Solution: Check firewall settings
   - Verify Azure Storage endpoints are accessible
   - Check if corporate network blocks Azure endpoints

4. **"IOPS limit exceeded"**
   - Solution: Adjust IOPS limits in settings
   - Monitor rate limit headers in API responses

## Production Considerations

1. **Security**: Use managed identities instead of account keys in production
2. **Performance**: Monitor IOPS usage and adjust limits accordingly
3. **Backup**: Enable Azure Storage backup for file shares
4. **Monitoring**: Use Azure Monitor for storage metrics
5. **Cost**: Monitor storage costs and optimize usage

## Next Steps

1. Configure Azure environment variables
2. Run `python test_azure_connection.py` to verify
3. Test file operations through the frontend
4. Monitor IOPS rate limiting in the UI
5. Configure production-grade settings

## Support

For Azure-specific issues:
- [Azure Files Documentation](https://docs.microsoft.com/azure/storage/files/storage-files-introduction)
- [Azure Storage Python SDK](https://docs.microsoft.com/azure/storage/common/storage-python-how-to-use-blob-storage)
