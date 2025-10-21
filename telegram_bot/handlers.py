"""
Обработчики команд и сообщений Telegram Bot
"""

import os
import sys
import asyncio
import logging
from pathlib import Path

from aiogram import Router, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    Message,
    FSInputFile,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery
)
from aiogram.enums import ChatAction
import re

# Логгер для handlers
logger = logging.getLogger(__name__)

# Добавляем путь к tts_common
sys.path.insert(0, str(Path(__file__).parent.parent))

from tts_common import (
    synthesize_text,
    parse_document,
    parse_url,
    is_valid_url,
    StorageManager,
    sanitize_filename,
    generate_filename_from_text
)
from tts_common.document_parser import SUPPORTED_EXTENSIONS

from config import (
    WELCOME_MESSAGE,
    PROCESSING_MESSAGE,
    AUDIO_DIR,
    TTS_VOICE,
    TTS_RATE,
    TTS_PITCH,
    MAX_TEXT_LENGTH,
    MAX_FILE_SIZE_MB,
    MAX_STORAGE_MB,
    OWNER_ID
)
from database import (
    save_request,
    add_tracked_channel,
    add_tracked_chat,
    get_tracked_channels,
    get_tracked_chats,
    save_voiced_message,
    get_last_voiced_message_id
)
from telethon_service import get_telethon_service

# Создаем роутер
router = Router()

# Инициализируем менеджер хранилища
storage_manager = StorageManager(str(AUDIO_DIR), MAX_STORAGE_MB)


# FSM States для диалогов
class AddChannelStates(StatesGroup):
    waiting_for_username = State()
    waiting_for_count = State()


class AddChatStates(StatesGroup):
    waiting_for_identifier = State()
    waiting_for_count = State()


@router.message(Command("start"))
async def cmd_start(message: Message):
    """Обработчик команды /start"""
    await message.answer(WELCOME_MESSAGE)
    # Показываем главное меню
    await show_main_menu(message)


@router.message(Command("menu"))
async def cmd_menu(message: Message):
    """Обработчик команды /menu - показывает главное меню"""
    await show_main_menu(message)


async def show_main_menu(message: Message):
    """Показывает главное меню с inline кнопками"""
    user_id = message.from_user.id

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
    if is_owner(user_id):
        keyboard.append([
            InlineKeyboardButton(text="➕ Добавить чат", callback_data="add_chat"),
            InlineKeyboardButton(text="💬 Мои чаты", callback_data="my_chats")
        ])

    keyboard.append([
        InlineKeyboardButton(text="📊 Статистика", callback_data="stats"),
        InlineKeyboardButton(text="❓ Помощь", callback_data="help")
    ])

    markup = InlineKeyboardMarkup(inline_keyboard=keyboard)

    await message.answer(
        "🎛 <b>Главное меню</b>\n\nВыберите действие:",
        reply_markup=markup,
        parse_mode="HTML"
    )


@router.message(Command("help"))
async def cmd_help(message: Message):
    """Обработчик команды /help"""
    user_id = message.from_user.id

    help_text = f"""
📖 <b>Помощь по использованию бота</b>

<b>Основные команды:</b>
/start - Начать работу с ботом
/help - Показать эту справку
/stats - Статистика хранилища

<b>Работа с каналами:</b>
/add_channel @username N - Добавить канал и озвучить последние N постов
/my_channels - Список отслеживаемых каналов
/voice_new - Озвучить новые посты из всех каналов
"""

    if is_owner(user_id):
        help_text += """
<b>Работа с чатами (только для владельца):</b>
/add_chat @username N - Добавить чат и озвучить последние N сообщений
/add_chat ID N - Добавить чат по ID
/my_chats - Список отслеживаемых чатов
"""

    help_text += f"""
<b>Поддерживаемые форматы документов:</b>
{', '.join(SUPPORTED_EXTENSIONS)}

<b>Способы озвучки:</b>
1️⃣ <b>Текст</b> - просто отправьте текст (до {MAX_TEXT_LENGTH} символов)
2️⃣ <b>Документ</b> - отправьте файл (до {MAX_FILE_SIZE_MB} MB)
3️⃣ <b>Ссылка</b> - отправьте URL веб-страницы
4️⃣ <b>Пересланное сообщение</b> - перешлите пост с любого канала

<b>Настройки TTS:</b>
🎤 Голос: {TTS_VOICE}
⚡ Скорость: {TTS_RATE}
🎵 Высота: {TTS_PITCH}

💾 Хранилище: {MAX_STORAGE_MB} MB (старые файлы удаляются автоматически)
"""
    await message.answer(help_text, parse_mode="HTML")


@router.message(Command("stats"))
async def cmd_stats(message: Message):
    """Обработчик команды /stats - показывает статистику хранилища"""
    stats = storage_manager.get_storage_stats()

    stats_text = f"""
📊 <b>Статистика хранилища</b>

💾 Использовано: {stats['total_size_mb']:.2f} MB / {stats['max_size_mb']:.0f} MB
📈 Заполнено: {stats['used_percent']:.1f}%
📁 Файлов: {stats['file_count']}
✅ Свободно: {stats['available_mb']:.2f} MB
"""
    await message.answer(stats_text, parse_mode="HTML")


@router.message(F.document)
async def handle_document(message: Message):
    """Обработчик документов"""
    document = message.document
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name

    # Проверяем размер файла
    file_size_mb = document.file_size / 1024 / 1024
    if file_size_mb > MAX_FILE_SIZE_MB:
        await message.answer(
            f"❌ Файл слишком большой ({file_size_mb:.1f} MB). "
            f"Максимальный размер: {MAX_FILE_SIZE_MB} MB"
        )
        return

    # Проверяем расширение файла
    file_name = document.file_name
    file_ext = os.path.splitext(file_name)[1].lower()

    if file_ext not in SUPPORTED_EXTENSIONS:
        await message.answer(
            f"❌ Формат файла '{file_ext}' не поддерживается.\n"
            f"Поддерживаемые форматы: {', '.join(SUPPORTED_EXTENSIONS)}"
        )
        return

    # Отправляем сообщение о начале обработки
    processing_msg = await message.answer(PROCESSING_MESSAGE)

    try:
        # Показываем статус "печатает"
        await message.bot.send_chat_action(message.chat.id, ChatAction.TYPING)

        # Скачиваем файл
        file = await message.bot.get_file(document.file_id)
        temp_file_path = AUDIO_DIR / f"temp_{user_id}_{document.file_id}{file_ext}"

        await message.bot.download_file(file.file_path, temp_file_path)

        # Извлекаем текст
        await processing_msg.edit_text("📄 Извлекаю текст из документа...")
        text = parse_document(str(temp_file_path))

        # Удаляем временный файл
        os.remove(temp_file_path)

        # Проверяем длину текста
        if len(text) > MAX_TEXT_LENGTH:
            await processing_msg.edit_text(
                f"❌ Текст слишком длинный ({len(text)} символов). "
                f"Максимум: {MAX_TEXT_LENGTH} символов"
            )
            return

        # Синтезируем аудио
        await processing_msg.edit_text("🎤 Синтезирую речь...")
        await message.bot.send_chat_action(message.chat.id, ChatAction.RECORD_VOICE)

        # Генерируем имя файла из первых 7 слов текста
        audio_filename = generate_filename_from_text(text, user_id)
        audio_path = AUDIO_DIR / audio_filename

        # Проверяем и освобождаем место
        estimated_size = len(text) * 300  # Примерная оценка размера файла
        await storage_manager.ensure_space_available_async(estimated_size)

        # Синтезируем
        success = await synthesize_text(
            text,
            str(audio_path),
            voice=TTS_VOICE,
            rate=TTS_RATE,
            pitch=TTS_PITCH
        )

        if not success:
            raise Exception("Не удалось синтезировать аудио")

        # Отправляем аудио пользователю
        await processing_msg.edit_text("📤 Отправляю аудио...")
        audio_file = FSInputFile(str(audio_path))
        await message.answer_audio(
            audio_file,
            title=file_name,
            performer="TTS Bot"
        )

        # Удаляем сообщение о обработке
        await processing_msg.delete()

        # Сохраняем в БД
        await save_request(
            user_id=user_id,
            username=username,
            request_type='document',
            content=file_name,
            audio_path=str(audio_path),
            status='success'
        )

    except Exception as e:
        error_msg = f"❌ Ошибка при обработке документа: {str(e)}"
        await processing_msg.edit_text(error_msg)

        # Сохраняем ошибку в БД
        await save_request(
            user_id=user_id,
            username=username,
            request_type='document',
            content=file_name,
            status='error',
            error_message=str(e)
        )

        # Удаляем временные файлы
        if temp_file_path.exists():
            os.remove(temp_file_path)


@router.message(F.text, StateFilter(None))
async def handle_text(message: Message):
    """Обработчик текстовых сообщений (текст или URL)"""
    text = message.text.strip()
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name

    # Пропускаем команды
    if text.startswith('/'):
        return

    # Проверяем, является ли текст URL
    if is_valid_url(text):
        await handle_url(message, text, user_id, username)
    else:
        await handle_plain_text(message, text, user_id, username)


async def handle_url(message: Message, url: str, user_id: int, username: str):
    """Обработчик URL"""
    processing_msg = await message.answer(PROCESSING_MESSAGE)

    try:
        await message.bot.send_chat_action(message.chat.id, ChatAction.TYPING)

        # Извлекаем текст с веб-страницы
        await processing_msg.edit_text("🌐 Загружаю страницу...")

        from tts_common.web_parser import parse_url_async
        text = await parse_url_async(url)

        # Проверяем длину текста
        if len(text) > MAX_TEXT_LENGTH:
            await processing_msg.edit_text(
                f"❌ Текст слишком длинный ({len(text)} символов). "
                f"Максимум: {MAX_TEXT_LENGTH} символов"
            )
            return

        # Синтезируем аудио
        await processing_msg.edit_text("🎤 Синтезирую речь...")
        await message.bot.send_chat_action(message.chat.id, ChatAction.RECORD_VOICE)

        # Генерируем имя файла из первых 7 слов извлеченного текста
        audio_filename = generate_filename_from_text(text, user_id)
        audio_path = AUDIO_DIR / audio_filename

        # Проверяем и освобождаем место
        estimated_size = len(text) * 300
        await storage_manager.ensure_space_available_async(estimated_size)

        # Синтезируем
        success = await synthesize_text(
            text,
            str(audio_path),
            voice=TTS_VOICE,
            rate=TTS_RATE,
            pitch=TTS_PITCH
        )

        if not success:
            raise Exception("Не удалось синтезировать аудио")

        # Отправляем аудио
        await processing_msg.edit_text("📤 Отправляю аудио...")
        audio_file = FSInputFile(str(audio_path))
        await message.answer_audio(
            audio_file,
            title="Web Article",
            performer="TTS Bot"
        )

        await processing_msg.delete()

        # Сохраняем в БД
        await save_request(
            user_id=user_id,
            username=username,
            request_type='url',
            content=url,
            audio_path=str(audio_path),
            status='success'
        )

    except Exception as e:
        error_msg = f"❌ Ошибка при обработке URL: {str(e)}"
        await processing_msg.edit_text(error_msg)

        await save_request(
            user_id=user_id,
            username=username,
            request_type='url',
            content=url,
            status='error',
            error_message=str(e)
        )


async def handle_plain_text(message: Message, text: str, user_id: int, username: str):
    """Обработчик обычного текста"""

    # Проверяем длину текста
    if len(text) > MAX_TEXT_LENGTH:
        await message.answer(
            f"❌ Текст слишком длинный ({len(text)} символов). "
            f"Максимум: {MAX_TEXT_LENGTH} символов"
        )
        return

    if len(text) < 10:
        await message.answer("❌ Текст слишком короткий. Минимум 10 символов.")
        return

    processing_msg = await message.answer(PROCESSING_MESSAGE)

    try:
        await message.bot.send_chat_action(message.chat.id, ChatAction.RECORD_VOICE)

        # Синтезируем аудио - используем первые 7 слов для имени файла
        audio_filename = generate_filename_from_text(text, user_id)
        audio_path = AUDIO_DIR / audio_filename

        # Проверяем и освобождаем место
        estimated_size = len(text) * 300
        await storage_manager.ensure_space_available_async(estimated_size)

        # Синтезируем
        success = await synthesize_text(
            text,
            str(audio_path),
            voice=TTS_VOICE,
            rate=TTS_RATE,
            pitch=TTS_PITCH
        )

        if not success:
            raise Exception("Не удалось синтезировать аудио")

        # Отправляем аудио
        audio_file = FSInputFile(str(audio_path))
        await message.answer_audio(
            audio_file,
            title="Text Message",
            performer="TTS Bot"
        )

        # Удаляем сообщение о обработке
        await processing_msg.delete()

        # Сохраняем в БД
        await save_request(
            user_id=user_id,
            username=username,
            request_type='text',
            content=text[:200],  # Сохраняем первые 200 символов
            audio_path=str(audio_path),
            status='success'
        )

    except Exception as e:
        error_msg = f"❌ Ошибка при синтезе речи: {str(e)}"
        await processing_msg.edit_text(error_msg)

        await save_request(
            user_id=user_id,
            username=username,
            request_type='text',
            content=text[:200],
            status='error',
            error_message=str(e)
        )


# ===== НОВЫЕ ОБРАБОТЧИКИ ДЛЯ РАБОТЫ С КАНАЛАМИ И ЧАТАМИ =====


def is_owner(user_id: int) -> bool:
    """Проверяет, является ли пользователь владельцем бота."""
    return user_id == OWNER_ID


@router.message(Command("add_channel"))
async def cmd_add_channel(message: Message):
    """
    Обработчик команды /add_channel.
    Формат: /add_channel @username 10
    """
    user_id = message.from_user.id

    # Парсим команду
    text = message.text.strip()
    parts = text.split()

    if len(parts) < 3:
        await message.answer(
            "❌ Неверный формат команды!\n\n"
            "Используйте: /add_channel @username количество\n"
            "Например: /add_channel @svalka_mk 10"
        )
        return

    channel_username = parts[1]
    try:
        initial_count = int(parts[2])
        if initial_count <= 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ Количество сообщений должно быть положительным числом!")
        return

    processing_msg = await message.answer("⏳ Добавляю канал...")

    try:
        # Получаем сервис Telethon
        telethon = await get_telethon_service()

        # Получаем информацию о канале
        channel_info = await telethon.get_channel_info(channel_username)

        if not channel_info:
            await processing_msg.edit_text(f"❌ Канал {channel_username} не найден!")
            return

        channel_id, channel_title = channel_info

        # Сохраняем в БД
        await add_tracked_channel(
            user_id=user_id,
            channel_username=channel_username.lstrip('@'),
            channel_id=channel_id,
            channel_title=channel_title
        )

        # Получаем и озвучиваем начальные посты
        await processing_msg.edit_text(f"✅ Канал добавлен: {channel_title}\n\n⏳ Озвучиваю последние {initial_count} постов...")

        messages = await telethon.get_channel_messages(channel_username, limit=initial_count)

        if not messages:
            await processing_msg.edit_text(
                f"✅ Канал добавлен: {channel_title}\n\n"
                f"❌ Не найдено сообщений для озвучки."
            )
            return

        await voice_messages(
            message,
            messages,
            user_id,
            source_type='channel',
            source_id=channel_id,
            status_msg=processing_msg
        )

    except Exception as e:
        logger.error(f"Ошибка при добавлении канала: {e}")
        await processing_msg.edit_text(f"❌ Ошибка при добавлении канала: {str(e)}")


@router.message(Command("add_chat"))
async def cmd_add_chat(message: Message):
    """
    Обработчик команды /add_chat (только для владельца).
    Формат: /add_chat @username 10 или /add_chat 123456789 10
    """
    user_id = message.from_user.id

    # Проверяем права доступа
    if not is_owner(user_id):
        await message.answer("❌ Эта команда доступна только владельцу бота!")
        return

    # Парсим команду
    text = message.text.strip()
    parts = text.split()

    if len(parts) < 3:
        await message.answer(
            "❌ Неверный формат команды!\n\n"
            "Используйте: /add_chat @username количество\n"
            "Или: /add_chat ID количество\n"
            "Например: /add_chat @friend 10"
        )
        return

    chat_identifier = parts[1]
    try:
        initial_count = int(parts[2])
        if initial_count <= 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ Количество сообщений должно быть положительным числом!")
        return

    processing_msg = await message.answer("⏳ Добавляю чат...")

    try:
        # Получаем сервис Telethon
        telethon = await get_telethon_service()

        # Получаем информацию о чате
        chat_info = await telethon.get_chat_info(chat_identifier)

        if not chat_info:
            await processing_msg.edit_text(f"❌ Чат {chat_identifier} не найден!")
            return

        chat_id, chat_title, chat_username = chat_info

        # Сохраняем в БД
        await add_tracked_chat(
            user_id=user_id,
            chat_id=chat_id,
            chat_username=chat_username,
            chat_title=chat_title
        )

        # Получаем и озвучиваем начальные сообщения
        await processing_msg.edit_text(f"✅ Чат добавлен: {chat_title}\n\n⏳ Озвучиваю последние {initial_count} сообщений...")

        messages = await telethon.get_chat_messages(chat_id, limit=initial_count)

        if not messages:
            await processing_msg.edit_text(
                f"✅ Чат добавлен: {chat_title}\n\n"
                f"❌ Не найдено сообщений для озвучки."
            )
            return

        await voice_messages(
            message,
            messages,
            user_id,
            source_type='chat',
            source_id=chat_id,
            status_msg=processing_msg
        )

    except Exception as e:
        logger.error(f"Ошибка при добавлении чата: {e}")
        await processing_msg.edit_text(f"❌ Ошибка при добавлении чата: {str(e)}")


@router.message(Command("voice_new"))
async def cmd_voice_new(message: Message):
    """Озвучивает новые посты из всех отслеживаемых каналов."""
    user_id = message.from_user.id

    processing_msg = await message.answer("⏳ Проверяю новые сообщения...")

    try:
        # Получаем сервис Telethon
        telethon = await get_telethon_service()

        # Получаем все отслеживаемые каналы
        channels = await get_tracked_channels(user_id)

        # Получаем все отслеживаемые чаты (только для владельца)
        chats = []
        if is_owner(user_id):
            chats = await get_tracked_chats(user_id)

        if not channels and not chats:
            await processing_msg.edit_text(
                "❌ У вас нет отслеживаемых каналов или чатов!\n\n"
                "Используйте /add_channel для добавления канала."
            )
            return

        total_new_messages = 0

        # Обрабатываем каналы
        for channel in channels:
            last_msg_id = await get_last_voiced_message_id(user_id, 'channel', channel.channel_id)

            messages = await telethon.get_channel_messages(
                channel.channel_username,
                limit=100,  # Максимум 100 новых сообщений за раз
                min_id=last_msg_id
            )

            if messages:
                await processing_msg.edit_text(
                    f"📢 Канал: {channel.channel_title}\n"
                    f"⏳ Озвучиваю {len(messages)} новых сообщений..."
                )

                await voice_messages(
                    message,
                    messages,
                    user_id,
                    source_type='channel',
                    source_id=channel.channel_id,
                    status_msg=None  # Не обновляем статус для каждого канала
                )

                total_new_messages += len(messages)

        # Обрабатываем чаты (только для владельца)
        for chat in chats:
            last_msg_id = await get_last_voiced_message_id(user_id, 'chat', chat.chat_id)

            messages = await telethon.get_chat_messages(
                chat.chat_id,
                limit=100,
                min_id=last_msg_id
            )

            if messages:
                await processing_msg.edit_text(
                    f"💬 Чат: {chat.chat_title}\n"
                    f"⏳ Озвучиваю {len(messages)} новых сообщений..."
                )

                await voice_messages(
                    message,
                    messages,
                    user_id,
                    source_type='chat',
                    source_id=chat.chat_id,
                    status_msg=None
                )

                total_new_messages += len(messages)

        if total_new_messages == 0:
            await processing_msg.edit_text("✅ Нет новых сообщений для озвучки!")
        else:
            await processing_msg.edit_text(f"✅ Озвучено {total_new_messages} новых сообщений!")

    except Exception as e:
        logger.error(f"Ошибка при озвучке новых сообщений: {e}")
        await processing_msg.edit_text(f"❌ Ошибка: {str(e)}")


async def voice_messages(
    message: Message,
    messages: list,
    user_id: int,
    source_type: str,
    source_id: int,
    status_msg: Message = None
):
    """
    Озвучивает список сообщений как единый текст.

    Args:
        message: Исходное сообщение пользователя
        messages: Список кортежей (message_id, message_text)
        user_id: ID пользователя
        source_type: Тип источника ('channel' или 'chat')
        source_id: ID источника
        status_msg: Сообщение для обновления статуса
    """
    if not messages:
        return

    # Фильтруем пустые сообщения и собираем валидные
    valid_messages = []
    for msg_id, text in messages:
        if text and len(text) >= 10:
            valid_messages.append((msg_id, text))

    if not valid_messages:
        if status_msg:
            await status_msg.edit_text("❌ Нет сообщений для озвучки")
        return

    try:
        if status_msg:
            await status_msg.edit_text(f"🎤 Объединяю {len(valid_messages)} сообщений...")

        # Объединяем все сообщения в один текст с разделителем
        combined_text = "\n\n".join([text for _, text in valid_messages])

        # Обрезаем если слишком длинный
        if len(combined_text) > MAX_TEXT_LENGTH:
            combined_text = combined_text[:MAX_TEXT_LENGTH]
            logger.warning(f"Текст обрезан до {MAX_TEXT_LENGTH} символов")

        if status_msg:
            await status_msg.edit_text(f"🎤 Синтезирую {len(combined_text)} символов...")

        # Генерируем имя файла из первого сообщения
        audio_filename = generate_filename_from_text(valid_messages[0][1], user_id)
        audio_path = AUDIO_DIR / audio_filename

        # Проверяем и освобождаем место
        estimated_size = len(combined_text) * 300
        await storage_manager.ensure_space_available_async(estimated_size)

        # Синтезируем объединенный текст
        success = await synthesize_text(
            combined_text,
            str(audio_path),
            voice=TTS_VOICE,
            rate=TTS_RATE,
            pitch=TTS_PITCH
        )

        if not success:
            if status_msg:
                await status_msg.edit_text("❌ Не удалось синтезировать аудио")
            return

        # Отправляем аудио
        if status_msg:
            await status_msg.edit_text("📤 Отправляю аудио...")

        audio_file = FSInputFile(str(audio_path))
        source_name = "Channel" if source_type == "channel" else "Chat"
        await message.answer_audio(
            audio_file,
            title=f"{source_name} ({len(valid_messages)} messages)",
            performer="TTS Bot"
        )

        # Сохраняем в БД информацию о последнем озвученном сообщении
        last_msg_id = valid_messages[-1][0]
        await save_voiced_message(
            user_id=user_id,
            source_type=source_type,
            source_id=source_id,
            message_id=last_msg_id,
            message_text=combined_text[:200],
            audio_path=str(audio_path)
        )

        if status_msg:
            await status_msg.edit_text(f"✅ Озвучено {len(valid_messages)} сообщений!")

    except Exception as e:
        logger.error(f"Ошибка при озвучке сообщений: {e}")
        if status_msg:
            await status_msg.edit_text(f"❌ Ошибка: {str(e)}")


@router.message(Command("my_channels"))
async def cmd_my_channels(message: Message):
    """Показывает список отслеживаемых каналов."""
    user_id = message.from_user.id

    channels = await get_tracked_channels(user_id)

    if not channels:
        await message.answer("У вас нет отслеживаемых каналов.")
        return

    text = "📢 <b>Ваши отслеживаемые каналы:</b>\n\n"
    for channel in channels:
        text += f"• @{channel.channel_username} - {channel.channel_title}\n"

    await message.answer(text, parse_mode="HTML")


@router.message(Command("my_chats"))
async def cmd_my_chats(message: Message):
    """Показывает список отслеживаемых чатов (только для владельца)."""
    user_id = message.from_user.id

    if not is_owner(user_id):
        await message.answer("❌ Эта команда доступна только владельцу бота!")
        return

    chats = await get_tracked_chats(user_id)

    if not chats:
        await message.answer("У вас нет отслеживаемых чатов.")
        return

    text = "💬 <b>Ваши отслеживаемые чаты:</b>\n\n"
    for chat in chats:
        username_text = f"@{chat.chat_username}" if chat.chat_username else f"ID: {chat.chat_id}"
        text += f"• {username_text} - {chat.chat_title}\n"

    await message.answer(text, parse_mode="HTML")


# ===== ОБРАБОТКА ПЕРЕСЛАННЫХ СООБЩЕНИЙ С ИЗОБРАЖЕНИЯМИ =====


@router.message(F.forward_from | F.forward_from_chat)
async def handle_forwarded(message: Message):
    """Обработчик пересланных сообщений."""
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name

    # Извлекаем текст из пересланного сообщения
    text = None

    # Проверяем текст сообщения
    if message.text:
        text = message.text.strip()
    elif message.caption:
        text = message.caption.strip()

    if not text:
        await message.answer("❌ В пересланном сообщении нет текста для озвучки.")
        return

    # Обрабатываем как обычный текст
    await handle_plain_text(message, text, user_id, username)


# ===== CALLBACK HANDLERS ДЛЯ INLINE КНОПОК =====


@router.callback_query(F.data == "help")
async def callback_help(callback: CallbackQuery):
    """Обработчик кнопки Помощь"""
    await callback.answer()

    user_id = callback.from_user.id
    help_text = f"""
📖 <b>Помощь по использованию бота</b>

<b>Основные команды:</b>
/start - Начать работу с ботом
/menu - Показать главное меню
/help - Показать эту справку
/stats - Статистика хранилища

<b>Работа с каналами:</b>
Используйте кнопки в меню (/menu) или команды:
/add_channel @username N - Добавить канал
/my_channels - Список каналов
/voice_new - Озвучить новые посты
"""

    if is_owner(user_id):
        help_text += """
<b>Работа с чатами (только для владельца):</b>
/add_chat @username N - Добавить чат
/my_chats - Список чатов
"""

    help_text += f"""
<b>Поддерживаемые форматы документов:</b>
{', '.join(SUPPORTED_EXTENSIONS)}

<b>Способы озвучки:</b>
1️⃣ <b>Текст</b> - просто отправьте текст
2️⃣ <b>Документ</b> - отправьте файл
3️⃣ <b>Ссылка</b> - отправьте URL
4️⃣ <b>Пересланное сообщение</b> - перешлите пост

<b>Настройки TTS:</b>
🎤 Голос: {TTS_VOICE}
⚡ Скорость: {TTS_RATE}

💾 Хранилище: {MAX_STORAGE_MB} MB
"""
    await callback.message.answer(help_text, parse_mode="HTML")


@router.callback_query(F.data == "stats")
async def callback_stats(callback: CallbackQuery):
    """Обработчик кнопки Статистика"""
    await callback.answer()

    stats = storage_manager.get_storage_stats()

    stats_text = f"""
📊 <b>Статистика хранилища</b>

💾 Использовано: {stats['total_size_mb']:.2f} MB / {stats['max_size_mb']:.0f} MB
📈 Заполнено: {stats['used_percent']:.1f}%
📁 Файлов: {stats['file_count']}
✅ Свободно: {stats['available_mb']:.2f} MB
"""
    await callback.message.answer(stats_text, parse_mode="HTML")


@router.callback_query(F.data == "add_channel")
async def callback_add_channel(callback: CallbackQuery, state: FSMContext):
    """Начинает диалог добавления канала"""
    await callback.answer()

    await callback.message.answer(
        "📢 <b>Добавление канала</b>\n\n"
        "Отправьте username канала (с @ или без)\n"
        "Например: @svalka_mk\n\n"
        "Или отправьте /cancel для отмены",
        parse_mode="HTML"
    )

    await state.set_state(AddChannelStates.waiting_for_username)


@router.message(StateFilter(AddChannelStates.waiting_for_username))
async def process_channel_username(message: Message, state: FSMContext):
    """Обрабатывает username канала"""
    if message.text.startswith('/cancel'):
        await state.clear()
        await message.answer("❌ Добавление канала отменено")
        return

    channel_username = message.text.strip()

    # Сохраняем username в FSM
    await state.update_data(channel_username=channel_username)

    await message.answer(
        f"✅ Канал: {channel_username}\n\n"
        "Теперь отправьте количество последних постов для озвучки\n"
        "Например: 10\n\n"
        "Или /cancel для отмены"
    )

    await state.set_state(AddChannelStates.waiting_for_count)


@router.message(StateFilter(AddChannelStates.waiting_for_count))
async def process_channel_count(message: Message, state: FSMContext):
    """Обрабатывает количество постов для озвучки"""
    if message.text.startswith('/cancel'):
        await state.clear()
        await message.answer("❌ Добавление канала отменено")
        return

    try:
        count = int(message.text.strip())
        if count <= 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ Пожалуйста, введите положительное число")
        return

    # Получаем сохраненные данные
    data = await state.get_data()
    channel_username = data['channel_username']

    # Очищаем состояние
    await state.clear()

    # Выполняем добавление канала
    user_id = message.from_user.id
    processing_msg = await message.answer("⏳ Добавляю канал...")

    try:
        telethon = await get_telethon_service()
        channel_info = await telethon.get_channel_info(channel_username)

        if not channel_info:
            await processing_msg.edit_text(f"❌ Канал {channel_username} не найден!")
            return

        channel_id, channel_title = channel_info

        await add_tracked_channel(
            user_id=user_id,
            channel_username=channel_username.lstrip('@'),
            channel_id=channel_id,
            channel_title=channel_title
        )

        await processing_msg.edit_text(
            f"✅ Канал добавлен: {channel_title}\n\n"
            f"⏳ Озвучиваю последние {count} постов..."
        )

        messages = await telethon.get_channel_messages(channel_username, limit=count)

        if not messages:
            await processing_msg.edit_text(
                f"✅ Канал добавлен: {channel_title}\n\n"
                f"❌ Не найдено сообщений для озвучки."
            )
            return

        await voice_messages(
            message,
            messages,
            user_id,
            source_type='channel',
            source_id=channel_id,
            status_msg=processing_msg
        )

    except Exception as e:
        logger.error(f"Ошибка при добавлении канала: {e}")
        await processing_msg.edit_text(f"❌ Ошибка: {str(e)}")


@router.callback_query(F.data == "add_chat")
async def callback_add_chat(callback: CallbackQuery, state: FSMContext):
    """Начинает диалог добавления чата (только для владельца)"""
    user_id = callback.from_user.id

    if not is_owner(user_id):
        await callback.answer("❌ Эта функция доступна только владельцу!", show_alert=True)
        return

    await callback.answer()

    await callback.message.answer(
        "💬 <b>Добавление чата</b>\n\n"
        "Отправьте username чата (с @) или ID чата\n"
        "Например: @friend или 123456789\n\n"
        "Или отправьте /cancel для отмены",
        parse_mode="HTML"
    )

    await state.set_state(AddChatStates.waiting_for_identifier)


@router.message(StateFilter(AddChatStates.waiting_for_identifier))
async def process_chat_identifier(message: Message, state: FSMContext):
    """Обрабатывает username/ID чата"""
    if message.text.startswith('/cancel'):
        await state.clear()
        await message.answer("❌ Добавление чата отменено")
        return

    chat_identifier = message.text.strip()

    await state.update_data(chat_identifier=chat_identifier)

    await message.answer(
        f"✅ Чат: {chat_identifier}\n\n"
        "Теперь отправьте количество последних сообщений для озвучки\n"
        "Например: 15\n\n"
        "Или /cancel для отмены"
    )

    await state.set_state(AddChatStates.waiting_for_count)


@router.message(StateFilter(AddChatStates.waiting_for_count))
async def process_chat_count(message: Message, state: FSMContext):
    """Обрабатывает количество сообщений для озвучки"""
    if message.text.startswith('/cancel'):
        await state.clear()
        await message.answer("❌ Добавление чата отменено")
        return

    try:
        count = int(message.text.strip())
        if count <= 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ Пожалуйста, введите положительное число")
        return

    data = await state.get_data()
    chat_identifier = data['chat_identifier']

    await state.clear()

    user_id = message.from_user.id
    processing_msg = await message.answer("⏳ Добавляю чат...")

    try:
        telethon = await get_telethon_service()
        chat_info = await telethon.get_chat_info(chat_identifier)

        if not chat_info:
            await processing_msg.edit_text(f"❌ Чат {chat_identifier} не найден!")
            return

        chat_id, chat_title, chat_username = chat_info

        await add_tracked_chat(
            user_id=user_id,
            chat_id=chat_id,
            chat_username=chat_username,
            chat_title=chat_title
        )

        await processing_msg.edit_text(
            f"✅ Чат добавлен: {chat_title}\n\n"
            f"⏳ Озвучиваю последние {count} сообщений..."
        )

        messages = await telethon.get_chat_messages(chat_id, limit=count)

        if not messages:
            await processing_msg.edit_text(
                f"✅ Чат добавлен: {chat_title}\n\n"
                f"❌ Не найдено сообщений для озвучки."
            )
            return

        await voice_messages(
            message,
            messages,
            user_id,
            source_type='chat',
            source_id=chat_id,
            status_msg=processing_msg
        )

    except Exception as e:
        logger.error(f"Ошибка при добавлении чата: {e}")
        await processing_msg.edit_text(f"❌ Ошибка: {str(e)}")


@router.callback_query(F.data == "my_channels")
async def callback_my_channels(callback: CallbackQuery):
    """Показывает список каналов"""
    await callback.answer()

    user_id = callback.from_user.id
    channels = await get_tracked_channels(user_id)

    if not channels:
        await callback.message.answer("У вас нет отслеживаемых каналов.")
        return

    text = "📢 <b>Ваши отслеживаемые каналы:</b>\n\n"
    for channel in channels:
        text += f"• @{channel.channel_username} - {channel.channel_title}\n"

    await callback.message.answer(text, parse_mode="HTML")


@router.callback_query(F.data == "my_chats")
async def callback_my_chats(callback: CallbackQuery):
    """Показывает список чатов"""
    user_id = callback.from_user.id

    if not is_owner(user_id):
        await callback.answer("❌ Эта функция доступна только владельцу!", show_alert=True)
        return

    await callback.answer()

    chats = await get_tracked_chats(user_id)

    if not chats:
        await callback.message.answer("У вас нет отслеживаемых чатов.")
        return

    text = "💬 <b>Ваши отслеживаемые чаты:</b>\n\n"
    for chat in chats:
        username_text = f"@{chat.chat_username}" if chat.chat_username else f"ID: {chat.chat_id}"
        text += f"• {username_text} - {chat.chat_title}\n"

    await callback.message.answer(text, parse_mode="HTML")


@router.callback_query(F.data == "voice_new")
async def callback_voice_new(callback: CallbackQuery):
    """Озвучивает новые посты из всех каналов"""
    await callback.answer()

    user_id = callback.from_user.id
    processing_msg = await callback.message.answer("⏳ Проверяю новые сообщения...")

    try:
        telethon = await get_telethon_service()

        channels = await get_tracked_channels(user_id)

        chats = []
        if is_owner(user_id):
            chats = await get_tracked_chats(user_id)

        if not channels and not chats:
            await processing_msg.edit_text(
                "❌ У вас нет отслеживаемых каналов или чатов!\n\n"
                "Используйте кнопку '➕ Добавить канал' в меню"
            )
            return

        total_new_messages = 0

        for channel in channels:
            last_msg_id = await get_last_voiced_message_id(user_id, 'channel', channel.channel_id)

            messages = await telethon.get_channel_messages(
                channel.channel_username,
                limit=100,
                min_id=last_msg_id
            )

            if messages:
                await processing_msg.edit_text(
                    f"📢 Канал: {channel.channel_title}\n"
                    f"⏳ Озвучиваю {len(messages)} новых сообщений..."
                )

                await voice_messages(
                    callback.message,
                    messages,
                    user_id,
                    source_type='channel',
                    source_id=channel.channel_id,
                    status_msg=None
                )

                total_new_messages += len(messages)

        for chat in chats:
            last_msg_id = await get_last_voiced_message_id(user_id, 'chat', chat.chat_id)

            messages = await telethon.get_chat_messages(
                chat.chat_id,
                limit=100,
                min_id=last_msg_id
            )

            if messages:
                await processing_msg.edit_text(
                    f"💬 Чат: {chat.chat_title}\n"
                    f"⏳ Озвучиваю {len(messages)} новых сообщений..."
                )

                await voice_messages(
                    callback.message,
                    messages,
                    user_id,
                    source_type='chat',
                    source_id=chat.chat_id,
                    status_msg=None
                )

                total_new_messages += len(messages)

        if total_new_messages == 0:
            await processing_msg.edit_text("✅ Нет новых сообщений для озвучки!")
        else:
            await processing_msg.edit_text(f"✅ Озвучено {total_new_messages} новых сообщений!")

    except Exception as e:
        logger.error(f"Ошибка при озвучке новых сообщений: {e}")
        await processing_msg.edit_text(f"❌ Ошибка: {str(e)}")
