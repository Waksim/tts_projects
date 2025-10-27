"""Test the Google Drive token validity.

This script checks if the token.json file exists and is valid.
It will also test basic Drive API access.
"""

import os
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from .config import SCOPES, TOKEN_FILE


def test_token():
    """Test if token is valid and can access Drive API."""

    if not os.path.exists(TOKEN_FILE):
        print(f"✗ {TOKEN_FILE} not found!")
        print("Run create_token.py first to authenticate.")
        return False

    try:
        print(f"Loading credentials from {TOKEN_FILE}...")
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

        # Check if credentials are valid
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                print("Token expired, attempting to refresh...")
                creds.refresh(Request())

                # Save refreshed token
                with open(TOKEN_FILE, 'w') as token:
                    token.write(creds.to_json())

                print("✓ Token refreshed successfully!")
            else:
                print("✗ Token is invalid and cannot be refreshed")
                print("Please delete token.json and run create_token.py again")
                return False
        else:
            print("✓ Token is valid!")

        # Test Drive API access
        print("\nTesting Drive API access...")
        service = build('drive', 'v3', credentials=creds)

        # Try to list files (just to test access)
        results = service.files().list(pageSize=1, fields="files(id, name)").execute()

        print("✓ Successfully connected to Google Drive API!")
        print(f"✓ Your Drive is accessible")

        return True

    except Exception as e:
        print(f"\n✗ Error: {e}")
        return False


if __name__ == '__main__':
    success = test_token()
    exit(0 if success else 1)
