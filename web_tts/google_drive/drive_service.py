"""Google Drive service for uploading and managing audio files."""

import os
import io
from typing import Optional, Dict, List
from datetime import datetime, timedelta

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload

from .config import SCOPES, TOKEN_FILE, CREDENTIALS_FILE, DRIVE_FOLDER_NAME


class GoogleDriveService:
    """Service for Google Drive operations."""

    def __init__(self):
        """Initialize with OAuth authentication."""
        self.service = None
        self.folder_id = None
        self._authenticate()

    def _authenticate(self):
        """Authenticate using token.json, auto-refresh if expired."""
        if not os.path.exists(TOKEN_FILE):
            raise FileNotFoundError(
                f"Token file '{TOKEN_FILE}' not found. "
                "Please run create_token.py first to authenticate."
            )

        try:
            creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

            # Check if credentials are valid or can be refreshed
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    print(f"[GoogleDrive] Token expired, refreshing...")
                    try:
                        creds.refresh(Request())
                        # Save the refreshed credentials
                        with open(TOKEN_FILE, 'w') as token:
                            token.write(creds.to_json())
                        print("[GoogleDrive] Token refreshed successfully")
                    except Exception as refresh_error:
                        raise ValueError(
                            f"Failed to refresh token: {refresh_error}\n"
                            "Your token may have been revoked. Please delete token.json and "
                            "run create_token.py again."
                        )
                else:
                    raise ValueError(
                        "Invalid credentials. Please delete token.json and run create_token.py."
                    )

            self.service = build('drive', 'v3', credentials=creds)
            print("[GoogleDrive] Service initialized successfully")

        except Exception as e:
            print(f"[GoogleDrive] Authentication error: {e}")
            raise

    def _find_or_create_folder(self, folder_name: str) -> str:
        """Find folder by name or create if doesn't exist.

        Args:
            folder_name: Name of the folder

        Returns:
            Folder ID
        """
        try:
            # Search for existing folder
            query = (
                f"name='{folder_name}' and "
                "mimeType='application/vnd.google-apps.folder' and "
                "trashed=false"
            )

            results = self.service.files().list(
                q=query,
                spaces='drive',
                fields='files(id, name)',
                pageSize=1
            ).execute()

            files = results.get('files', [])

            if files:
                folder_id = files[0]['id']
                print(f"[GoogleDrive] Found existing folder: {folder_name} (ID: {folder_id})")
                return folder_id

            # Create new folder if not found
            file_metadata = {
                'name': folder_name,
                'mimeType': 'application/vnd.google-apps.folder'
            }

            folder = self.service.files().create(
                body=file_metadata,
                fields='id'
            ).execute()

            folder_id = folder.get('id')
            print(f"[GoogleDrive] Created new folder: {folder_name} (ID: {folder_id})")
            return folder_id

        except HttpError as error:
            print(f"[GoogleDrive] Error finding/creating folder: {error}")
            raise

    def get_folder_id(self) -> str:
        """Get or create the main audio folder ID.

        Returns:
            Folder ID
        """
        if self.folder_id is None:
            self.folder_id = self._find_or_create_folder(DRIVE_FOLDER_NAME)
        return self.folder_id

    def upload_file(self, file_path: str, original_filename: str = None) -> Optional[str]:
        """Upload a file to Google Drive.

        Args:
            file_path: Local path to the file
            original_filename: Optional custom filename (uses basename if not provided)

        Returns:
            Google Drive file ID, or None if upload failed
        """
        try:
            folder_id = self.get_folder_id()

            file_name = original_filename or os.path.basename(file_path)

            file_metadata = {
                'name': file_name,
                'parents': [folder_id]
            }

            media = MediaFileUpload(
                file_path,
                mimetype='audio/mpeg',
                resumable=True
            )

            print(f"[GoogleDrive] Uploading file: {file_name}")
            file = self.service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id,name,size,createdTime'
            ).execute()

            file_id = file.get('id')
            file_size = file.get('size', 0)
            print(f"[GoogleDrive] Upload successful: {file_name} (ID: {file_id}, Size: {file_size} bytes)")

            return file_id

        except HttpError as error:
            print(f"[GoogleDrive] Error uploading file {file_path}: {error}")
            return None

    def download_file(self, file_id: str, local_path: str) -> bool:
        """Download entire file from Google Drive to local path.

        Args:
            file_id: Google Drive file ID
            local_path: Local path to save the file

        Returns:
            True if successful, False otherwise
        """
        try:
            request = self.service.files().get_media(fileId=file_id)

            with io.FileIO(local_path, 'wb') as fh:
                downloader = MediaIoBaseDownload(fh, request)
                done = False
                while not done:
                    status, done = downloader.next_chunk()
                    if status:
                        print(f"[GoogleDrive] Download progress: {int(status.progress() * 100)}%")

            print(f"[GoogleDrive] Download complete: {local_path}")
            return True

        except HttpError as error:
            print(f"[GoogleDrive] Error downloading file {file_id}: {error}")
            return False

    def get_file_content(self, file_id: str) -> Optional[bytes]:
        """Get file content as bytes (for streaming).

        Args:
            file_id: Google Drive file ID

        Returns:
            File content as bytes, or None if failed
        """
        try:
            request = self.service.files().get_media(fileId=file_id)

            file_content = io.BytesIO()
            downloader = MediaIoBaseDownload(file_content, request)

            done = False
            while not done:
                status, done = downloader.next_chunk()

            file_content.seek(0)
            return file_content.read()

        except HttpError as error:
            print(f"[GoogleDrive] Error getting file content {file_id}: {error}")
            return None

    def get_file_metadata(self, file_id: str) -> Optional[Dict]:
        """Get file metadata.

        Args:
            file_id: Google Drive file ID

        Returns:
            File metadata dictionary, or None if failed
        """
        try:
            file_metadata = self.service.files().get(
                fileId=file_id,
                fields='id,name,size,createdTime,mimeType'
            ).execute()
            return file_metadata

        except HttpError as error:
            print(f"[GoogleDrive] Error getting file metadata {file_id}: {error}")
            return None

    def delete_file(self, file_id: str) -> bool:
        """Delete a file from Google Drive.

        Args:
            file_id: Google Drive file ID

        Returns:
            True if successful, False otherwise
        """
        try:
            self.service.files().delete(fileId=file_id).execute()
            print(f"[GoogleDrive] Deleted file: {file_id}")
            return True

        except HttpError as error:
            print(f"[GoogleDrive] Error deleting file {file_id}: {error}")
            return False

    def list_old_files(self, days: int = 7) -> List[Dict]:
        """List files older than specified days in the audio folder.

        Args:
            days: Number of days (files older than this will be listed)

        Returns:
            List of file metadata dictionaries
        """
        try:
            folder_id = self.get_folder_id()

            # Calculate the cutoff date
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            cutoff_date_str = cutoff_date.isoformat() + 'Z'

            # Query for old files
            query = (
                f"'{folder_id}' in parents and "
                f"createdTime < '{cutoff_date_str}' and "
                "trashed=false"
            )

            results = self.service.files().list(
                q=query,
                spaces='drive',
                fields='files(id, name, createdTime, size)',
                pageSize=100
            ).execute()

            files = results.get('files', [])
            print(f"[GoogleDrive] Found {len(files)} files older than {days} days")

            return files

        except HttpError as error:
            print(f"[GoogleDrive] Error listing old files: {error}")
            return []


# Singleton instance
_drive_service = None


def get_drive_service(force_refresh: bool = False) -> GoogleDriveService:
    """Get or create the Google Drive service instance.

    Args:
        force_refresh: If True, recreate the service instance

    Returns:
        GoogleDriveService instance
    """
    global _drive_service
    if _drive_service is None or force_refresh:
        _drive_service = GoogleDriveService()
    return _drive_service
