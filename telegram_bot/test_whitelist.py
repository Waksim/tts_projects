"""
Тестовый скрипт для проверки функционала белого списка
"""

import asyncio
import sys
from pathlib import Path

# Добавляем путь к tts_common
sys.path.insert(0, str(Path(__file__).parent.parent))

from database import (
    init_db,
    add_whitelisted_user,
    is_user_whitelisted,
    get_all_whitelisted_users,
    remove_whitelisted_user
)


async def test_whitelist():
    """Тестирование функционала белого списка"""

    print("=" * 50)
    print("Тестирование функционала белого списка")
    print("=" * 50)

    # Инициализируем БД
    await init_db()
    print("✓ База данных инициализирована")

    # Тестовые данные
    test_user_id = 511772312
    test_username = "XDmarina"
    test_first_name = "Марина"
    admin_id = 382202500

    # Проверяем, что пользователя нет в списке
    is_whitelisted = await is_user_whitelisted(test_user_id)
    print(f"\n1. Пользователь {test_user_id} в белом списке: {is_whitelisted}")

    # Добавляем пользователя
    print(f"\n2. Добавляю пользователя {test_username}...")
    await add_whitelisted_user(
        user_id=test_user_id,
        added_by=admin_id,
        username=test_username,
        first_name=test_first_name
    )
    print("✓ Пользователь добавлен")

    # Проверяем снова
    is_whitelisted = await is_user_whitelisted(test_user_id)
    print(f"\n3. Пользователь {test_user_id} в белом списке: {is_whitelisted}")

    # Получаем список всех пользователей
    print("\n4. Список всех пользователей в белом списке:")
    users = await get_all_whitelisted_users()
    for user in users:
        print(f"   - ID: {user.user_id}, @{user.username}, {user.first_name}")

    # Удаляем пользователя
    print(f"\n5. Удаляю пользователя {test_user_id}...")
    was_removed = await remove_whitelisted_user(str(test_user_id))
    print(f"✓ Пользователь удален: {was_removed}")

    # Проверяем финальное состояние
    is_whitelisted = await is_user_whitelisted(test_user_id)
    print(f"\n6. Пользователь {test_user_id} в белом списке: {is_whitelisted}")

    print("\n" + "=" * 50)
    print("Тест завершен успешно!")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(test_whitelist())
