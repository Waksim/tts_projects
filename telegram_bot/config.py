"""
Конфигурация Telegram Bot
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Загружаем переменные окружения из .env файла
load_dotenv()

# Telegram Bot Token
BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN_HERE")

# Прокси (если Telegram заблокирован в вашей стране)
# Раскомментируйте и настройте если нужно:
# PROXY = "http://proxy-server:port"
# PROXY = "socks5://proxy-server:port"
PROXY = os.getenv("PROXY", None)

# Telethon User API credentials
# Получите API ID и API Hash на https://my.telegram.org
# Установите значения в .env файле
TELETHON_API_ID = int(os.getenv("TELETHON_API_ID", "0"))
TELETHON_API_HASH = os.getenv("TELETHON_API_HASH", "")
TELETHON_PHONE = os.getenv("TELETHON_PHONE", "")
TELETHON_SESSION = os.getenv("TELETHON_SESSION", "")

# ID владельца бота (для доступа к приватным функциям)
OWNER_ID = 382202500

# Обязательный канал для доступа к боту
REQUIRED_CHANNEL_USERNAME = "svalka_mk"
REQUIRED_CHANNEL_ID = -1001510749345

# Директории
BASE_DIR = Path(__file__).parent
AUDIO_DIR = BASE_DIR / "audio"
DB_PATH = BASE_DIR / "bot_history.db"

# TTS настройки
TTS_VOICE = "ru-RU-DmitryNeural"
TTS_RATE = "+50%"
TTS_PITCH = "+0Hz"

# Доступные голоса для выбора пользователем
AVAILABLE_VOICES = {
    "ru-RU-DmitryNeural": {
        "name": "👨 Дмитрий (мужской)",
        "styles": None
    },
    "ru-RU-SvetlanaNeural": {
        "name": "👩 Светлана (женский)",
        "styles": None
    },
    "ru-RU-DariyaNeural": {
        "name": "👩 Дария (женский)",
        "styles": ["crisp", "bright", "clear"]
    }
}

# Русские названия стилей для голоса Дарии
VOICE_STYLES = {
    "crisp": "🎯 Четкий",
    "bright": "✨ Яркий",
    "clear": "💎 Чистый"
}

# Хранилище
MAX_STORAGE_MB = 500

# Лимиты
MAX_TEXT_LENGTH = 50000  # Максимальная длина текста для озвучки
MAX_FILE_SIZE_MB = 20    # Максимальный размер загружаемого файла

# Сообщения
WELCOME_MESSAGE = """
👋 Привет! Я бот для озвучивания текста.

Я могу:
📝 Озвучить текст, который вы мне отправите
📄 Извлечь текст из документов (txt, docx, pdf, md, rtf, epub, fb2) и озвучить
🌐 Извлечь текст из веб-страницы по ссылке и озвучить

Просто отправьте мне текст, документ или ссылку!

⚙️ Голос: {voice}
⚡ Скорость: {rate}
""".format(voice=TTS_VOICE, rate=TTS_RATE)

PROCESSING_MESSAGE = "⏳ Обрабатываю... Это может занять некоторое время."
