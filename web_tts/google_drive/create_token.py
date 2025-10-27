"""Create OAuth token for Google Drive access.

This script should be run once to create the token.json file.
It will open a browser window for Google authentication.
"""

import os
from google_auth_oauthlib.flow import InstalledAppFlow
from .config import SCOPES, TOKEN_FILE, CREDENTIALS_FILE


def create_token():
    """Create OAuth token through browser authentication flow."""

    if not os.path.exists(CREDENTIALS_FILE):
        print(f"ERROR: {CREDENTIALS_FILE} not found!")
        print("\nTo get credentials.json:")
        print("1. Go to https://console.cloud.google.com/")
        print("2. Create a new project or select existing")
        print("3. Enable Google Drive API")
        print("4. Create OAuth 2.0 credentials (Desktop app)")
        print("5. Download the JSON file and save as 'credentials.json'")
        return

    print("Starting OAuth authentication flow...")
    print("A browser window will open for authentication.")
    print("Please log in and grant permissions.")

    try:
        flow = InstalledAppFlow.from_client_secrets_file(
            CREDENTIALS_FILE,
            SCOPES
        )

        creds = flow.run_local_server(port=0)

        # Save the credentials
        with open(TOKEN_FILE, 'w') as token:
            token.write(creds.to_json())

        print(f"\n✓ Successfully created {TOKEN_FILE}")
        print("You can now use the Google Drive integration!")

    except Exception as e:
        print(f"\n✗ Error during authentication: {e}")


if __name__ == '__main__':
    create_token()
