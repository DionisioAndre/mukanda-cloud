# Azure Files 2 - Network Drive Mapping

## Overview

Azure Files 2 extends the original Azure Files integration with **Windows network drive mapping** using SMB 3.0 protocol. This allows users to map Azure File Shares as local drives (Z:, X:, etc.) for native AutoCAD compatibility and optimal performance.

## Key Features

- **SMB 3.0 Protocol**: Native Windows network drive mapping
- **AutoCAD Compatibility**: Mapped drives work like local disks
- **Automatic Drive Selection**: Finds available drive letters automatically
- **Persistent Mapping**: Option to keep drives mapped after reboot
- **API Endpoints**: RESTful API for drive management
- **Drive Management**: List, map, unmap, and test network drives

## Architecture

### Components

1. **NetworkDriveManager** (`core/network_drive.py`)
   - Core module for Windows network drive operations
   - Uses `net use` commands via subprocess
   - Manages drive letter allocation and mapping

2. **NetworkDriveViewSet** (`apps/files/views.py`)
   - REST API endpoints for drive management
   - Authentication required for all operations

3. **Test Scripts**
   - `test_network_drive.py`: Full test with Azure credentials
   - `test_network_drive_basic.py`: Basic module test

## Installation

No additional dependencies required. Uses standard Python libraries:
- `subprocess` (built-in)
- `os` (built-in)
- `re` (built-in)

## Configuration

### Environment Variables

Set the following environment variables for Azure Files:

```env
AZURE_STORAGE_ACCOUNT_NAME=your_storage_account_name
AZURE_STORAGE_ACCOUNT_KEY=your_storage_account_key
AZURE_STORAGE_SHARE_NAME=filevault
```

### SMB Path Format

The module automatically generates SMB paths in the format:
```
\\{account_name}.file.core.windows.net\{share_name}
```

Example:
```
\\mukandafilevault.file.core.windows.net\filevault
```

## API Endpoints

All endpoints require authentication.

### List Mapped Drives

```http
GET /api/files/network-drives/list_drives/
```

Response:
```json
{
  "success": true,
  "drives": [
    {
      "drive_letter": "Z",
      "share_path": "\\account.file.core.windows.net\share",
      "status": "Microsoft Windows Network"
    }
  ],
  "count": 1
}
```

### Get Drive Info

```http
GET /api/files/network-drives/drive_info/?drive_letter=Z
```

Response:
```json
{
  "success": true,
  "drive": {
    "drive_letter": "Z",
    "share_path": "\\account.file.core.windows.net\share",
    "status": "Microsoft Windows Network"
  }
}
```

### Map Azure Files (Auto-select Drive)

```http
POST /api/files/network-drives/map_azure_files/
Content-Type: application/json

{
  "drive_letter": "Z",
  "persistent": true
}
```

Response:
```json
{
  "success": true,
  "message": "Drive Z: successfully mapped to \\account.file.core.windows.net\share",
  "drive_letter": "Z",
  "share_path": "\\account.file.core.windows.net\share"
}
```

### Map Custom Drive

```http
POST /api/files/network-drives/map_drive/
Content-Type: application/json

{
  "drive_letter": "X",
  "share_path": "\\custom.server\share",
  "persistent": true,
  "username": "user",
  "password": "pass"
}
```

### Unmap Drive

```http
POST /api/files/network-drives/unmap_drive/
Content-Type: application/json

{
  "drive_letter": "Z",
  "force": true
}
```

### Get Available Drive Letter

```http
GET /api/files/network-drives/available_drive/?start=Z&end=D
```

Response:
```json
{
  "success": true,
  "drive_letter": "Z"
}
```

### Test Drive Access

```http
GET /api/files/network-drives/test_drive/?drive_letter=Z
```

Response:
```json
{
  "success": true,
  "message": "Drive Z: is accessible",
  "drive_letter": "Z",
  "item_count": 5
}
```

### Get Azure SMB Path

```http
GET /api/files/network-drives/azure_smb_path/
```

Response:
```json
{
  "success": true,
  "smb_path": "\\account.file.core.windows.net\share",
  "account_name": "account",
  "share_name": "share"
}
```

## Usage Examples

### Python API

```python
from core.network_drive import drive_manager

# Map Azure Files to an available drive
result = drive_manager.map_azure_files(persistent=True)
print(f"Mapped to {result['drive_letter']}:")

# List all mapped drives
drives = drive_manager.list_mapped_drives()
for drive in drives:
    print(f"{drive['drive_letter']}: -> {drive['share_path']}")

# Unmap a drive
drive_manager.unmap_drive('Z', force=True)

# Check if drive is mapped
if drive_manager.is_drive_mapped('Z'):
    print("Drive Z: is mapped")

# Find available drive letter
available = drive_manager.get_available_drive_letter()
print(f"Available drive: {available}:")
```

### Manual Windows Command

To manually map a drive using Windows command:

```cmd
net use Z: \\account.file.core.windows.net\share /user:account_name account_key /persistent:yes
```

Or use the Azure Portal script:
1. Go to Azure Portal → Storage Account → File Share
2. Click "Connect"
3. Select "Windows" and copy the provided script

## Testing

### Basic Test (No Azure Credentials Required)

```bash
cd DJANGO
python test_network_drive_basic.py
```

This tests:
- Drive listing
- Drive status checking
- Available drive detection
- Drive info retrieval

### Full Test (Requires Azure Credentials)

```bash
cd DJANGO
# Set environment variables first
set AZURE_STORAGE_ACCOUNT_NAME=your_account
set AZURE_STORAGE_ACCOUNT_KEY=your_key
set AZURE_STORAGE_SHARE_NAME=filevault

python test_network_drive.py
```

This tests:
- Azure configuration
- SMB path generation
- Drive mapping
- Drive access testing
- Drive unmapping

## AutoCAD Integration

### Benefits

1. **Native Performance**: AutoCAD treats mapped drives as local disks
2. **No Sync Issues**: Direct SMB access eliminates sync delays
3. **Large File Support**: SMB 3.0 handles large CAD files efficiently
4. **Network Transparency**: Users work with familiar drive letters

### Setup for AutoCAD Users

1. Map the Azure Files share to a drive letter (e.g., Z:)
2. In AutoCAD, use the mapped drive path: `Z:\projects\file.dwg`
3. AutoCAD will access files via SMB 3.0 with optimal performance

### Performance Comparison

| Method | Performance | AutoCAD Compatibility |
|--------|------------|----------------------|
| SharePoint/OneDrive | Slow (sync delays) | Poor |
| Azure Files Web API | Medium | Requires custom integration |
| **Network Drive (SMB)** | **Fast (native)** | **Excellent** |

## Security Considerations

### Credentials

- **Never commit** Azure credentials to version control
- Use environment variables or secure vaults
- Consider using Managed Identity in production

### Network Security

- Azure Files supports SMB 3.0 encryption
- Configure Azure Storage firewalls
- Use VPN for corporate network access

### Drive Persistence

- Persistent mappings store credentials in Windows credential manager
- For shared computers, consider non-persistent mappings
- Implement drive mapping policies via Group Policy

## Troubleshooting

### "No valid Azure credentials found"

**Solution**: Check environment variables are set correctly
```powershell
$env:AZURE_STORAGE_ACCOUNT_NAME
$env:AZURE_STORAGE_ACCOUNT_KEY
$env:AZURE_STORAGE_SHARE_NAME
```

### "Drive already in use"

**Solution**: Unmap the existing drive first or use a different letter
```python
drive_manager.unmap_drive('Z', force=True)
```

### "Network path not found"

**Solution**: 
- Verify Azure Storage account name is correct
- Check File Share exists in Azure Portal
- Ensure network connectivity to Azure endpoints

### "Access denied"

**Solution**:
- Verify account key is correct
- Check IP whitelist in Azure Storage settings
- Ensure SMB 3.0 is enabled on client machine

### "No available drive letters"

**Solution**:
- Unmap unused drives
- Specify a different range: `get_available_drive_letter(start='Y', end='E')`

## Windows Requirements

- Windows 7 or later
- SMB 3.0 support (Windows 8+ recommended)
- Administrator privileges for drive mapping
- Network connectivity to Azure Storage endpoints

## Limitations

- **Windows Only**: Network drive mapping is Windows-specific
- **Admin Rights**: Requires administrator privileges
- **Client-Side**: Mapping occurs on client machines, not server
- **Credential Storage**: Persistent mappings store credentials locally

## Future Enhancements

- [ ] Linux SMB mount support (using `mount.cifs`)
- [ ] macOS SMB mount support
- [ ] Group Policy integration for enterprise deployment
- [ ] Drive mapping templates per user/department
- [ ] Automatic reconnection on network changes
- [ ] Drive usage monitoring and reporting

## Comparison: Azure Files vs Azure Files 2

| Feature | Azure Files (Original) | Azure Files 2 (Network Drive) |
|---------|----------------------|-------------------------------|
| Server-side API | ✅ Yes | ✅ Yes |
| SMB Protocol | ✅ Yes (server-side) | ✅ Yes (client-side) |
| Network Drive Mapping | ❌ No | ✅ Yes |
| AutoCAD Native Support | ❌ No | ✅ Yes |
| Local Drive Experience | ❌ No | ✅ Yes |
| Web API Access | ✅ Yes | ✅ Yes |

## Support

For issues:
1. Check the troubleshooting section above
2. Run `test_network_drive_basic.py` to verify module functionality
3. Review Azure Storage logs in Azure Portal
4. Check Windows Event Viewer for SMB errors
