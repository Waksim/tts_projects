"""
Сервис для работы с Telethon User API
"""

import logging
from typing import List, Optional, Tuple
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.types import Channel, User, Chat, Message
from telethon.errors import SessionPasswordNeededError

logger = logging.getLogger(__name__)


class TelethonService:
    """Сервис для работы с Telegram User API через Telethon."""

    def __init__(self, session_string: str, api_id: int, api_hash: str, phone: str):
        """
        Инициализация клиента Telethon.

        Args:
            session_string: Строка сессии для авторизации
            api_id: API ID приложения
            api_hash: API Hash приложения
            phone: Номер телефона
        """
        self.phone = phone
        self.api_id = api_id
        self.api_hash = api_hash
        self.session_string = session_string
        self.client: Optional[TelegramClient] = None

    async def start(self):
        """Запускает клиент Telethon."""
        try:
            # Создаем сессию из строки
            session = StringSession(self.session_string)

            # Создаем клиента
            self.client = TelegramClient(
                session,
                self.api_id,
                self.api_hash
            )

            await self.client.connect()

            if not await self.client.is_user_authorized():
                logger.warning("Клиент не авторизован, требуется повторная авторизация")
                # Можно добавить логику переавторизации если потребуется

            logger.info("Telethon клиент успешно запущен")

        except Exception as e:
            logger.error(f"Ошибка при запуске Telethon клиента: {e}")
            raise

    async def stop(self):
        """Останавливает клиент Telethon."""
        if self.client:
            await self.client.disconnect()
            logger.info("Telethon клиент остановлен")

    async def get_channel_info(self, username: str) -> Optional[Tuple[int, str]]:
        """
        Получает информацию о канале по username.

        Args:
            username: Username канала (с @ или без)

        Returns:
            Tuple[channel_id, channel_title] или None если не найден
        """
        try:
            # Убираем @ если есть
            username = username.lstrip('@')

            entity = await self.client.get_entity(username)

            if isinstance(entity, Channel):
                return (entity.id, entity.title)
            else:
                logger.warning(f"Entity {username} не является каналом")
                return None

        except Exception as e:
            logger.error(f"Ошибка при получении информации о канале {username}: {e}")
            return None

    async def get_chat_info(self, identifier: str) -> Optional[Tuple[int, str, Optional[str]]]:
        """
        Получает информацию о чате по username или ID.

        Args:
            identifier: Username (с @) или ID чата

        Returns:
            Tuple[chat_id, chat_title, username] или None если не найден
        """
        try:
            # Пробуем преобразовать в int (если это ID)
            try:
                chat_id = int(identifier)
                entity = await self.client.get_entity(chat_id)
            except ValueError:
                # Это username
                username = identifier.lstrip('@')
                entity = await self.client.get_entity(username)

            # Получаем информацию в зависимости от типа
            if isinstance(entity, User):
                username = entity.username if hasattr(entity, 'username') else None
                title = f"{entity.first_name or ''} {entity.last_name or ''}".strip()
                return (entity.id, title, username)
            elif isinstance(entity, (Chat, Channel)):
                username = entity.username if hasattr(entity, 'username') else None
                return (entity.id, entity.title, username)
            else:
                logger.warning(f"Неизвестный тип entity: {type(entity)}")
                return None

        except Exception as e:
            logger.error(f"Ошибка при получении информации о чате {identifier}: {e}")
            return None

    async def get_channel_messages(
        self,
        channel_username: str,
        limit: int = 10,
        min_id: int = 0
    ) -> List[Tuple[int, str]]:
        """
        Получает последние сообщения из канала.

        Args:
            channel_username: Username канала
            limit: Максимальное количество сообщений
            min_id: ID сообщения, с которого начинать (не включая его)

        Returns:
            List[Tuple[message_id, message_text]]
        """
        try:
            username = channel_username.lstrip('@')
            entity = await self.client.get_entity(username)

            messages = []
            async for message in self.client.iter_messages(
                entity,
                limit=limit,
                reverse=False,  # От новых к старым
                min_id=min_id
            ):
                # Извлекаем текст из сообщения (даже если есть медиа)
                text = self._extract_message_text(message)
                if text:
                    messages.append((message.id, text))

            # Разворачиваем чтобы от старых к новым
            messages.reverse()
            return messages

        except Exception as e:
            logger.error(f"Ошибка при получении сообщений из канала {channel_username}: {e}")
            return []

    async def get_chat_messages(
        self,
        chat_id: int,
        limit: int = 10,
        min_id: int = 0
    ) -> List[Tuple[int, str]]:
        """
        Получает последние сообщения из чата.

        Args:
            chat_id: ID чата
            limit: Максимальное количество сообщений
            min_id: ID сообщения, с которого начинать (не включая его)

        Returns:
            List[Tuple[message_id, message_text]]
        """
        try:
            entity = await self.client.get_entity(chat_id)

            messages = []
            async for message in self.client.iter_messages(
                entity,
                limit=limit,
                reverse=False,
                min_id=min_id
            ):
                # Извлекаем текст из сообщения (даже если есть медиа)
                text = self._extract_message_text(message)
                if text:
                    messages.append((message.id, text))

            # Разворачиваем чтобы от старых к новым
            messages.reverse()
            return messages

        except Exception as e:
            logger.error(f"Ошибка при получении сообщений из чата {chat_id}: {e}")
            return []

    def _extract_message_text(self, message: Message) -> Optional[str]:
        """
        Извлекает текст из сообщения, игнорируя медиа.

        Args:
            message: Объект сообщения Telethon

        Returns:
            Текст сообщения или None
        """
        if not message:
            return None

        # Получаем текст сообщения
        text = message.message or ""

        # Если есть caption (описание медиа), добавляем его
        if hasattr(message, 'media') and message.media:
            # У некоторых медиа может быть caption
            if hasattr(message.media, 'caption'):
                caption = message.media.caption or ""
                if caption and caption != text:
                    text = f"{text}\n{caption}".strip()

        return text.strip() if text.strip() else None


# Глобальный экземпляр сервиса
_telethon_service: Optional[TelethonService] = None


async def get_telethon_service() -> TelethonService:
    """Возвращает глобальный экземпляр TelethonService."""
    global _telethon_service

    if _telethon_service is None:
        raise RuntimeError("TelethonService не инициализирован. Вызовите init_telethon_service() сначала.")

    return _telethon_service


async def init_telethon_service(session_string: str, api_id: int, api_hash: str, phone: str):
    """
    Инициализирует глобальный экземпляр TelethonService.

    Args:
        session_string: Строка сессии
        api_id: API ID
        api_hash: API Hash
        phone: Номер телефона
    """
    global _telethon_service

    _telethon_service = TelethonService(session_string, api_id, api_hash, phone)
    await _telethon_service.start()
    logger.info("TelethonService инициализирован")


async def stop_telethon_service():
    """Останавливает глобальный экземпляр TelethonService."""
    global _telethon_service

    if _telethon_service:
        await _telethon_service.stop()
        _telethon_service = None
