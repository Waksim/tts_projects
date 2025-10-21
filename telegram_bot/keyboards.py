"""
Клавиатуры для Telegram Bot
"""

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import OWNER_ID


def get_main_menu_keyboard(user_id: int) -> InlineKeyboardMarkup:
    """
    Создает главное меню с inline кнопками.

    Args:
        user_id: ID пользователя (для проверки прав доступа)

    Returns:
        InlineKeyboardMarkup с кнопками главного меню
    """
    keyboard = []

    # Кнопки для каналов (доступны всем)
    keyboard.append([
        InlineKeyboardButton(text="➕ Добавить канал", callback_data="add_channel"),
        InlineKeyboardButton(text="📢 Мои каналы", callback_data="my_channels")
    ])

    keyboard.append([
        InlineKeyboardButton(text="🔊 Озвучить новые посты", callback_data="voice_new")
    ])

    # Кнопки для чатов (только для владельца)
    if user_id == OWNER_ID:
        keyboard.append([
            InlineKeyboardButton(text="➕ Добавить чат", callback_data="add_chat"),
            InlineKeyboardButton(text="💬 Мои чаты", callback_data="my_chats")
        ])

    # Кнопка выбора голоса
    keyboard.append([
        InlineKeyboardButton(text="🎤 Выбор голоса", callback_data="select_voice")
    ])

    keyboard.append([
        InlineKeyboardButton(text="📊 Статистика", callback_data="stats"),
        InlineKeyboardButton(text="❓ Помощь", callback_data="help")
    ])

    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_back_button_keyboard() -> InlineKeyboardMarkup:
    """
    Создает клавиатуру только с кнопкой "Назад".

    Returns:
        InlineKeyboardMarkup с кнопкой "Назад"
    """
    keyboard = [[InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_main")]]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_posts_count_keyboard(channel_username: str) -> InlineKeyboardMarkup:
    """
    Создает клавиатуру для выбора количества постов.

    Args:
        channel_username: Username канала

    Returns:
        InlineKeyboardMarkup с кнопками выбора количества
    """
    counts = [1, 2, 5, 10, 30]

    keyboard = []

    # Первая строка с числами
    row = []
    for count in counts:
        row.append(InlineKeyboardButton(
            text=str(count),
            callback_data=f"voice_channel:{channel_username}:{count}"
        ))
    keyboard.append(row)

    # Кнопка "Назад"
    keyboard.append([InlineKeyboardButton(text="◀️ Назад", callback_data="my_channels")])

    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_my_channels_keyboard(channels: list) -> InlineKeyboardMarkup:
    """
    Создает клавиатуру со списком каналов.

    Args:
        channels: Список объектов каналов из БД

    Returns:
        InlineKeyboardMarkup с кнопками каналов
    """
    keyboard = []

    # Кнопки для каждого канала
    for channel in channels:
        keyboard.append([
            InlineKeyboardButton(
                text=f"📢 {channel.channel_title}",
                callback_data=f"channel:{channel.channel_username}"
            )
        ])

    # Кнопка "Назад"
    keyboard.append([InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_main")])

    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_messages_count_keyboard(chat_id: int) -> InlineKeyboardMarkup:
    """
    Создает клавиатуру для выбора количества сообщений чата.

    Args:
        chat_id: ID чата

    Returns:
        InlineKeyboardMarkup с кнопками выбора количества
    """
    counts = [1, 2, 5, 10, 30]

    keyboard = []

    # Первая строка с числами
    row = []
    for count in counts:
        row.append(InlineKeyboardButton(
            text=str(count),
            callback_data=f"voice_chat:{chat_id}:{count}"
        ))
    keyboard.append(row)

    # Кнопка "Назад"
    keyboard.append([InlineKeyboardButton(text="◀️ Назад", callback_data="my_chats")])

    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_my_chats_keyboard(chats: list) -> InlineKeyboardMarkup:
    """
    Создает клавиатуру со списком чатов.

    Args:
        chats: Список объектов чатов из БД

    Returns:
        InlineKeyboardMarkup с кнопками чатов
    """
    keyboard = []

    # Кнопки для каждого чата
    for chat in chats:
        keyboard.append([
            InlineKeyboardButton(
                text=f"💬 {chat.chat_title}",
                callback_data=f"chat:{chat.chat_id}"
            )
        ])

    # Кнопка "Назад"
    keyboard.append([InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_main")])

    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_voice_selection_keyboard() -> InlineKeyboardMarkup:
    """
    Создает клавиатуру для выбора голоса.

    Returns:
        InlineKeyboardMarkup с кнопками выбора голосов
    """
    from config import AVAILABLE_VOICES

    keyboard = []

    # Кнопки для каждого голоса
    for voice_id, voice_info in AVAILABLE_VOICES.items():
        keyboard.append([
            InlineKeyboardButton(
                text=voice_info["name"],
                callback_data=f"set_voice:{voice_id}"
            )
        ])

    # Кнопка "Назад"
    keyboard.append([InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_main")])

    return InlineKeyboardMarkup(inline_keyboard=keyboard)


