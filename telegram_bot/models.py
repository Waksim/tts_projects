"""
Модели базы данных для Telegram Bot
"""

from datetime import datetime
from sqlalchemy import String, Integer, DateTime, Text, BigInteger, Boolean
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Request(Base):
    """Модель для хранения истории запросов пользователей."""

    __tablename__ = "requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    username: Mapped[str] = mapped_column(String(255), nullable=True)
    request_type: Mapped[str] = mapped_column(String(50), nullable=False)  # 'text', 'document', 'url'
    content: Mapped[str] = mapped_column(Text, nullable=False)  # Текст, имя файла или URL
    audio_path: Mapped[str] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False)  # 'success', 'error'
    error_message: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    def __repr__(self):
        return f"<Request(id={self.id}, user_id={self.user_id}, type={self.request_type})>"


class TrackedChannel(Base):
    """Модель для хранения отслеживаемых каналов."""

    __tablename__ = "tracked_channels"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    channel_username: Mapped[str] = mapped_column(String(255), nullable=False)  # @username канала
    channel_id: Mapped[int] = mapped_column(BigInteger, nullable=True)  # ID канала в Telegram
    channel_title: Mapped[str] = mapped_column(String(500), nullable=True)  # Название канала
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    def __repr__(self):
        return f"<TrackedChannel(id={self.id}, username={self.channel_username})>"


class TrackedChat(Base):
    """Модель для хранения отслеживаемых чатов."""

    __tablename__ = "tracked_chats"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    chat_username: Mapped[str] = mapped_column(String(255), nullable=True)  # @username или None
    chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False)  # ID чата в Telegram
    chat_title: Mapped[str] = mapped_column(String(500), nullable=True)  # Название чата
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    def __repr__(self):
        return f"<TrackedChat(id={self.id}, chat_id={self.chat_id})>"


class VoicedMessage(Base):
    """Модель для хранения озвученных сообщений."""

    __tablename__ = "voiced_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)  # 'channel' или 'chat'
    source_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)  # ID канала/чата
    message_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)  # ID сообщения
    message_text: Mapped[str] = mapped_column(Text, nullable=True)  # Текст сообщения
    audio_path: Mapped[str] = mapped_column(String(500), nullable=True)  # Путь к аудио
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    def __repr__(self):
        return f"<VoicedMessage(id={self.id}, source={self.source_type}, msg_id={self.message_id})>"


class UserSettings(Base):
    """Модель для хранения пользовательских настроек."""

    __tablename__ = "user_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, unique=True, index=True)
    voice_name: Mapped[str] = mapped_column(String(100), nullable=False, default="ru-RU-DmitryNeural")
    speech_rate: Mapped[str] = mapped_column(String(10), nullable=False, default="+50%")  # Скорость речи
    max_audio_duration_minutes: Mapped[int] = mapped_column(Integer, nullable=True, default=None)  # None = без лимита
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<UserSettings(user_id={self.user_id}, voice={self.voice_name}, rate={self.speech_rate}, max_duration={self.max_audio_duration_minutes})>"
