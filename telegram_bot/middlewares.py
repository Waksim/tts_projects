"""
Middlewares для Telegram Bot
"""

import logging
from typing import Callable, Dict, Any, Awaitable
from datetime import datetime, timedelta

from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery

from config import REQUIRED_CHANNEL_ID, REQUIRED_CHANNEL_USERNAME
from telethon_service import get_telethon_service

logger = logging.getLogger(__name__)


class SubscriptionCheckMiddleware(BaseMiddleware):
    """
    Middleware для проверки подписки пользователя на обязательный канал.
    """

    def __init__(self):
        super().__init__()
        # Кэш проверок подписки: {user_id: (is_subscribed, check_time)}
        self._subscription_cache: Dict[int, tuple[bool, datetime]] = {}
        # Время жизни кэша - 5 минут
        self._cache_ttl = timedelta(minutes=5)

    async def __call__(
        self,
        handler: Callable[[Message | CallbackQuery, Dict[str, Any]], Awaitable[Any]],
        event: Message | CallbackQuery,
        data: Dict[str, Any]
    ) -> Any:
        """
        Проверяет подписку пользователя перед выполнением обработчика.

        Args:
            handler: Обработчик события
            event: Событие (Message или CallbackQuery)
            data: Данные контекста

        Returns:
            Результат выполнения обработчика или None
        """
        user_id = event.from_user.id

        # Проверяем кэш
        if user_id in self._subscription_cache:
            is_subscribed, check_time = self._subscription_cache[user_id]

            # Если кэш актуален и пользователь подписан
            if datetime.now() - check_time < self._cache_ttl and is_subscribed:
                return await handler(event, data)

        # Выполняем проверку подписки
        try:
            telethon = await get_telethon_service()
            is_subscribed = await telethon.is_user_subscribed(user_id, REQUIRED_CHANNEL_ID)

            # Обновляем кэш
            self._subscription_cache[user_id] = (is_subscribed, datetime.now())

            if is_subscribed:
                return await handler(event, data)

            # Пользователь не подписан
            await self._send_subscription_message(event)
            return None

        except Exception as e:
            logger.error(f"Ошибка при проверке подписки пользователя {user_id}: {e}")
            # В случае ошибки пропускаем пользователя
            return await handler(event, data)

    async def _send_subscription_message(self, event: Message | CallbackQuery):
        """
        Отправляет сообщение с требованием подписки.

        Args:
            event: Событие (Message или CallbackQuery)
        """
        message_text = (
            "⛔️ <b>Доступ ограничен</b>\n\n"
            "Для использования бота напишите администратору @maksenro"
        )

        if isinstance(event, Message):
            await event.answer(message_text, parse_mode="HTML")
        elif isinstance(event, CallbackQuery):
            await event.answer("⛔️ Требуется подписка на канал!", show_alert=True)
            await event.message.answer(message_text, parse_mode="HTML")
