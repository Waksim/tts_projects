"""Configuration for Google Drive integration."""

import os
from pathlib import Path

# OAuth 2.0 settings
SCOPES = ['https://www.googleapis.com/auth/drive']

# Project root directory
BASE_DIR = Path(__file__).parent.parent

# Credentials files
CREDENTIALS_FILE = str(BASE_DIR / 'credentials.json')
TOKEN_FILE = str(BASE_DIR / 'token.json')

# Google Drive folder name for audio files
DRIVE_FOLDER_NAME = os.getenv('DRIVE_FOLDER_NAME', 'WebTTS_Audio')

# Audio file extensions
AUDIO_EXTENSIONS = ['mp3', 'wav', 'ogg']

# File retention period (in days)
FILE_RETENTION_DAYS = 7
