"""Database operations for web_tts."""

import os
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Optional

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from models import Base, AudioHistory

# Database configuration
BASE_DIR = Path(__file__).parent
DATABASE_URL = f"sqlite:///{BASE_DIR / 'history.db'}"


class DatabaseManager:
    """Manager for database operations."""

    def __init__(self, database_url: str = DATABASE_URL):
        """Initialize database connection.

        Args:
            database_url: SQLAlchemy database URL
        """
        # Use StaticPool for SQLite to avoid threading issues
        self.engine = create_engine(
            database_url,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
            echo=False  # Set to True for SQL debugging
        )

        # Create tables if they don't exist
        Base.metadata.create_all(self.engine)

        # Session factory
        self.SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=self.engine
        )

    def get_session(self) -> Session:
        """Get a new database session.

        Returns:
            SQLAlchemy Session
        """
        return self.SessionLocal()

    def add_audio_record(
        self,
        user_id: str,
        file_id: str,
        drive_file_id: str,
        file_name: str,
        text_preview: str = None,
        voice: str = None,
        rate: str = None
    ) -> AudioHistory:
        """Add a new audio record to history.

        Args:
            user_id: User identifier
            file_id: Local file UUID
            drive_file_id: Google Drive file ID
            file_name: Original filename
            text_preview: Preview of the original text
            voice: Voice used for synthesis
            rate: Speech rate

        Returns:
            Created AudioHistory object
        """
        session = self.get_session()
        try:
            record = AudioHistory(
                user_id=user_id,
                file_id=file_id,
                drive_file_id=drive_file_id,
                file_name=file_name,
                text_preview=text_preview[:200] if text_preview else None,
                voice=voice,
                rate=rate,
                created_at=datetime.utcnow()
            )

            session.add(record)
            session.commit()
            session.refresh(record)

            print(f"[Database] Added record: file_id={file_id}, user_id={user_id}")
            return record

        except Exception as e:
            session.rollback()
            print(f"[Database] Error adding record: {e}")
            raise
        finally:
            session.close()

    def get_user_history(
        self,
        user_id: str,
        limit: int = 50,
        offset: int = 0
    ) -> List[AudioHistory]:
        """Get audio history for a specific user.

        Args:
            user_id: User identifier
            limit: Maximum number of records to return
            offset: Number of records to skip

        Returns:
            List of AudioHistory objects
        """
        session = self.get_session()
        try:
            records = session.query(AudioHistory).filter(
                AudioHistory.user_id == user_id
            ).order_by(
                AudioHistory.created_at.desc()
            ).limit(limit).offset(offset).all()

            return records

        finally:
            session.close()

    def get_record_by_file_id(self, file_id: str) -> Optional[AudioHistory]:
        """Get a record by file_id.

        Args:
            file_id: File UUID

        Returns:
            AudioHistory object or None
        """
        session = self.get_session()
        try:
            record = session.query(AudioHistory).filter(
                AudioHistory.file_id == file_id
            ).first()

            return record

        finally:
            session.close()

    def delete_old_records(self, days: int = 7) -> int:
        """Delete records older than specified days.

        Args:
            days: Number of days (records older than this will be deleted)

        Returns:
            Number of deleted records
        """
        session = self.get_session()
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days)

            # Get records to delete (to get drive_file_ids)
            old_records = session.query(AudioHistory).filter(
                AudioHistory.created_at < cutoff_date
            ).all()

            # Delete records
            deleted_count = session.query(AudioHistory).filter(
                AudioHistory.created_at < cutoff_date
            ).delete()

            session.commit()

            print(f"[Database] Deleted {deleted_count} records older than {days} days")
            return deleted_count

        except Exception as e:
            session.rollback()
            print(f"[Database] Error deleting old records: {e}")
            raise
        finally:
            session.close()

    def get_old_records(self, days: int = 7) -> List[AudioHistory]:
        """Get records older than specified days (for cleanup).

        Args:
            days: Number of days

        Returns:
            List of AudioHistory objects
        """
        session = self.get_session()
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days)

            old_records = session.query(AudioHistory).filter(
                AudioHistory.created_at < cutoff_date
            ).all()

            return old_records

        finally:
            session.close()

    def delete_record(self, file_id: str) -> bool:
        """Delete a specific record by file_id.

        Args:
            file_id: File UUID

        Returns:
            True if deleted, False otherwise
        """
        session = self.get_session()
        try:
            deleted_count = session.query(AudioHistory).filter(
                AudioHistory.file_id == file_id
            ).delete()

            session.commit()

            if deleted_count > 0:
                print(f"[Database] Deleted record: file_id={file_id}")
                return True
            else:
                print(f"[Database] Record not found: file_id={file_id}")
                return False

        except Exception as e:
            session.rollback()
            print(f"[Database] Error deleting record: {e}")
            raise
        finally:
            session.close()


# Singleton instance
_db_manager = None


def get_db_manager() -> DatabaseManager:
    """Get or create the DatabaseManager instance.

    Returns:
        DatabaseManager instance
    """
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseManager()
    return _db_manager
