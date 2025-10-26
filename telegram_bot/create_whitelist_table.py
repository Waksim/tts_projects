"""
Скрипт для создания таблицы whitelisted_users в базе данных
"""

import sqlite3
from pathlib import Path

# Путь к базе данных
DB_PATH = Path(__file__).parent / "bot_history.db"

# SQL для создания таблицы
CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS whitelisted_users (
    id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
    user_id BIGINT NOT NULL UNIQUE,
    username VARCHAR(255),
    first_name VARCHAR(255),
    last_name VARCHAR(255),
    added_by BIGINT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_whitelisted_users_user_id ON whitelisted_users (user_id);
CREATE INDEX IF NOT EXISTS ix_whitelisted_users_created_at ON whitelisted_users (created_at);
"""

def main():
    print("=" * 60)
    print("Создание таблицы whitelisted_users")
    print("=" * 60)

    # Подключаемся к базе данных
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Выполняем SQL
    cursor.executescript(CREATE_TABLE_SQL)
    conn.commit()

    # Проверяем, что таблица создана
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='whitelisted_users'")
    result = cursor.fetchone()

    if result:
        print("✓ Таблица whitelisted_users успешно создана!")

        # Показываем структуру таблицы
        cursor.execute("PRAGMA table_info(whitelisted_users)")
        columns = cursor.fetchall()

        print("\nСтруктура таблицы:")
        for col in columns:
            print(f"  - {col[1]} ({col[2]})")
    else:
        print("✗ Ошибка при создании таблицы")

    conn.close()
    print("\n" + "=" * 60)

if __name__ == "__main__":
    main()
