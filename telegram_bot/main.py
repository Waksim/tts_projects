"""
Telegram Bot для озвучивания текста
Главный файл запуска
"""

# КРИТИЧНО: Двойная защита от uvloop (одной переменной недостаточно!)
import os
import sys

os.environ['AIOGRAM_NO_UVLOOP'] = '1'

# ОБЯЗАТЕЛЬНО для Python 3.13+ (переменная окружения может не сработать!)
if sys.version_info >= (3, 13):
    import asyncio
    asyncio.set_event_loop_policy(asyncio.DefaultEventLoopPolicy())
else:
    import asyncio

import logging
import ssl
from pathlib import Path

import aiohttp
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
# --- НОВЫЕ ИМПОРТЫ для меню команд ---
from aiogram.types import BotCommand, BotCommandScopeDefault, BotCommandScopeChat
# ------------------------------------

from config import (
    BOT_TOKEN,
    AUDIO_DIR,
    TELETHON_API_ID,
    TELETHON_API_HASH,
    TELETHON_PHONE,
    TELETHON_SESSION,
    OWNER_ID  # <-- ДОБАВЛЕНО: импортируем ID владельца
)
from database import init_db
from handlers import router
from telethon_service import init_telethon_service, stop_telethon_service
# --- ИЗМЕНЕНО: теперь используем новый middleware ---
from middlewares import SubscriptionCheckMiddleware
# -----------------------------------------------

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('bot.log', encoding='utf-8')
    ]
)

logger = logging.getLogger(__name__)

# Уменьшаем уровень логирования для aiogram
logging.getLogger("aiogram.event").setLevel(logging.WARNING)
logging.getLogger("aiogram.dispatcher").setLevel(logging.WARNING)
logging.getLogger("telethon").setLevel(logging.WARNING)

if sys.version_info >= (3, 13):
    logger.info("✓ Принудительно установлен стандартный asyncio для Python 3.13+")


# --- НОВЫЙ БЛОК: Функция для установки команд меню ---
async def set_bot_commands(bot: Bot):
    """Устанавливает команды в меню бота для разных типов пользователей."""

    # Команды для обычных пользователей
    user_commands = [
        BotCommand(command="menu", description="🎛 Главное меню"),
        BotCommand(command="help", description="📖 Помощь"),
        BotCommand(command="stats", description="📊 Статистика"),
    ]
    await bot.set_my_commands(user_commands, scope=BotCommandScopeDefault())
    logger.info("✓ Установлены команды для обычных пользователей.")

    # Добавляем команды для владельца бота
    owner_commands = user_commands + [
        BotCommand(command="add_chat", description="💬 Добавить чат (админ)"),
        BotCommand(command="my_chats", description="📜 Мои чаты (админ)"),
    ]
    await bot.set_my_commands(owner_commands, scope=BotCommandScopeChat(chat_id=OWNER_ID))
    logger.info(f"✓ Установлены расширенные команды для владельца (ID: {OWNER_ID}).")

# ---------------------------------------------------


async def on_startup(dispatcher: Dispatcher, bot: Bot):
    """Выполняется при старте бота"""
    # Создаем директорию для аудио
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    logger.info(f"✓ Директория для аудио: {AUDIO_DIR}")

    # Инициализируем базу данных
    await init_db()

    # --- ДОБАВЛЕНО: Устанавливаем команды меню ---
    await set_bot_commands(bot)
    # ------------------------------------------

    # Инициализируем Telethon сервис
    if TELETHON_API_ID and TELETHON_API_ID != 0:
        try:
            await init_telethon_service(
                session_string=TELETHON_SESSION,
                api_id=TELETHON_API_ID,
                api_hash=TELETHON_API_HASH,
                phone=TELETHON_PHONE
            )
            logger.info("✓ Telethon сервис инициализирован")
        except Exception as e:
            logger.error(f"✗ Ошибка Telethon: {e}")
            logger.warning("Функции работы с каналами и чатами будут недоступны!")
    else:
        logger.warning("TELETHON_API_ID не установлен. Получите его на https://my.telegram.org")
        logger.warning("Функции работы с каналами и чатами будут недоступны!")


async def on_shutdown(dispatcher: Dispatcher, bot: Bot):
    """Выполняется при остановке бота"""
    await stop_telethon_service()
    logger.info("✓ Бот остановлен")


async def main():
    """Главная функция запуска бота"""

    # Workaround для Python 3.13 + OpenSSL 3.6: используем legacy SSL с минимальными проверками
    ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    # Разрешаем все версии TLS, включая старые
    ssl_context.minimum_version = ssl.TLSVersion.TLSv1
    ssl_context.maximum_version = ssl.TLSVersion.TLSv1_3

    # Создаем connector с legacy SSL
    connector = aiohttp.TCPConnector(
        ssl=ssl_context,
        limit=100,
        ttl_dns_cache=300,
        force_close=False,
        enable_cleanup_closed=True
    )

    # Глобально патчим создание SSL context в aiohttp
    # Это самый радикальный но рабочий способ для Python 3.13
    original_create_default_context = ssl.create_default_context

    def patched_create_default_context(*args, **kwargs):
        context = original_create_default_context(*args, **kwargs)
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        try:
            context.minimum_version = ssl.TLSVersion.TLSv1
        except:
            pass
        return context

    ssl.create_default_context = patched_create_default_context

    # Создаем бота - он будет использовать пропатченный SSL
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )

    logger.info("✓ SSL глобально пропатчен (workaround для Python 3.13)")

    # Создаем Dispatcher с FSM storage
    dp = Dispatcher(storage=MemoryStorage())

    # Регистрируем middleware для проверки подписки
    subscription_middleware = SubscriptionCheckMiddleware()
    dp.message.middleware(subscription_middleware)
    dp.callback_query.middleware(subscription_middleware)

    # Регистрируем роутер с обработчиками
    dp.include_router(router)

    # ВАЖНО: Регистрируем lifecycle hooks
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    logger.info("✓ Бот запущен и готов к работе!")

    try:
        # Пытаемся удалить webhook (может зависнуть из-за SSL в Python 3.13)
        try:
            await bot.delete_webhook(drop_pending_updates=True)
            logger.info("✓ Webhook удален")
        except Exception as e:
            logger.warning(f"Не удалось удалить webhook (пропускаем): {e}")

        # Запускаем polling
        await dp.start_polling(bot, polling_timeout=20, handle_signals=True)
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"✗ Ошибка при работе бота: {e}")
        raise


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем")
