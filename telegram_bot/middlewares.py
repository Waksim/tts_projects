"""
Middlewares для Telegram Bot
"""

import logging
from typing import Callable, Dict, Any, Awaitable
from datetime import datetime, timedelta

from aiogram import BaseMiddleware, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.exceptions import TelegramBadRequest

from config import REQUIRED_CHANNEL_ID, OWNER_ID

logger = logging.getLogger(__name__)


class SubscriptionCheckMiddleware(BaseMiddleware):
    """
    Middleware для проверки подписки пользователя на обязательный канал.
    Использует API бота (bot.get_chat_member) для надежности.
    """

    def __init__(self):
        super().__init__()
        # Кэш проверок подписки: {user_id: (is_subscribed, check_time)}
        self._subscription_cache: Dict[int, tuple[bool, datetime]] = {}
        self._cache_ttl = timedelta(minutes=5)  # Время жизни кэша

    async def __call__(
        self,
        handler: Callable[[Message | CallbackQuery, Dict[str, Any]], Awaitable[Any]],
        event: Message | CallbackQuery,
        data: Dict[str, Any]
    ) -> Any:
        user_id = event.from_user.id
        bot: Bot = data['bot']  # Получаем объект бота из контекста

        # Логируем для отладки
        if isinstance(event, Message) and event.text:
            logger.info(f"Middleware: user_id={user_id}, OWNER_ID={OWNER_ID}, text='{event.text[:50]}'")

        # Владелец бота имеет полный доступ без проверок
        if user_id == OWNER_ID:
            logger.info(f"Owner detected! Allowing access for user_id={user_id}")
            return await handler(event, data)

        # Проверяем белый список
        from database import is_user_whitelisted
        is_whitelisted = await is_user_whitelisted(user_id)

        if is_whitelisted:
            # Пользователь в белом списке - пропускаем проверку подписки
            return await handler(event, data)

        # Проверяем кэш подписки
        cached_sub = self._subscription_cache.get(user_id)
        if cached_sub:
            is_subscribed, check_time = cached_sub
            if datetime.now() - check_time < self._cache_ttl and is_subscribed:
                return await handler(event, data)

        # Выполняем проверку подписки через API бота
        try:
            member = await bot.get_chat_member(chat_id=REQUIRED_CHANNEL_ID, user_id=user_id)
            is_subscribed = member.status not in ["left", "kicked"]

            # Обновляем кэш
            self._subscription_cache[user_id] = (is_subscribed, datetime.now())

            if is_subscribed:
                return await handler(event, data)

            # Пользователь не подписан
            await self._send_subscription_message(event)
            return None  # Прерываем выполнение

        except TelegramBadRequest as e:
            logger.error(f"Ошибка при проверке подписки (get_chat_member) для {user_id} в {REQUIRED_CHANNEL_ID}: {e}")
            await self._send_error_message(event)
            return None
        except Exception as e:
            logger.error(f"Критическая ошибка при проверке подписки для {user_id}: {e}")
            return await handler(event, data)

    async def _send_subscription_message(self, event: Message | CallbackQuery):
        """Отправляет сообщение с требованием связаться с администратором."""
        
        # --- ВАШЕ СООБЩЕНИЕ ---
        message_text = (
            "⛔️ <b>Доступ ограничен</b>\n\n"
            "Для использования бота напишите администратору @maksenro"
        )
        # ----------------------

        if isinstance(event, Message):
            await event.answer(message_text, parse_mode="HTML", disable_web_page_preview=True)
        elif isinstance(event, CallbackQuery):
            # Используем более общее сообщение для всплывающего уведомления
            await event.answer("⛔️ Доступ ограничен!", show_alert=True)
            await event.message.answer(message_text, parse_mode="HTML", disable_web_page_preview=True)

    async def _send_error_message(self, event: Message | CallbackQuery):
        """Отправляет сообщение об ошибке проверки."""
        error_text = "⚠️ Не удалось проверить подписку. Возможно, бот не является администратором в канале. Сообщите владельцу."
        if isinstance(event, Message):
            await event.answer(error_text)
        elif isinstance(event, CallbackQuery):
            await event.answer(error_text, show_alert=True)