"""Database models for web_tts."""

from sqlalchemy import Column, String, DateTime, Integer, Text, Index
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()


class AudioHistory(Base):
    """Model for storing audio synthesis history."""

    __tablename__ = 'audio_history'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(64), nullable=False, index=True)  # From auth cookie
    file_id = Column(String(36), nullable=False, unique=True, index=True)  # UUID
    drive_file_id = Column(String(255), nullable=False)  # Google Drive file ID
    file_name = Column(String(255), nullable=False)  # Original filename (UUID.mp3)
    text_preview = Column(Text, nullable=True)  # First 200 chars of original text
    voice = Column(String(50), nullable=True)  # Voice used
    rate = Column(String(10), nullable=True)  # Speech rate
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)

    # Composite index for efficient user history queries
    __table_args__ = (
        Index('idx_user_created', 'user_id', 'created_at'),
    )

    def __repr__(self):
        return f"<AudioHistory(id={self.id}, user_id={self.user_id}, file_id={self.file_id})>"

    def to_dict(self):
        """Convert to dictionary for JSON serialization."""
        return {
            'id': self.id,
            'file_id': self.file_id,
            'file_name': self.file_name,
            'text_preview': self.text_preview,
            'voice': self.voice,
            'rate': self.rate,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
