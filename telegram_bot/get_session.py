"""
Скрипт для получения Session String для Telethon.
ВАЖНО: После получения session string удалите этот файл!
"""

from telethon.sync import TelegramClient
from telethon.sessions import StringSession

# НАСТРОЙТЕ ЭТИ ПАРАМЕТРЫ
api_id = 0  # Замените на ваш API ID (получите на https://my.telegram.org)
api_hash = 'YOUR_API_HASH'  # Замените на ваш API Hash
phone = '+79259157352'  # Ваш номер телефона

# Проверка заполнения параметров
if api_id == 0 or api_hash == 'YOUR_API_HASH':
    print("❌ ОШИБКА: Заполните api_id и api_hash в этом скрипте!")
    print("\n1. Перейдите на https://my.telegram.org")
    print("2. Войдите с вашим номером телефона")
    print("3. Выберите 'API development tools'")
    print("4. Создайте приложение и скопируйте api_id и api_hash")
    print("\n5. Отредактируйте этот файл (get_session.py) и замените значения:")
    print(f"   api_id = YOUR_API_ID  # число")
    print(f"   api_hash = 'YOUR_API_HASH'  # строка")
    exit(1)

print("=" * 60)
print("Получение Session String для Telegram")
print("=" * 60)
print(f"API ID: {api_id}")
print(f"Телефон: {phone}")
print("=" * 60)

try:
    with TelegramClient(StringSession(), api_id, api_hash) as client:
        print("\n✅ Авторизация успешна!")
        print("\n" + "=" * 60)
        print("📋 Ваш Session String:")
        print("=" * 60)
        session_string = client.session.save()
        print(session_string)
        print("=" * 60)
        print("\n✅ Скопируйте строку выше и вставьте в config.py:")
        print(f"   TELETHON_SESSION = \"{session_string}\"")
        print("\n⚠️  ВАЖНО: После копирования удалите этот файл get_session.py!")
        print("=" * 60)

except Exception as e:
    print(f"\n❌ Ошибка: {e}")
    print("\nВозможные причины:")
    print("1. Неверный api_id или api_hash")
    print("2. Проблемы с интернет-соединением")
    print("3. Неверный номер телефона")
