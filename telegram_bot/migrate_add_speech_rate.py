"""
Миграция для добавления колонки speech_rate в таблицу user_settings.
Запускать один раз: python migrate_add_speech_rate.py
"""

import sqlite3
import sys
from pathlib import Path

# Путь к базе данных
DB_PATH = Path(__file__).parent / "bot_history.db"


def migrate():
    """Добавляет колонку speech_rate в таблицу user_settings."""
    if not DB_PATH.exists():
        print(f"❌ База данных не найдена по пути: {DB_PATH}")
        print("Создайте базу данных сначала, запустив бота.")
        sys.exit(1)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # Проверяем, существует ли колонка
        cursor.execute("PRAGMA table_info(user_settings)")
        columns = [column[1] for column in cursor.fetchall()]

        if 'speech_rate' in columns:
            print("✅ Колонка 'speech_rate' уже существует, миграция не требуется.")
            return

        # Добавляем колонку с дефолтным значением +50%
        print("Добавляю колонку 'speech_rate'...")
        cursor.execute("""
            ALTER TABLE user_settings
            ADD COLUMN speech_rate VARCHAR(10) NOT NULL DEFAULT '+50%'
        """)

        conn.commit()
        print("✅ Миграция выполнена успешно!")
        print("   Колонка 'speech_rate' добавлена со значением по умолчанию '+50%'")

    except Exception as e:
        conn.rollback()
        print(f"❌ Ошибка при выполнении миграции: {e}")
        sys.exit(1)
    finally:
        conn.close()


if __name__ == "__main__":
    print("🔧 Запуск миграции для добавления колонки speech_rate...")
    migrate()
