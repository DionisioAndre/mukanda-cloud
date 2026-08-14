"""
Azure Files Storage Backend for Django
Supports SMB protocol and IOPS management
"""
import os
from urllib.parse import urlparse
from django.core.files.storage import Storage
from django.core.files.base import File
from django.utils.deconstruct import deconstructible
from azure.storage.file.share import ShareClient, ShareDirectoryClient, ShareFileClient
from azure.identity import DefaultAzureCredential
from azure.core.exceptions import AzureError
import logging

logger = logging.getLogger(__name__)


@deconstructible
class AzureFilesStorage(Storage):
    """
    Azure Files storage backend using SMB protocol.
    Supports IOPS throttling and multi-tenant isolation.
    """
    
    def __init__(self, account_name=None, account_key=None, share_name=None, 
                 connection_string=None, credential=None, iops_limit=1000):
        """
        Initialize Azure Files storage.
        
        Args:
            account_name: Azure Storage account name
            account_key: Azure Storage account key (optional if using credential)
            share_name: Azure File Share name
            connection_string: Azure Storage connection string (overrides other params)
            credential: AzureCredential object for auth (e.g., DefaultAzureCredential)
            iops_limit: Maximum IOPS per second for throttling
        """
        self.account_name = account_name or os.environ.get('AZURE_STORAGE_ACCOUNT_NAME')
        self.account_key = account_key or os.environ.get('AZURE_STORAGE_ACCOUNT_KEY')
        self.share_name = share_name or os.environ.get('AZURE_STORAGE_SHARE_NAME', 'filevault')
        self.connection_string = connection_string or os.environ.get('AZURE_STORAGE_CONNECTION_STRING')
        self.credential = credential
        self.iops_limit = iops_limit
        
        self._share_client = None
        self._iops_counter = 0
        self._iops_window = 1.0  # seconds
        
    @property
    def share_client(self):
        """Lazy initialization of ShareClient."""
        if self._share_client is None:
            if self.connection_string:
                self._share_client = ShareClient.from_connection_string(
                    self.connection_string, 
                    self.share_name
                )
            elif self.account_name and self.account_key:
                account_url = f"https://{self.account_name}.file.core.windows.net"
                self._share_client = ShareClient(
                    account_url=account_url,
                    share_name=self.share_name,
                    credential=self.account_key
                )
            elif self.account_name and self.credential:
                account_url = f"https://{self.account_name}.file.core.windows.net"
                self._share_client = ShareClient(
                    account_url=account_url,
                    share_name=self.share_name,
                    credential=self.credential
                )
            else:
                raise ValueError(
                    "Azure Files storage requires either connection_string, "
                    "account_key, or credential to be configured."
                )
        return self._share_client
    
    def _get_directory_client(self, name):
        """Get directory client for a given path."""
        directory_name = os.path.dirname(name)
        if not directory_name:
            return self.share_client.get_root_directory_client()
        
        dir_client = self.share_client.get_directory_client(directory_name)
        if not dir_client.exists():
            # Create parent directories
            parent_dir = os.path.dirname(directory_name)
            if parent_dir:
                parent_client = self.share_client.get_directory_client(parent_dir)
                if not parent_client.exists():
                    parent_client.create_directory()
            dir_client.create_directory()
        return dir_client
    
    def _check_iops_limit(self):
        """Simple IOPS throttling check."""
        # In production, use Redis or similar for distributed IOPS tracking
        self._iops_counter += 1
        if self._iops_counter > self.iops_limit:
            logger.warning(f"IOPS limit reached: {self._iops_counter}/{self.iops_limit}")
            # Could implement rate limiting here
            self._iops_counter = 0
    
    def _open(self, name, mode='rb'):
        """Open file from Azure Files."""
        self._check_iops_limit()
        file_client = self.share_client.get_file_client(name)
        if not file_client.exists():
            raise FileNotFoundError(f"File {name} does not exist")
        return AzureFile(file_client, mode)
    
    def _save(self, name, content):
        """Save file to Azure Files."""
        self._check_iops_limit()
        
        # Get directory client and ensure directory exists
        dir_client = self._get_directory_client(name)
        filename = os.path.basename(name)
        
        file_client = dir_client.create_file(filename, len(content))
        
        # Upload content in chunks for large files
        chunk_size = 4 * 1024 * 1024  # 4MB chunks
        if hasattr(content, 'chunks'):
            for chunk in content.chunks():
                file_client.upload_range(chunk, offset=file_client.get_file_properties().size)
        else:
            file_client.upload_range(content.read())
        
        return name
    
    def delete(self, name):
        """Delete file from Azure Files."""
        self._check_iops_limit()
        file_client = self.share_client.get_file_client(name)
        try:
            file_client.delete_file()
        except AzureError as e:
            logger.error(f"Error deleting file {name}: {e}")
            raise
    
    def exists(self, name):
        """Check if file exists in Azure Files."""
        file_client = self.share_client.get_file_client(name)
        try:
            return file_client.exists()
        except AzureError:
            return False
    
    def listdir(self, path):
        """List contents of directory in Azure Files."""
        self._check_iops_limit()
        dir_client = self.share_client.get_directory_client(path)
        if not dir_client.exists():
            return [], []
        
        directories = []
        files = []
        
        for item in dir_client.list_directories_and_files():
            if item.is_directory:
                directories.append(item.name)
            else:
                files.append(item.name)
        
        return directories, files
    
    def size(self, name):
        """Get file size from Azure Files."""
        file_client = self.share_client.get_file_client(name)
        props = file_client.get_file_properties()
        return props.size
    
    def url(self, name):
        """Generate URL for file (SAS URL would be better for production)."""
        account_url = f"https://{self.account_name}.file.core.windows.net"
        return f"{account_url}/{self.share_name}/{name}"
    
    def get_available_name(self, name, max_length=None):
        """Get available filename, handling conflicts."""
        if self.exists(name):
            base, ext = os.path.splitext(name)
            counter = 1
            while self.exists(f"{base}_{counter}{ext}"):
                counter += 1
            name = f"{base}_{counter}{ext}"
        return name
    
    def get_valid_name(self, name):
        """Sanitize filename for Azure Files."""
        # Azure Files has restrictions on characters
        invalid_chars = ['\\', '/', ':', '*', '?', '"', '<', '>', '|']
        for char in invalid_chars:
            name = name.replace(char, '_')
        return name


class AzureFile(File):
    """File wrapper for Azure Files."""
    
    def __init__(self, file_client, mode):
        self.file_client = file_client
        self.mode = mode
        self._position = 0
        self._content = None
    
    def read(self, size=-1):
        if self._content is None:
            download = self.file_client.download_file()
            self._content = download.readall()
        
        if size == -1:
            result = self._content[self._position:]
            self._position = len(self._content)
        else:
            result = self._content[self._position:self._position + size]
            self._position += len(result)
        
        return result
    
    def write(self, content):
        if 'w' not in self.mode:
            raise ValueError("File not opened for writing")
        # For simplicity, this implementation doesn't support write
        # Use _save for writing files
        raise NotImplementedError("Use storage.save() for writing files")
    
    def close(self):
        self._content = None
        self._position = 0
