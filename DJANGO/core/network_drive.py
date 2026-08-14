"""
Network Drive Mapping Module for SMB 3.0
Supports Windows SMB 3.0 network drive mapping (Z:, X:, etc.)
Works with any SMB server: Azure Files, NAS, Windows Server, local shares, etc.
"""
import os
import subprocess
import logging
import re
from typing import Optional, Dict, List, Tuple
from django.conf import settings

logger = logging.getLogger(__name__)


class NetworkDriveManager:
    """
    Manages Windows network drive mappings using SMB 3.0.
    Maps any SMB share as local drives (Z:, X:, etc.) for AutoCAD compatibility.
    Supports: Azure Files, NAS, Windows Server, local shares, etc.
    """
    
    def __init__(self):
        # Azure-specific (optional - for convenience)
        self.azure_account_name = os.environ.get('AZURE_STORAGE_ACCOUNT_NAME')
        self.azure_account_key = os.environ.get('AZURE_STORAGE_ACCOUNT_KEY')
        self.azure_share_name = os.environ.get('AZURE_STORAGE_SHARE_NAME', 'filevault')
        
    def get_azure_smb_path(self) -> str:
        """
        Generate SMB path for Azure Files.
        Format: \\\\{account_name}.file.core.windows.net\\{share_name}
        """
        if not self.azure_account_name:
            raise ValueError("AZURE_STORAGE_ACCOUNT_NAME not configured")
        if not self.azure_share_name:
            raise ValueError("AZURE_STORAGE_SHARE_NAME not configured")
        
        return f"\\\\{self.azure_account_name}.file.core.windows.net\\{self.azure_share_name}"
    
    def map_drive(self, drive_letter: str, share_path: Optional[str] = None, 
                  persistent: bool = True, username: Optional[str] = None,
                  password: Optional[str] = None) -> Dict[str, any]:
        """
        Map a network drive using Windows 'net use' command.
        
        Args:
            drive_letter: Drive letter (e.g., 'Z', 'X')
            share_path: SMB path (defaults to Azure Files path if not provided)
            persistent: Keep mapping after reboot
            username: SMB username (optional for public shares)
            password: SMB password (optional for public shares)
            
        Returns:
            Dict with success status and message
        """
        drive_letter = drive_letter.upper().replace(':', '')
        if len(drive_letter) != 1 or not drive_letter.isalpha():
            return {'success': False, 'message': 'Invalid drive letter'}
        
        # If share_path not provided, try Azure (if configured)
        if share_path is None:
            try:
                share_path = self.get_azure_smb_path()
                # Use Azure credentials if mapping Azure
                if username is None:
                    username = self.azure_account_name
                if password is None:
                    password = self.azure_account_key
            except ValueError:
                return {'success': False, 'message': 'share_path is required when Azure is not configured'}
        
        # Build net use command
        cmd = ['net', 'use', f'{drive_letter}:', share_path]
        
        # Add credentials only if provided (for authenticated shares)
        if username and password:
            cmd.extend(['/user', username, password])
        
        if persistent:
            cmd.append('/persistent:yes')
        else:
            cmd.append('/persistent:no')
        
        try:
            # Execute net use command
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True
            )
            
            logger.info(f"Drive {drive_letter}: mapped to {share_path}")
            return {
                'success': True,
                'message': f'Drive {drive_letter}: successfully mapped to {share_path}',
                'drive_letter': drive_letter,
                'share_path': share_path,
                'output': result.stdout
            }
            
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr.strip() if e.stderr else str(e)
            logger.error(f"Failed to map drive {drive_letter}: {error_msg}")
            return {
                'success': False,
                'message': f'Failed to map drive: {error_msg}',
                'error': error_msg
            }
        except Exception as e:
            logger.error(f"Error mapping drive {drive_letter}: {e}")
            return {
                'success': False,
                'message': f'Error: {str(e)}',
                'error': str(e)
            }
    
    def unmap_drive(self, drive_letter: str, force: bool = False) -> Dict[str, any]:
        """
        Unmap a network drive.
        
        Args:
            drive_letter: Drive letter to unmap (e.g., 'Z', 'X')
            force: Force unmap even if in use
            
        Returns:
            Dict with success status and message
        """
        drive_letter = drive_letter.upper().replace(':', '')
        if len(drive_letter) != 1 or not drive_letter.isalpha():
            return {'success': False, 'message': 'Invalid drive letter'}
        
        cmd = ['net', 'use', f'{drive_letter}:', '/delete']
        if force:
            cmd.append('/yes')
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True
            )
            
            logger.info(f"Drive {drive_letter}: unmapped")
            return {
                'success': True,
                'message': f'Drive {drive_letter}: successfully unmapped',
                'drive_letter': drive_letter,
                'output': result.stdout
            }
            
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr.strip() if e.stderr else str(e)
            logger.error(f"Failed to unmap drive {drive_letter}: {error_msg}")
            return {
                'success': False,
                'message': f'Failed to unmap drive: {error_msg}',
                'error': error_msg
            }
        except Exception as e:
            logger.error(f"Error unmapping drive {drive_letter}: {e}")
            return {
                'success': False,
                'message': f'Error: {str(e)}',
                'error': str(e)
            }
    
    def list_mapped_drives(self) -> List[Dict[str, str]]:
        """
        List all currently mapped network drives.
        
        Returns:
            List of dicts with drive info (letter, path, status)
        """
        drives = []
        
        try:
            result = subprocess.run(
                ['net', 'use'],
                capture_output=True,
                text=True,
                check=True
            )
            
            # Parse net use output
            lines = result.stdout.split('\n')
            for line in lines:
                # Pattern: Z:  \\account.file.core.windows.net\share  Microsoft Windows Network
                match = re.search(r'([A-Z]):\s+\\\\([^\s]+)\s+(.+)', line)
                if match:
                    drives.append({
                        'drive_letter': match.group(1),
                        'share_path': f'\\\\{match.group(2)}',
                        'status': match.group(3).strip()
                    })
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to list drives: {e}")
        except Exception as e:
            logger.error(f"Error listing drives: {e}")
        
        return drives
    
    def get_drive_info(self, drive_letter: str) -> Optional[Dict[str, str]]:
        """
        Get information about a specific mapped drive.
        
        Args:
            drive_letter: Drive letter (e.g., 'Z', 'X')
            
        Returns:
            Dict with drive info or None if not mapped
        """
        drive_letter = drive_letter.upper().replace(':', '')
        drives = self.list_mapped_drives()
        
        for drive in drives:
            if drive['drive_letter'] == drive_letter:
                return drive
        
        return None
    
    def is_drive_mapped(self, drive_letter: str) -> bool:
        """
        Check if a drive is currently mapped.
        
        Args:
            drive_letter: Drive letter (e.g., 'Z', 'X')
            
        Returns:
            True if mapped, False otherwise
        """
        return self.get_drive_info(drive_letter) is not None
    
    def get_available_drive_letter(self, start: str = 'Z', end: str = 'D') -> Optional[str]:
        """
        Find an available drive letter in the specified range.
        
        Args:
            start: Starting letter (default 'Z')
            end: Ending letter (default 'D')
            
        Returns:
            Available drive letter or None if none available
        """
        mapped_drives = self.list_mapped_drives()
        mapped_letters = {d['drive_letter'] for d in mapped_drives}
        
        # Check letters from start down to end
        for letter_code in range(ord(start.upper()), ord(end.upper()) - 1, -1):
            letter = chr(letter_code)
            if letter not in mapped_letters:
                return letter
        
        return None
    
    def map_azure_files(self, drive_letter: Optional[str] = None, 
                       persistent: bool = True) -> Dict[str, any]:
        """
        Convenience method to map Azure Files to a drive.
        
        Args:
            drive_letter: Drive letter (auto-selects if None)
            persistent: Keep mapping after reboot
            
        Returns:
            Dict with success status and drive info
        """
        if drive_letter is None:
            drive_letter = self.get_available_drive_letter()
            if drive_letter is None:
                return {
                    'success': False,
                    'message': 'No available drive letters'
                }
        
        return self.map_drive(drive_letter, persistent=persistent)
    
    def map_any_smb(self, share_path: str, drive_letter: Optional[str] = None,
                   persistent: bool = True, username: Optional[str] = None,
                   password: Optional[str] = None) -> Dict[str, any]:
        r"""
        Map any SMB share to a drive (NAS, Windows Server, local share, etc.).
        
        Args:
            share_path: SMB path (e.g., \\192.168.1.100\share or \\server\share)
            drive_letter: Drive letter (auto-selects if None)
            persistent: Keep mapping after reboot
            username: SMB username (if required)
            password: SMB password (if required)
            
        Returns:
            Dict with success status and drive info
        """
        if drive_letter is None:
            drive_letter = self.get_available_drive_letter()
            if drive_letter is None:
                return {
                    'success': False,
                    'message': 'No available drive letters'
                }
        
        return self.map_drive(
            drive_letter=drive_letter,
            share_path=share_path,
            persistent=persistent,
            username=username,
            password=password
        )
    
    def test_drive_access(self, drive_letter: str) -> Dict[str, any]:
        """
        Test if a mapped drive is accessible.
        
        Args:
            drive_letter: Drive letter to test
            
        Returns:
            Dict with test results
        """
        drive_letter = drive_letter.upper().replace(':', '')
        drive_path = f'{drive_letter}:\\'
        
        if not self.is_drive_mapped(drive_letter):
            return {
                'success': False,
                'message': f'Drive {drive_letter}: is not mapped'
            }
        
        try:
            # Test if drive is accessible
            if os.path.exists(drive_path):
                # Try to list contents
                try:
                    contents = os.listdir(drive_path)
                    return {
                        'success': True,
                        'message': f'Drive {drive_letter}: is accessible',
                        'drive_letter': drive_letter,
                        'item_count': len(contents)
                    }
                except PermissionError:
                    return {
                        'success': False,
                        'message': f'Drive {drive_letter}: permission denied',
                        'drive_letter': drive_letter
                    }
            else:
                return {
                    'success': False,
                    'message': f'Drive {drive_letter}: path does not exist',
                    'drive_letter': drive_letter
                }
                
        except Exception as e:
            logger.error(f"Error testing drive {drive_letter}: {e}")
            return {
                'success': False,
                'message': f'Error: {str(e)}',
                'error': str(e)
            }


# Singleton instance
drive_manager = NetworkDriveManager()
