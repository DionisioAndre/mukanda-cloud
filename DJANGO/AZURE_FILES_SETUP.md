# Azure Files Integration Guide

This document explains how to configure and use Azure Files with SMB protocol and IOPS management in the FileVault application.

## Overview

The FileVault application now supports Azure Files as a storage backend with:
- **SMB Protocol**: Native Azure Files integration using Azure Storage SDK
- **IOPS Management**: Rate limiting and throttling for storage operations
- **Multi-tenant Support**: Per-user and per-company IOPS limits
- **Automatic Fallback**: Uses local storage if Azure is not configured

## Prerequisites

1. Azure Storage Account with File Share
2. Azure Storage Account Key or Connection String
3. Python 3.8+
4. Redis (recommended for production cache)

## Installation

1. Install the required dependencies:
```bash
pip install -r requirements.txt
```

The following packages are added for Azure Files support:
- `azure-storage-file-share==12.15.0`
- `azure-identity==1.15.0`
- `azure-core==1.30.2`
- `smbprotocol==1.10.1`

## Configuration

### 1. Environment Variables

Copy `.env.example` to `.env` and configure your Azure credentials:

```bash
cp .env.example .env
```

Edit `.env` with your Azure credentials:

```env
AZURE_STORAGE_ACCOUNT_NAME=your_storage_account_name
AZURE_STORAGE_ACCOUNT_KEY=your_storage_account_key
# OR use connection string (recommended)
AZURE_STORAGE_CONNECTION_STRING=DefaultEndpointsProtocol=https;AccountName=...;AccountKey=...;EndpointSuffix=core.windows.net
AZURE_STORAGE_SHARE_NAME=filevault
```

### 2. IOPS Configuration

Configure IOPS limits based on your Azure Files tier:

```env
# Global IOPS limit (default: 1000)
AZURE_STORAGE_IOPS_LIMIT=1000

# Time window in seconds (default: 1.0)
AZURE_STORAGE_IOPS_WINDOW=1.0

# Per-user IOPS limit (default: 100)
AZURE_STORAGE_USER_IOPS_LIMIT=100

# Per-company IOPS limit (default: 500)
AZURE_STORAGE_COMPANY_IOPS_LIMIT=500

# Burst limit per IP (default: 100)
AZURE_STORAGE_BURST_LIMIT=100
```

### 3. Cache Configuration (Production)

For distributed IOPS tracking, configure Redis:

```env
REDIS_URL=redis://localhost:6379/1
```

Update Django settings to use Redis cache:

```python
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': os.environ.get('REDIS_URL', 'redis://127.0.0.1:6379/1'),
    }
}
```

## Azure Files Tiers and IOPS

Choose the appropriate IOPS limits based on your Azure Files tier:

| Tier | Max IOPS | Recommended Limit |
|------|----------|-------------------|
| Standard | 1000-5000 | 1000 |
| Premium | 3000-80000 | 5000-10000 |

## Usage

### Automatic Storage Selection

The application automatically uses Azure Files if configured, otherwise falls back to local storage.

### File Uploads

File uploads are automatically tracked for IOPS:

```python
# Upload is automatically tracked
POST /api/files/
Content-Type: multipart/form-data
file: <file>
```

### File Downloads

Downloads are also tracked:

```python
GET /api/files/{id}/download
```

### IOPS Monitoring

View IOPSstatistics using the `IOPSCounter` utility:

```python
from core.iops_middleware import IOPSCounter

stats = IOPSCounter.get_stats('upload')
print(f"Total uploads: {stats['total_operations']}")
print(f"Total bytes: {stats['total_bytes']}")
```

## API Rate Limit Headers

The API includes rate limit information in response headers:

```
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 950
X-RateLimit-Reset: 1234567890
X-RateLimit-User-Limit: 100
X-RateLimit-User-Remaining: 95
X-RateLimit-Company-Limit: 500
X-RateLimit-Company-Remaining: 450
```

When limits are exceeded, the API returns HTTP 429 with retry information.

## SMB Protocol Details

The Azure Files integration uses:
- **Azure Storage File Share SDK** for file operations
- **SMB Protocol** for file access (handled by Azure)
- **Chunked Uploads** for large files (4MB chunks)
- **Automatic Directory Creation** for nested paths

## Troubleshooting

### Connection Issues

If you get connection errors:
1. Verify your Azure credentials
2. Check that the File Share exists
3. Ensure your IP is whitelisted in Azure Network settings
4. Verify the storage account is in the same region

### IOPS Limit Exceeded

If you see 429 errors frequently:
1. Increase `AZURE_STORAGE_IOPS_LIMIT` in settings
2. Upgrade to a higher Azure Files tier
3. Implement client-side retry logic
4. Consider caching frequently accessed files

### Authentication Issues

For production, use Managed Identity instead of account keys:

```python
from azure.identity import DefaultAzureCredential

AZURE_FILES_STORAGE = AzureFilesStorage(
    account_name=AZURE_STORAGE_ACCOUNT_NAME,
    credential=DefaultAzureCredential(),
    share_name=AZURE_STORAGE_SHARE_NAME,
    iops_limit=AZURE_STORAGE_IOPS_LIMIT
)
```

## Migration from Local Storage

To migrate existing files from local storage to Azure Files:

1. Configure Azure Files
2. Run the migration script (create one if needed)
3. Update settings to use Azure Files
4. Verify file access

## Security Best Practices

1. **Never commit credentials** to version control
2. **Use Managed Identity** in production
3. **Enable HTTPS** for all Azure Storage operations
4. **Use SAS tokens** for temporary file access
5. **Monitor IOPS usage** to prevent throttling
6. **Implement backup strategy** for Azure Files

## Monitoring

Enable Azure Monitor for your Storage Account to track:
- IOPS usage
- Latency
- Error rates
- Capacity usage

## Cost Optimization

- Use appropriate Azure Files tier
- Implement lifecycle management policies
- Enable compression for large files
- Cache frequently accessed files
- Monitor and optimize IOPS patterns
