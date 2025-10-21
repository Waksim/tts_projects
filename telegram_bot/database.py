"""
Настройка базы данных для Telegram Bot
"""

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from models import Base
from config import DB_PATH


# Создаем async engine для SQLite
DATABASE_URL = f"sqlite+aiosqlite:///{DB_PATH}"
engine = create_async_engine(DATABASE_URL, echo=False)

# Создаем фабрику сессий
async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)


async def init_db():
    """Инициализирует базу данных, создает таблицы."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("[DB] База данных инициализирована")


async def get_session() -> AsyncSession:
    """Получает новую сессию БД."""
    async with async_session_factory() as session:
        yield session


async def save_request(
    user_id: int,
    username: str,
    request_type: str,
    content: str,
    audio_path: str = None,
    status: str = "success",
    error_message: str = None
):
    """
    Сохраняет запрос пользователя в базу данных.

    Args:
        user_id: Telegram ID пользователя
        username: Username пользователя
        request_type: Тип запроса ('text', 'document', 'url')
        content: Содержимое запроса
        audio_path: Путь к созданному аудиофайлу
        status: Статус обработки ('success', 'error')
        error_message: Сообщение об ошибке (если есть)
    """
    from models import Request

    async with async_session_factory() as session:
        request = Request(
            user_id=user_id,
            username=username,
            request_type=request_type,
            content=content,
            audio_path=audio_path,
            status=status,
            error_message=error_message
        )
        session.add(request)
        await session.commit()


# CRUD функции для отслеживания каналов и чатов

async def add_tracked_channel(
    user_id: int,
    channel_username: str,
    channel_id: int = None,
    channel_title: str = None
):
    """Добавляет канал в отслеживаемые."""
    from models import TrackedChannel
    from sqlalchemy import select

    async with async_session_factory() as session:
        # Проверяем, не добавлен ли уже
        stmt = select(TrackedChannel).where(
            TrackedChannel.user_id == user_id,
            TrackedChannel.channel_username == channel_username
        )
        result = await session.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            # Обновляем существующий
            existing.is_active = True
            if channel_id:
                existing.channel_id = channel_id
            if channel_title:
                existing.channel_title = channel_title
        else:
            # Создаем новый
            channel = TrackedChannel(
                user_id=user_id,
                channel_username=channel_username,
                channel_id=channel_id,
                channel_title=channel_title
            )
            session.add(channel)

        await session.commit()


async def add_tracked_chat(
    user_id: int,
    chat_id: int,
    chat_username: str = None,
    chat_title: str = None
):
    """Добавляет чат в отслеживаемые."""
    from models import TrackedChat
    from sqlalchemy import select

    async with async_session_factory() as session:
        # Проверяем, не добавлен ли уже
        stmt = select(TrackedChat).where(
            TrackedChat.user_id == user_id,
            TrackedChat.chat_id == chat_id
        )
        result = await session.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            # Обновляем существующий
            existing.is_active = True
            if chat_username:
                existing.chat_username = chat_username
            if chat_title:
                existing.chat_title = chat_title
        else:
            # Создаем новый
            chat = TrackedChat(
                user_id=user_id,
                chat_id=chat_id,
                chat_username=chat_username,
                chat_title=chat_title
            )
            session.add(chat)

        await session.commit()


async def get_tracked_channels(user_id: int):
    """Возвращает список отслеживаемых каналов пользователя."""
    from models import TrackedChannel
    from sqlalchemy import select

    async with async_session_factory() as session:
        stmt = select(TrackedChannel).where(
            TrackedChannel.user_id == user_id,
            TrackedChannel.is_active == True
        )
        result = await session.execute(stmt)
        return result.scalars().all()


async def get_tracked_chats(user_id: int):
    """Возвращает список отслеживаемых чатов пользователя."""
    from models import TrackedChat
    from sqlalchemy import select

    async with async_session_factory() as session:
        stmt = select(TrackedChat).where(
            TrackedChat.user_id == user_id,
            TrackedChat.is_active == True
        )
        result = await session.execute(stmt)
        return result.scalars().all()


async def save_voiced_message(
    user_id: int,
    source_type: str,
    source_id: int,
    message_id: int,
    message_text: str = None,
    audio_path: str = None
):
    """Сохраняет информацию об озвученном сообщении."""
    from models import VoicedMessage

    async with async_session_factory() as session:
        voiced_msg = VoicedMessage(
            user_id=user_id,
            source_type=source_type,
            source_id=source_id,
            message_id=message_id,
            message_text=message_text,
            audio_path=audio_path
        )
        session.add(voiced_msg)
        await session.commit()


async def get_last_voiced_message_id(user_id: int, source_type: str, source_id: int):
    """Возвращает ID последнего озвученного сообщения для источника."""
    from models import VoicedMessage
    from sqlalchemy import select, desc

    async with async_session_factory() as session:
        stmt = select(VoicedMessage.message_id).where(
            VoicedMessage.user_id == user_id,
            VoicedMessage.source_type == source_type,
            VoicedMessage.source_id == source_id
        ).order_by(desc(VoicedMessage.message_id)).limit(1)

        result = await session.execute(stmt)
        last_id = result.scalar_one_or_none()
        return last_id if last_id else 0
