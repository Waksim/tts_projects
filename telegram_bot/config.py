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
        "name": "👨 Дмитрий (мужской)"
    },
    "ru-RU-SvetlanaNeural": {
        "name": "👩 Светлана (женский)"
    },
    "ru-RU-DariyaNeural": {
        "name": "👩 Дария (женский)"
    }
}

# Доступные варианты скорости речи
AVAILABLE_RATES = {
    "-50%": "🐌 Очень медленно (-50%)",
    "-25%": "🐢 Медленно (-25%)",
    "+0%": "⚡ Нормально (+0%)",
    "+25%": "🚀 Быстро (+25%)",
    "+50%": "⚡⚡ Очень быстро (+50%)",
    "+75%": "🏎 Супер быстро (+75%)",
    "+100%": "🚄 Максимально (+100%)"
}

# Доступные варианты максимальной длительности аудио (в минутах)
AVAILABLE_DURATIONS = {
    15: "⏱ 15 минут",
    30: "⏱ 30 минут",
    60: "⏱ 1 час",
    120: "⏱ 2 часа",
    180: "⏱ 3 часа",
    360: "⏱ 6 часов",
    None: "♾️ Без лимита"
}

# Длительность по умолчанию (None = без лимита)
DEFAULT_MAX_DURATION_MINUTES = None

# Хранилище
MAX_STORAGE_MB = 500

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
