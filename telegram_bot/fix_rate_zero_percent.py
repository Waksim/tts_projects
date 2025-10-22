"""
Скрипт для исправления значений '0%' на '+0%' в таблице user_settings.
Edge TTS API не принимает '0%', только '+0%'.

Запускать на сервере после деплоя:
python fix_rate_zero_percent.py
"""

import sqlite3
import sys
from pathlib import Path

# Путь к базе данных
DB_PATH = Path(__file__).parent / "bot_history.db"


def fix_zero_percent_rate():
    """Обновляет записи user_settings, заменяя '0%' на '+0%'."""
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

        # Подсчитываем количество записей с '0%'
        cursor.execute("""
            SELECT COUNT(*) FROM user_settings
            WHERE speech_rate = '0%'
        """)
        count_to_fix = cursor.fetchone()[0]

        if count_to_fix == 0:
            print("✅ Нет записей с некорректным значением '0%'. Исправление не требуется.")
            return

        print(f"🔧 Найдено {count_to_fix} записей со значением '0%'. Начинаю исправление...")

        # Обновляем '0%' на '+0%'
        cursor.execute("""
            UPDATE user_settings
            SET speech_rate = '+0%'
            WHERE speech_rate = '0%'
        """)
        updated_count = cursor.rowcount
        print(f"   Обновлено записей: {updated_count}")

        conn.commit()
        print("✅ Исправление завершено успешно!")

        # Показываем статистику
        cursor.execute("SELECT COUNT(*) FROM user_settings WHERE speech_rate = '+0%'")
        new_count = cursor.fetchone()[0]
        print(f"\n📊 Статистика:")
        print(f"   Записей с корректным значением '+0%': {new_count}")

    except Exception as e:
        conn.rollback()
        print(f"❌ Ошибка при исправлении записей: {e}")
        sys.exit(1)
    finally:
        conn.close()


if __name__ == "__main__":
    print("🔧 Запуск скрипта исправления '0%' -> '+0%'...\n")
    fix_zero_percent_rate()
