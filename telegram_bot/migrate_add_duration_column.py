#!/usr/bin/env python3
"""
Database migration script: Add max_audio_duration_minutes column to user_settings table

This script adds the missing 'max_audio_duration_minutes' column to the user_settings table.
Safe to run multiple times - checks if column already exists.

Usage:
    python migrate_add_duration_column.py
"""

import sqlite3
import sys
from pathlib import Path

# Database path - same as in config.py
DB_PATH = Path(__file__).parent / "bot_history.db"


def column_exists(cursor, table_name: str, column_name: str) -> bool:
    """Check if a column exists in a table."""
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = [row[1] for row in cursor.fetchall()]
    return column_name in columns


def main():
    db_path = Path(DB_PATH)

    if not db_path.exists():
        print(f"❌ Database not found at: {db_path}")
        print("   The database will be created automatically when the bot starts.")
        return 0

    print(f"📊 Connecting to database: {db_path}")

    try:
        # Connect to the database
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()

        # Check if user_settings table exists
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='user_settings'
        """)

        if not cursor.fetchone():
            print("⚠️  Table 'user_settings' does not exist yet.")
            print("   It will be created when the bot starts.")
            conn.close()
            return 0

        # Check if column already exists
        if column_exists(cursor, 'user_settings', 'max_audio_duration_minutes'):
            print("✅ Column 'max_audio_duration_minutes' already exists in 'user_settings' table.")
            print("   No migration needed.")
            conn.close()
            return 0

        # Add the missing column
        print("🔧 Adding column 'max_audio_duration_minutes' to 'user_settings' table...")

        cursor.execute("""
            ALTER TABLE user_settings
            ADD COLUMN max_audio_duration_minutes INTEGER DEFAULT NULL
        """)

        conn.commit()

        print("✅ Migration completed successfully!")
        print("   Column 'max_audio_duration_minutes' has been added to 'user_settings' table.")

        # Verify the column was added
        if column_exists(cursor, 'user_settings', 'max_audio_duration_minutes'):
            print("✅ Verification: Column exists and is ready to use.")
        else:
            print("❌ Verification failed: Column was not added properly.")
            conn.close()
            return 1

        conn.close()
        return 0

    except sqlite3.Error as e:
        print(f"❌ Database error: {e}")
        return 1
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
