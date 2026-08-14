"""
Presigned URL Service for Azure Files
Generates time-limited URLs for direct client-to-storage upload/download
"""
import os
from datetime import timedelta, datetime
from django.conf import settings
from django.utils import timezone
from django.core.exceptions import ValidationError

# Try to import Azure SDK, but handle gracefully if not installed
try:
    from azure.storage.file.share import (
        ShareFileClient,
        generate_file_sas,
        ShareSasPermissions
    )
    from azure.core.exceptions import AzureError
    AZURE_AVAILABLE = True
except ImportError:
    AZURE_AVAILABLE = False


class PresignedURLService:
    """
    Service for generating presigned URLs for direct Azure Files access.
    This allows clients to upload/download files directly without proxying through Django.
    """

    def __init__(self):
        self.account_name = getattr(settings, 'AZURE_STORAGE_ACCOUNT_NAME', None)
        self.account_key = getattr(settings, 'AZURE_STORAGE_ACCOUNT_KEY', None)
        self.share_name = getattr(settings, 'AZURE_STORAGE_SHARE_NAME', 'filevault')
        self.connection_string = getattr(settings, 'AZURE_STORAGE_CONNECTION_STRING', None)

        if not AZURE_AVAILABLE:
            raise ValueError("Azure SDK not installed. Install azure-storage-file-share package.")

        if not (self.account_name or self.connection_string):
            raise ValueError("Azure Storage credentials not configured")
    
    def generate_upload_url(
        self, 
        file_path, 
        expires_in_minutes=60,
        max_file_size=1024 * 1024 * 1024  # 1GB default
    ):
        """
        Generate a presigned URL for file upload.
        
        Args:
            file_path: Path where the file will be stored (e.g., 'files/2024/01/document.pdf')
            expires_in_minutes: URL expiration time in minutes
            max_file_size: Maximum file size in bytes
            
        Returns:
            dict: {
                'upload_url': str,
                'method': 'PUT',
                'headers': dict,
                'expires_at': datetime
            }
        """
        try:
            # Create file client
            file_client = self._get_file_client(file_path)
            
            # Generate SAS token with write permissions
            sas_token = self._generate_sas_token(
                file_path,
                permission=ShareSasPermissions(write=True, create=True),
                expires_in_minutes=expires_in_minutes
            )
            
            # Build upload URL
            account_url = f"https://{self.account_name}.file.core.windows.net"
            upload_url = f"{account_url}/{self.share_name}/{file_path}?{sas_token}"
            
            return {
                'upload_url': upload_url,
                'method': 'PUT',
                'headers': {
                    'x-ms-file-type': 'file',
                    'x-ms-content-length': str(max_file_size),
                },
                'expires_at': (timezone.now() + timedelta(minutes=expires_in_minutes)).isoformat(),
                'file_path': file_path
            }
            
        except AzureError as e:
            raise ValidationError(f"Failed to generate upload URL: {str(e)}")
    
    def generate_download_url(
        self, 
        file_path, 
        expires_in_minutes=60,
        content_disposition=None
    ):
        """
        Generate a presigned URL for file download.
        
        Args:
            file_path: Path to the file (e.g., 'files/2024/01/document.pdf')
            expires_in_minutes: URL expiration time in minutes
            content_disposition: Content disposition header (e.g., 'attachment; filename="doc.pdf"')
            
        Returns:
            dict: {
                'download_url': str,
                'method': 'GET',
                'expires_at': datetime
            }
        """
        try:
            # Generate SAS token with read permissions
            sas_token = self._generate_sas_token(
                file_path,
                permission=ShareSasPermissions(read=True),
                expires_in_minutes=expires_in_minutes
            )
            
            # Build download URL
            account_url = f"https://{self.account_name}.file.core.windows.net"
            download_url = f"{account_url}/{self.share_name}/{file_path}?{sas_token}"
            
            if content_disposition:
                download_url += f"&response-content-disposition={content_disposition}"
            
            return {
                'download_url': download_url,
                'method': 'GET',
                'expires_at': (timezone.now() + timedelta(minutes=expires_in_minutes)).isoformat(),
                'file_path': file_path
            }
            
        except AzureError as e:
            raise ValidationError(f"Failed to generate download URL: {str(e)}")
    
    def generate_delete_url(self, file_path, expires_in_minutes=10):
        """
        Generate a presigned URL for file deletion.
        
        Args:
            file_path: Path to the file
            expires_in_minutes: URL expiration time in minutes
            
        Returns:
            dict: {
                'delete_url': str,
                'method': 'DELETE',
                'expires_at': datetime
            }
        """
        try:
            sas_token = self._generate_sas_token(
                file_path,
                permission=ShareSasPermissions(delete=True),
                expires_in_minutes=expires_in_minutes
            )
            
            account_url = f"https://{self.account_name}.file.core.windows.net"
            delete_url = f"{account_url}/{self.share_name}/{file_path}?{sas_token}"
            
            return {
                'delete_url': delete_url,
                'method': 'DELETE',
                'expires_at': (timezone.now() + timedelta(minutes=expires_in_minutes)).isoformat(),
                'file_path': file_path
            }
            
        except AzureError as e:
            raise ValidationError(f"Failed to generate delete URL: {str(e)}")
    
    def _get_file_client(self, file_path):
        """Get Azure File client for the given path."""
        account_url = f"https://{self.account_name}.file.core.windows.net"
        
        if self.connection_string:
            from azure.storage.file.share import ShareClient
            share_client = ShareClient.from_connection_string(
                self.connection_string,
                self.share_name
            )
        else:
            from azure.storage.file.share import ShareClient
            share_client = ShareClient(
                account_url=account_url,
                share_name=self.share_name,
                credential=self.account_key
            )
        
        return share_client.get_file_client(file_path)
    
    def _generate_sas_token(self, file_path, permission, expires_in_minutes):
        """
        Generate SAS token for Azure Files.
        
        Args:
            file_path: Path to the file
            permission: ShareSasPermissions object
            expires_in_minutes: Expiration time in minutes
            
        Returns:
            str: SAS token string
        """
        from datetime import datetime, timedelta
        
        account_url = f"https://{self.account_name}.file.core.windows.net"
        
        sas_token = generate_file_sas(
            account_name=self.account_name,
            share_name=self.share_name,
            file_path=file_path,
            account_key=self.account_key,
            permission=permission,
            expiry=datetime.utcnow() + timedelta(minutes=expires_in_minutes),
            protocol='https'
        )
        
        return sas_token
    
    def verify_file_exists(self, file_path):
        """
        Verify if a file exists in Azure Files.
        
        Args:
            file_path: Path to the file
            
        Returns:
            bool: True if file exists
        """
        try:
            file_client = self._get_file_client(file_path)
            return file_client.exists()
        except AzureError:
            return False
    
    def get_file_properties(self, file_path):
        """
        Get file properties from Azure Files.
        
        Args:
            file_path: Path to the file
            
        Returns:
            dict: File properties (size, content_type, etc.)
        """
        try:
            file_client = self._get_file_client(file_path)
            props = file_client.get_file_properties()
            return {
                'size': props.size,
                'content_type': props.content_settings.content_type,
                'last_modified': props.last_modified,
                'metadata': props.metadata
            }
        except AzureError as e:
            raise ValidationError(f"Failed to get file properties: {str(e)}")


# Fallback for local storage (when Azure is not configured)
class LocalPresignedURLService:
    """
    Fallback service for local storage.
    Returns regular Django URLs instead of presigned URLs.
    """
    
    def generate_upload_url(self, file_path, expires_in_minutes=60, max_file_size=None):
        from django.urls import reverse
        return {
            'upload_url': reverse('file-upload'),  # Would need to implement this endpoint
            'method': 'POST',
            'headers': {},
            'expires_at': None,
            'file_path': file_path,
            'note': 'Using local storage - presigned URLs not available'
        }
    
    def generate_download_url(self, file_path, expires_in_minutes=60, content_disposition=None):
        from django.urls import reverse
        return {
            'download_url': reverse('file-download', kwargs={'path': file_path}),
            'method': 'GET',
            'expires_at': None,
            'file_path': file_path,
            'note': 'Using local storage - presigned URLs not available'
        }
    
    def generate_delete_url(self, file_path, expires_in_minutes=10):
        from django.urls import reverse
        return {
            'delete_url': reverse('file-delete', kwargs={'path': file_path}),
            'method': 'DELETE',
            'expires_at': None,
            'file_path': file_path,
            'note': 'Using local storage - presigned URLs not available'
        }


def get_presigned_url_service():
    """
    Factory function to get the appropriate presigned URL service.
    Returns Azure service if configured, otherwise local fallback.
    """
    if hasattr(settings, 'AZURE_STORAGE_ACCOUNT_NAME') or hasattr(settings, 'AZURE_STORAGE_CONNECTION_STRING'):
        return PresignedURLService()
    return LocalPresignedURLService()
