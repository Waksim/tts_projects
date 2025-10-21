"""
Скрипт для исправления существующих записей в таблице user_settings.
Устанавливает дефолтные значения для полей, которые могут быть NULL.

Запускать на сервере после деплоя:
python fix_user_settings.py
"""

import sqlite3
import sys
from pathlib import Path

# Путь к базе данных
DB_PATH = Path(__file__).parent / "bot_history.db"

# Дефолтные значения из config.py
DEFAULT_VOICE = "ru-RU-DmitryNeural"
DEFAULT_RATE = "+50%"


def fix_user_settings():
    """Обновляет записи user_settings, устанавливая дефолтные значения для NULL полей."""
    if not DB_PATH.exists():
        print(f"❌ База данных не найдена по пути: {DB_PATH}")
        print("Создайте базу данных сначала, запустив бота.")
        sys.exit(1)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # Проверяем, существует ли таблица user_settings
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='user_settings'")
        if not cursor.fetchone():
            print("ℹ️  Таблица user_settings не существует. Скрипт не требуется.")
            return

        # Подсчитываем количество записей с NULL значениями
        cursor.execute("""
            SELECT COUNT(*) FROM user_settings
            WHERE speech_rate IS NULL OR speech_rate = '' OR voice_name IS NULL OR voice_name = ''
        """)
        count_to_fix = cursor.fetchone()[0]

        if count_to_fix == 0:
            print("✅ Все записи в user_settings имеют корректные значения. Исправление не требуется.")
            return

        print(f"🔧 Найдено {count_to_fix} записей с NULL значениями. Начинаю исправление...")

        # Обновляем speech_rate для записей где он NULL или пустая строка
        cursor.execute("""
            UPDATE user_settings
            SET speech_rate = ?
            WHERE speech_rate IS NULL OR speech_rate = ''
        """, (DEFAULT_RATE,))
        updated_rate = cursor.rowcount
        print(f"   Обновлено speech_rate: {updated_rate} записей")

        # Обновляем voice_name для записей где он NULL или пустая строка
        cursor.execute("""
            UPDATE user_settings
            SET voice_name = ?
            WHERE voice_name IS NULL OR voice_name = ''
        """, (DEFAULT_VOICE,))
        updated_voice = cursor.rowcount
        print(f"   Обновлено voice_name: {updated_voice} записей")

        conn.commit()
        print("✅ Исправление завершено успешно!")
        print(f"   Всего обработано записей: {max(updated_rate, updated_voice)}")

        # Показываем статистику
        cursor.execute("SELECT COUNT(*) FROM user_settings")
        total_records = cursor.fetchone()[0]
        print(f"\n📊 Статистика user_settings:")
        print(f"   Всего записей: {total_records}")

        cursor.execute("SELECT COUNT(*) FROM user_settings WHERE speech_rate = ?", (DEFAULT_RATE,))
        default_rate_count = cursor.fetchone()[0]
        print(f"   Записей с дефолтной скоростью ({DEFAULT_RATE}): {default_rate_count}")

        cursor.execute("SELECT COUNT(*) FROM user_settings WHERE voice_name = ?", (DEFAULT_VOICE,))
        default_voice_count = cursor.fetchone()[0]
        print(f"   Записей с дефолтным голосом ({DEFAULT_VOICE}): {default_voice_count}")

    except Exception as e:
        conn.rollback()
        print(f"❌ Ошибка при исправлении записей: {e}")
        sys.exit(1)
    finally:
        conn.close()


if __name__ == "__main__":
    print("🔧 Запуск скрипта исправления user_settings...\n")
    fix_user_settings()
