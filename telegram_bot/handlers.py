"""
Обработчики команд и сообщений Telegram Bot
"""

import os
import sys
import asyncio
import logging
import shutil
from pathlib import Path

from aiogram import Router, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    Message,
    FSInputFile,
    CallbackQuery
)
from aiogram.enums import ChatAction
from aiogram.exceptions import TelegramBadRequest
import re

# Логгер для handlers
logger = logging.getLogger(__name__)

# Добавляем путь к tts_common
sys.path.insert(0, str(Path(__file__).parent.parent))

from tts_common import (
    synthesize_text,
    synthesize_text_with_duration_limit,
    parse_document,
    parse_url,
    is_valid_url,
    StorageManager,
    sanitize_filename,
    generate_filename_from_text,
    estimate_duration_minutes,
    format_duration_display,
    calculate_parts_info
)
from tts_common.document_parser import SUPPORTED_EXTENSIONS

from config import (
    WELCOME_MESSAGE,
    PROCESSING_MESSAGE,
    AUDIO_DIR,
    TTS_VOICE,
    TTS_RATE,
    TTS_PITCH,
    MAX_STORAGE_MB,
    OWNER_ID,
    AVAILABLE_VOICES
)
from database import (
    save_request,
    add_tracked_channel,
    add_tracked_chat,
    get_tracked_channels,
    get_tracked_chats,
    save_voiced_message,
    get_last_voiced_message_id,
    get_user_voice,
    set_user_voice,
    get_user_rate,
    set_user_rate,
    get_user_max_duration,
    set_user_max_duration
)
from telethon_service import get_telethon_service
from keyboards import (
    get_main_menu_keyboard,
    get_back_button_keyboard,
    get_posts_count_keyboard,
    get_my_channels_keyboard,
    get_messages_count_keyboard,
    get_my_chats_keyboard,
    get_voice_selection_keyboard,
    get_rate_selection_keyboard,
    get_duration_selection_keyboard
)
from states import AddChannelStates, AddChatStates

# Создаем роутер
router = Router()

# Инициализируем менеджер хранилища
storage_manager = StorageManager(str(AUDIO_DIR), MAX_STORAGE_MB)


# ===== HELPER КЛАСС ДЛЯ УПОРЯДОЧЕННОЙ ОТПРАВКИ ЧАСТЕЙ =====


class OrderedPartSender:
    """
    Класс для упорядоченной отправки частей аудио по мере их готовности.
    Гарантирует, что части отправляются в правильном порядке (1, 2, 3, ...),
    даже если они готовятся параллельно и в произвольном порядке.
    """

    def __init__(self, message: Message, total_parts: int, title_formatter):
        """
        Args:
            message: Сообщение для отправки аудио
            total_parts: Общее количество частей
            title_formatter: Функция для форматирования названия (part_num, total_parts) -> str
        """
        self.message = message
        self.total_parts = total_parts
        self.title_formatter = title_formatter
        self.next_to_send = 1  # Следующий номер части для отправки
        self.ready_parts = {}  # Словарь {part_num: file_path} готовых, но ещё не отправленных частей
        self.lock = asyncio.Lock()  # Для thread-safe доступа

    async def on_part_ready(self, part_num: int, file_path: str, total_parts: int):
        """
        Callback, вызываемый когда часть готова.
        Отправляет часть если она следующая по порядку, или сохраняет для последующей отправки.
        """
        async with self.lock:
            # Сохраняем готовую часть
            self.ready_parts[part_num] = file_path
            print(f"✅ Часть {part_num}/{total_parts} готова к отправке")

            # Отправляем все части которые готовы и идут по порядку
            while self.next_to_send in self.ready_parts:
                current_part = self.next_to_send
                current_file = self.ready_parts.pop(current_part)

                # Формируем название
                title = self.title_formatter(current_part, self.total_parts)

                # Отправляем
                try:
                    audio_file = FSInputFile(current_file)
                    await self.message.answer_audio(
                        audio_file,
                        title=title,
                        performer="MKttsBOT"
                    )
                    print(f"📤 Часть {current_part}/{self.total_parts} отправлена")

                    # Удаляем файл сразу после отправки
                    try:
                        os.remove(current_file)
                    except OSError:
                        pass
                except Exception as e:
                    logger.error(f"Ошибка при отправке части {current_part}: {e}")

                self.next_to_send += 1


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


async def show_main_menu(message: Message, edit: bool = False):
    """
    Показывает главное меню с inline кнопками.

    Args:
        message: Сообщение пользователя
        edit: Если True, редактирует существующее сообщение
    """
    user_id = message.from_user.id
    markup = get_main_menu_keyboard(user_id)
    text = "🎛 <b>Главное меню</b>\n\nВыберите действие:"

    if edit:
        try:
            await message.edit_text(text, reply_markup=markup, parse_mode="HTML")
        except TelegramBadRequest:
            # Если не удалось отредактировать, отправляем новое
            await message.answer(text, reply_markup=markup, parse_mode="HTML")
    else:
        await message.answer(text, reply_markup=markup, parse_mode="HTML")


def get_voice_display_name(voice_name: str) -> str:
    """Формирует красивое отображение голоса для пользователя"""
    # Получаем базовое имя голоса
    if voice_name in AVAILABLE_VOICES:
        display_name = AVAILABLE_VOICES[voice_name]["name"]
    else:
        display_name = voice_name  # fallback на ID голоса

    return display_name


@router.message(Command("help"))
async def cmd_help(message: Message):
    """Обработчик команды /help"""
    user_id = message.from_user.id

    # Получаем текущий голос пользователя
    voice_name = await get_user_voice(user_id)
    voice_display = get_voice_display_name(voice_name)

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
🎤 Ваш голос: {voice_display}
⚡ Скорость: {TTS_RATE}

💾 Хранилище: {MAX_STORAGE_MB} MB
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

        # Получаем персональные настройки пользователя
        voice_name = await get_user_voice(user_id)
        speech_rate = await get_user_rate(user_id)
        max_duration = await get_user_max_duration(user_id)

        # Проверяем свободное место на диске
        free_space = shutil.disk_usage("/").free
        if free_space < 300_000_000:  # < 300MB
            await processing_msg.edit_text(
                f"❌ Недостаточно места на сервере ({free_space/1024/1024:.0f} MB свободно).\n\n"
                "Попробуйте позже или отправьте текст покороче."
            )
            return

        # Рассчитываем количество частей
        parts_count, avg_duration = calculate_parts_info(text, max_duration)

        if parts_count > 1:
            duration_text = format_duration_display(avg_duration)
            await processing_msg.edit_text(
                f"🎤 Синтезирую речь...\n\n"
                f"Текст будет разбит на {parts_count} частей (~{duration_text} каждая)"
            )
        else:
            await processing_msg.edit_text("🎤 Синтезирую речь...")

        await message.bot.send_chat_action(message.chat.id, ChatAction.RECORD_VOICE)

        # Генерируем имя файла из первых 7 слов текста
        audio_filename = generate_filename_from_text(text, user_id)
        audio_path = AUDIO_DIR / audio_filename

        # Проверяем и освобождаем место
        # Коэффициент зависит от скорости речи (медленная речь = больше файл)
        multiplier = 300 if speech_rate in ["+25%", "+50%", "+75%", "+100%"] else 600
        estimated_size = len(text) * multiplier * 3  # ×3 для промежуточных файлов
        await storage_manager.ensure_space_available_async(estimated_size)

        # Берем имя из имени документа (без расширения)
        doc_name = os.path.splitext(file_name)[0]

        # Если частей будет больше одной, используем упорядоченную отправку
        if parts_count > 1:
            # Создаем sender для упорядоченной отправки
            def title_formatter(part_num, total):
                return f"Часть {part_num}/{total} - {doc_name}"

            sender = OrderedPartSender(message, parts_count, title_formatter)

            # Синтезируем с callback для отправки по мере готовности
            audio_files = await synthesize_text_with_duration_limit(
                text,
                str(audio_path),
                max_duration_minutes=max_duration,
                voice=voice_name,
                rate=speech_rate,
                pitch=TTS_PITCH,
                on_part_ready=sender.on_part_ready
            )
        else:
            # Обычный синтез без callback
            audio_files = await synthesize_text_with_duration_limit(
                text,
                str(audio_path),
                max_duration_minutes=max_duration,
                voice=voice_name,
                rate=speech_rate,
                pitch=TTS_PITCH
            )

        if not audio_files:
            raise Exception("Не удалось синтезировать аудио")

        # Если одна часть, отправляем её вручную (при множественных уже отправлено через callback)
        if len(audio_files) == 1:
            await processing_msg.edit_text("📤 Отправляю аудио...")
            audio_file = FSInputFile(audio_files[0])
            await message.answer_audio(
                audio_file,
                title=file_name,
                performer="MKttsBOT"
            )
            # Удаляем файл сразу после отправки
            try:
                os.remove(audio_files[0])
            except OSError:
                pass

        # Удаляем сообщение о обработке
        await processing_msg.delete()

        # Сохраняем в БД (сохраняем путь к первому файлу)
        await save_request(
            user_id=user_id,
            username=username,
            request_type='document',
            content=file_name,
            audio_path=audio_files[0] if audio_files else None,
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

        # Получаем персональные настройки пользователя
        voice_name = await get_user_voice(user_id)
        speech_rate = await get_user_rate(user_id)
        max_duration = await get_user_max_duration(user_id)

        # Проверяем свободное место на диске
        free_space = shutil.disk_usage("/").free
        if free_space < 300_000_000:  # < 300MB
            await processing_msg.edit_text(
                f"❌ Недостаточно места на сервере ({free_space/1024/1024:.0f} MB свободно).\n\n"
                "Попробуйте позже или отправьте текст покороче."
            )
            return

        # Рассчитываем количество частей
        parts_count, avg_duration = calculate_parts_info(text, max_duration)

        if parts_count > 1:
            duration_text = format_duration_display(avg_duration)
            await processing_msg.edit_text(
                f"🎤 Синтезирую речь...\n\n"
                f"Текст будет разбит на {parts_count} частей (~{duration_text} каждая)"
            )
        else:
            await processing_msg.edit_text("🎤 Синтезирую речь...")

        await message.bot.send_chat_action(message.chat.id, ChatAction.RECORD_VOICE)

        # Генерируем имя файла из первых 7 слов извлеченного текста
        audio_filename = generate_filename_from_text(text, user_id)
        audio_path = AUDIO_DIR / audio_filename

        # Проверяем и освобождаем место
        # Коэффициент зависит от скорости речи (медленная речь = больше файл)
        multiplier = 300 if speech_rate in ["+25%", "+50%", "+75%", "+100%"] else 600
        estimated_size = len(text) * multiplier * 3  # ×3 для промежуточных файлов
        await storage_manager.ensure_space_available_async(estimated_size)

        # Берем первые 7 слов для названия
        web_title = ' '.join(text.split()[:7])

        # Если частей будет больше одной, используем упорядоченную отправку
        if parts_count > 1:
            # Создаем sender для упорядоченной отправки
            def title_formatter(part_num, total):
                return f"Часть {part_num}/{total} - {web_title}"

            sender = OrderedPartSender(message, parts_count, title_formatter)

            # Синтезируем с callback для отправки по мере готовности
            audio_files = await synthesize_text_with_duration_limit(
                text,
                str(audio_path),
                max_duration_minutes=max_duration,
                voice=voice_name,
                rate=speech_rate,
                pitch=TTS_PITCH,
                on_part_ready=sender.on_part_ready
            )
        else:
            # Обычный синтез без callback
            audio_files = await synthesize_text_with_duration_limit(
                text,
                str(audio_path),
                max_duration_minutes=max_duration,
                voice=voice_name,
                rate=speech_rate,
                pitch=TTS_PITCH
            )

        if not audio_files:
            raise Exception("Не удалось синтезировать аудио")

        # Если одна часть, отправляем её вручную (при множественных уже отправлено через callback)
        if len(audio_files) == 1:
            await processing_msg.edit_text("📤 Отправляю аудио...")
            audio_file = FSInputFile(audio_files[0])
            await message.answer_audio(
                audio_file,
                title=web_title,
                performer="MKttsBOT"
            )
            # Удаляем файл сразу после отправки
            try:
                os.remove(audio_files[0])
            except OSError:
                pass

        await processing_msg.delete()

        # Сохраняем в БД (сохраняем путь к первому файлу)
        await save_request(
            user_id=user_id,
            username=username,
            request_type='url',
            content=url,
            audio_path=audio_files[0] if audio_files else None,
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

    if len(text) < 10:
        await message.answer("❌ Текст слишком короткий. Минимум 10 символов.")
        return

    processing_msg = await message.answer(PROCESSING_MESSAGE)

    try:
        await message.bot.send_chat_action(message.chat.id, ChatAction.RECORD_VOICE)

        # Получаем персональные настройки пользователя
        voice_name = await get_user_voice(user_id)
        speech_rate = await get_user_rate(user_id)
        max_duration = await get_user_max_duration(user_id)

        # Проверяем свободное место на диске
        free_space = shutil.disk_usage("/").free
        if free_space < 300_000_000:  # < 300MB
            await processing_msg.edit_text(
                f"❌ Недостаточно места на сервере ({free_space/1024/1024:.0f} MB свободно).\n\n"
                "Попробуйте позже или отправьте текст покороче."
            )
            return

        # Рассчитываем количество частей
        parts_count, avg_duration = calculate_parts_info(text, max_duration)

        if parts_count > 1:
            duration_text = format_duration_display(avg_duration)
            await processing_msg.edit_text(
                f"🎤 Синтезирую речь...\n\n"
                f"Текст будет разбит на {parts_count} частей (~{duration_text} каждая)"
            )

        # Синтезируем аудио - используем первые 7 слов для имени файла
        audio_filename = generate_filename_from_text(text, user_id)
        audio_path = AUDIO_DIR / audio_filename

        # Проверяем и освобождаем место
        # Коэффициент зависит от скорости речи (медленная речь = больше файл)
        multiplier = 300 if speech_rate in ["+25%", "+50%", "+75%", "+100%"] else 600
        estimated_size = len(text) * multiplier * 3  # ×3 для промежуточных файлов
        await storage_manager.ensure_space_available_async(estimated_size)

        # Берем первые 7 слов для названия
        text_title = ' '.join(text.split()[:7])

        # Если частей будет больше одной, используем упорядоченную отправку
        if parts_count > 1:
            # Создаем sender для упорядоченной отправки
            def title_formatter(part_num, total):
                return f"Часть {part_num}/{total} - {text_title}"

            sender = OrderedPartSender(message, parts_count, title_formatter)

            # Синтезируем с callback для отправки по мере готовности
            audio_files = await synthesize_text_with_duration_limit(
                text,
                str(audio_path),
                max_duration_minutes=max_duration,
                voice=voice_name,
                rate=speech_rate,
                pitch=TTS_PITCH,
                on_part_ready=sender.on_part_ready
            )
        else:
            # Обычный синтез без callback
            audio_files = await synthesize_text_with_duration_limit(
                text,
                str(audio_path),
                max_duration_minutes=max_duration,
                voice=voice_name,
                rate=speech_rate,
                pitch=TTS_PITCH
            )

        if not audio_files:
            raise Exception("Не удалось синтезировать аудио")

        # Если одна часть, отправляем её вручную (при множественных уже отправлено через callback)
        if len(audio_files) == 1:
            await processing_msg.edit_text("📤 Отправляю аудио...")
            audio_file = FSInputFile(audio_files[0])
            await message.answer_audio(
                audio_file,
                title=text_title,
                performer="MKttsBOT"
            )
            # Удаляем файл сразу после отправки
            try:
                os.remove(audio_files[0])
            except OSError:
                pass

        # Удаляем сообщение о обработке
        await processing_msg.delete()

        # Сохраняем в БД (сохраняем путь к первому файлу)
        await save_request(
            user_id=user_id,
            username=username,
            request_type='text',
            content=text[:200],  # Сохраняем первые 200 символов
            audio_path=audio_files[0] if audio_files else None,
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
            status_msg=processing_msg,
            source_title=channel_title
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
            status_msg=processing_msg,
            source_title=chat_title
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
                    status_msg=None,  # Не обновляем статус для каждого канала
                    source_title=channel.channel_title
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
                    status_msg=None,
                    source_title=chat.chat_title
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
    status_msg: Message = None,
    source_title: str = None
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
        source_title: Название канала или чата (опционально)
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

        # Получаем персональные настройки пользователя
        voice_name = await get_user_voice(user_id)
        speech_rate = await get_user_rate(user_id)
        max_duration = await get_user_max_duration(user_id)

        # Проверяем свободное место на диске
        free_space = shutil.disk_usage("/").free
        if free_space < 300_000_000:  # < 300MB
            if status_msg:
                await status_msg.edit_text(
                    f"❌ Недостаточно места на сервере ({free_space/1024/1024:.0f} MB свободно).\n\n"
                    "Попробуйте позже."
                )
            return

        # Рассчитываем количество частей
        parts_count, avg_duration = calculate_parts_info(combined_text, max_duration)

        if parts_count > 1:
            duration_text = format_duration_display(avg_duration)
            if status_msg:
                await status_msg.edit_text(
                    f"🎤 Синтезирую {len(combined_text)} символов...\n\n"
                    f"Будет создано {parts_count} частей (~{duration_text} каждая)"
                )
        else:
            if status_msg:
                await status_msg.edit_text(f"🎤 Синтезирую {len(combined_text)} символов...")

        # Генерируем имя файла из первого сообщения
        audio_filename = generate_filename_from_text(valid_messages[0][1], user_id)
        audio_path = AUDIO_DIR / audio_filename

        # Проверяем и освобождаем место
        # Коэффициент зависит от скорости речи (медленная речь = больше файл)
        multiplier = 300 if speech_rate in ["+25%", "+50%", "+75%", "+100%"] else 600
        estimated_size = len(combined_text) * multiplier * 3  # ×3 для промежуточных файлов
        await storage_manager.ensure_space_available_async(estimated_size)

        # Формируем базовое название аудио
        if source_title:
            # Очищаем название от недопустимых символов
            clean_title = sanitize_filename(source_title).replace('.mp3', '')
            base_title = f"{clean_title} ({len(valid_messages)} messages)"
        else:
            # Fallback на старое поведение
            source_name = "Channel" if source_type == "channel" else "Chat"
            base_title = f"{source_name} ({len(valid_messages)} messages)"

        # Если частей будет больше одной, используем упорядоченную отправку
        if parts_count > 1:
            # Создаем sender для упорядоченной отправки
            def title_formatter(part_num, total):
                return f"Часть {part_num}/{total} - {base_title}"

            sender = OrderedPartSender(message, parts_count, title_formatter)

            # Синтезируем с callback для отправки по мере готовности
            audio_files = await synthesize_text_with_duration_limit(
                combined_text,
                str(audio_path),
                max_duration_minutes=max_duration,
                voice=voice_name,
                rate=speech_rate,
                pitch=TTS_PITCH,
                on_part_ready=sender.on_part_ready
            )
        else:
            # Обычный синтез без callback
            audio_files = await synthesize_text_with_duration_limit(
                combined_text,
                str(audio_path),
                max_duration_minutes=max_duration,
                voice=voice_name,
                rate=speech_rate,
                pitch=TTS_PITCH
            )

        if not audio_files:
            if status_msg:
                await status_msg.edit_text("❌ Не удалось синтезировать аудио")
            return

        # Если одна часть, отправляем её вручную (при множественных уже отправлено через callback)
        if len(audio_files) == 1:
            if status_msg:
                await status_msg.edit_text("📤 Отправляю аудио...")

            audio_file = FSInputFile(audio_files[0])
            await message.answer_audio(
                audio_file,
                title=base_title,
                performer="MKttsBOT"
            )
            # Удаляем файл сразу после отправки
            try:
                os.remove(audio_files[0])
            except OSError:
                pass

        # Сохраняем в БД информацию о последнем озвученном сообщении
        last_msg_id = valid_messages[-1][0]
        await save_voiced_message(
            user_id=user_id,
            source_type=source_type,
            source_id=source_id,
            message_id=last_msg_id,
            message_text=combined_text[:200],
            audio_path=audio_files[0] if audio_files else None
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


@router.callback_query(F.data == "back_to_main")
async def callback_back_to_main(callback: CallbackQuery, state: FSMContext):
    """Возврат в главное меню"""
    await callback.answer()

    # Очищаем FSM состояние
    await state.clear()

    # Редактируем сообщение с главным меню
    await show_main_menu(callback.message, edit=True)


@router.callback_query(F.data == "help")
async def callback_help(callback: CallbackQuery):
    """Обработчик кнопки Помощь"""
    await callback.answer()

    user_id = callback.from_user.id

    # Получаем текущий голос пользователя
    voice_name = await get_user_voice(user_id)
    voice_display = get_voice_display_name(voice_name)

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
🎤 Ваш голос: {voice_display}
⚡ Скорость: {TTS_RATE}

💾 Хранилище: {MAX_STORAGE_MB} MB
"""
    # Редактируем сообщение вместо отправки нового
    try:
        await callback.message.edit_text(help_text, parse_mode="HTML", reply_markup=get_back_button_keyboard())
    except TelegramBadRequest:
        await callback.message.answer(help_text, parse_mode="HTML", reply_markup=get_back_button_keyboard())


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
    # Редактируем сообщение вместо отправки нового
    try:
        await callback.message.edit_text(stats_text, parse_mode="HTML", reply_markup=get_back_button_keyboard())
    except TelegramBadRequest:
        await callback.message.answer(stats_text, parse_mode="HTML", reply_markup=get_back_button_keyboard())


@router.callback_query(F.data == "add_channel")
async def callback_add_channel(callback: CallbackQuery, state: FSMContext):
    """Начинает диалог добавления канала"""
    await callback.answer()

    text = (
        "📢 <b>Добавление канала</b>\n\n"
        "Отправьте username канала (с @ или без)\n"
        "Например: @svalka_mk"
    )

    # Редактируем сообщение с кнопкой "Назад"
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_back_button_keyboard())
    except TelegramBadRequest:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=get_back_button_keyboard())

    # Сохраняем message_id для последующего редактирования
    await state.update_data(menu_message_id=callback.message.message_id)
    await state.set_state(AddChannelStates.waiting_for_username)


@router.message(StateFilter(AddChannelStates.waiting_for_username))
async def process_channel_username(message: Message, state: FSMContext):
    """Обрабатывает username канала и добавляет его в БД"""
    channel_username = message.text.strip()
    user_id = message.from_user.id

    # Получаем message_id меню из state
    data = await state.get_data()
    menu_message_id = data.get('menu_message_id')

    try:
        # Проверяем существование канала через Telethon
        telethon = await get_telethon_service()
        channel_info = await telethon.get_channel_info(channel_username)

        if not channel_info:
            await message.answer(f"❌ Канал {channel_username} не найден!")
            return

        channel_id, channel_title = channel_info

        # Добавляем канал в БД
        await add_tracked_channel(
            user_id=user_id,
            channel_username=channel_username.lstrip('@'),
            channel_id=channel_id,
            channel_title=channel_title
        )

        # Редактируем меню с выбором количества постов
        text = (
            f"✅ Канал добавлен: <b>{channel_title}</b>\n\n"
            "Выберите количество последних постов для озвучки:"
        )

        keyboard = get_posts_count_keyboard(channel_username.lstrip('@'))

        # Пытаемся отредактировать исходное сообщение меню
        if menu_message_id:
            try:
                await message.bot.edit_message_text(
                    text=text,
                    chat_id=message.chat.id,
                    message_id=menu_message_id,
                    parse_mode="HTML",
                    reply_markup=keyboard
                )
            except TelegramBadRequest:
                # Если не удалось, отправляем новое
                await message.answer(text, parse_mode="HTML", reply_markup=keyboard)
        else:
            await message.answer(text, parse_mode="HTML", reply_markup=keyboard)

        # Удаляем сообщение пользователя с username
        try:
            await message.delete()
        except:
            pass

        # Очищаем состояние
        await state.clear()

    except Exception as e:
        logger.error(f"Ошибка при добавлении канала: {e}")
        await message.answer(f"❌ Ошибка: {str(e)}")


@router.callback_query(F.data.startswith("voice_channel:"))
async def callback_voice_channel(callback: CallbackQuery):
    """Озвучивает последние N постов из канала"""
    await callback.answer()

    # Парсим callback_data: voice_channel:username:count
    parts = callback.data.split(":")
    if len(parts) != 3:
        await callback.message.edit_text("❌ Ошибка: неверный формат данных")
        return

    channel_username = parts[1]
    count = int(parts[2])
    user_id = callback.from_user.id

    # Обновляем сообщение о начале озвучки
    await callback.message.edit_text(
        f"⏳ Озвучиваю последние {count} постов из канала @{channel_username}..."
    )

    try:
        telethon = await get_telethon_service()

        # Получаем сообщения канала
        messages = await telethon.get_channel_messages(channel_username, limit=count)

        if not messages:
            await callback.message.edit_text(
                f"❌ Не найдено сообщений в канале @{channel_username}"
            )
            return

        # Получаем информацию о канале для source_id
        channel_info = await telethon.get_channel_info(channel_username)
        if not channel_info:
            await callback.message.edit_text(f"❌ Не удалось получить информацию о канале")
            return

        channel_id, channel_title = channel_info

        # Озвучиваем сообщения
        await voice_messages(
            callback.message,
            messages,
            user_id,
            source_type='channel',
            source_id=channel_id,
            status_msg=callback.message,
            source_title=channel_title
        )

        # После озвучки возвращаемся в главное меню
        await show_main_menu(callback.message, edit=True)

    except Exception as e:
        logger.error(f"Ошибка при озвучке канала: {e}")
        await callback.message.edit_text(f"❌ Ошибка: {str(e)}")


@router.callback_query(F.data == "add_chat")
async def callback_add_chat(callback: CallbackQuery, state: FSMContext):
    """Начинает диалог добавления чата (только для владельца)"""
    user_id = callback.from_user.id

    if not is_owner(user_id):
        await callback.answer("❌ Эта функция доступна только владельцу!", show_alert=True)
        return

    await callback.answer()

    text = (
        "💬 <b>Добавление чата</b>\n\n"
        "Отправьте username чата (с @) или ID чата\n"
        "Например: @friend или 123456789"
    )

    # Редактируем сообщение с кнопкой "Назад"
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_back_button_keyboard())
    except TelegramBadRequest:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=get_back_button_keyboard())

    # Сохраняем message_id для последующего редактирования
    await state.update_data(menu_message_id=callback.message.message_id)
    await state.set_state(AddChatStates.waiting_for_identifier)


@router.message(StateFilter(AddChatStates.waiting_for_identifier))
async def process_chat_identifier(message: Message, state: FSMContext):
    """Обрабатывает username/ID чата и добавляет его в БД"""
    chat_identifier = message.text.strip()
    user_id = message.from_user.id

    # Получаем message_id меню из state
    data = await state.get_data()
    menu_message_id = data.get('menu_message_id')

    try:
        # Проверяем существование чата через Telethon
        telethon = await get_telethon_service()
        chat_info = await telethon.get_chat_info(chat_identifier)

        if not chat_info:
            await message.answer(f"❌ Чат {chat_identifier} не найден!")
            return

        chat_id, chat_title, chat_username = chat_info

        # Добавляем чат в БД
        await add_tracked_chat(
            user_id=user_id,
            chat_id=chat_id,
            chat_username=chat_username,
            chat_title=chat_title
        )

        # Редактируем меню с выбором количества сообщений
        text = (
            f"✅ Чат добавлен: <b>{chat_title}</b>\n\n"
            "Выберите количество последних сообщений для озвучки:"
        )

        keyboard = get_messages_count_keyboard(chat_id)

        # Пытаемся отредактировать исходное сообщение меню
        if menu_message_id:
            try:
                await message.bot.edit_message_text(
                    text=text,
                    chat_id=message.chat.id,
                    message_id=menu_message_id,
                    parse_mode="HTML",
                    reply_markup=keyboard
                )
            except TelegramBadRequest:
                # Если не удалось, отправляем новое
                await message.answer(text, parse_mode="HTML", reply_markup=keyboard)
        else:
            await message.answer(text, parse_mode="HTML", reply_markup=keyboard)

        # Удаляем сообщение пользователя с identifier
        try:
            await message.delete()
        except:
            pass

        # Очищаем состояние
        await state.clear()

    except Exception as e:
        logger.error(f"Ошибка при добавлении чата: {e}")
        await message.answer(f"❌ Ошибка: {str(e)}")


@router.callback_query(F.data.startswith("voice_chat:"))
async def callback_voice_chat(callback: CallbackQuery):
    """Озвучивает последние N сообщений из чата"""
    await callback.answer()

    # Парсим callback_data: voice_chat:chat_id:count
    parts = callback.data.split(":")
    if len(parts) != 3:
        await callback.message.edit_text("❌ Ошибка: неверный формат данных")
        return

    chat_id = int(parts[1])
    count = int(parts[2])
    user_id = callback.from_user.id

    # Обновляем сообщение о начале озвучки
    await callback.message.edit_text(
        f"⏳ Озвучиваю последние {count} сообщений из чата..."
    )

    try:
        telethon = await get_telethon_service()

        # Получаем информацию о чате
        chat_info = await telethon.get_chat_info(chat_id)
        if not chat_info:
            await callback.message.edit_text(f"❌ Не удалось получить информацию о чате")
            return

        _, chat_title, _ = chat_info

        # Получаем сообщения чата
        messages = await telethon.get_chat_messages(chat_id, limit=count)

        if not messages:
            await callback.message.edit_text(
                f"❌ Не найдено сообщений в чате"
            )
            return

        # Озвучиваем сообщения
        await voice_messages(
            callback.message,
            messages,
            user_id,
            source_type='chat',
            source_id=chat_id,
            status_msg=callback.message,
            source_title=chat_title
        )

        # После озвучки возвращаемся в главное меню
        await show_main_menu(callback.message, edit=True)

    except Exception as e:
        logger.error(f"Ошибка при озвучке чата: {e}")
        await callback.message.edit_text(f"❌ Ошибка: {str(e)}")


@router.callback_query(F.data == "my_channels")
async def callback_my_channels(callback: CallbackQuery):
    """Показывает список каналов как интерактивные кнопки"""
    await callback.answer()

    user_id = callback.from_user.id
    channels = await get_tracked_channels(user_id)

    if not channels:
        text = "У вас нет отслеживаемых каналов.\n\nИспользуйте кнопку \"➕ Добавить канал\""
        try:
            await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_back_button_keyboard())
        except TelegramBadRequest:
            await callback.message.answer(text, parse_mode="HTML", reply_markup=get_back_button_keyboard())
        return

    text = "📢 <b>Ваши отслеживаемые каналы:</b>\n\nВыберите канал для озвучки постов:"
    keyboard = get_my_channels_keyboard(channels)

    # Редактируем сообщение
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
    except TelegramBadRequest:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=keyboard)


@router.callback_query(F.data.startswith("channel:"))
async def callback_channel_select(callback: CallbackQuery):
    """Обработчик выбора канала из списка - показывает меню выбора количества постов"""
    await callback.answer()

    # Парсим callback_data: channel:username
    channel_username = callback.data.split(":", 1)[1]

    text = f"📢 Канал: <b>@{channel_username}</b>\n\nВыберите количество постов для озвучки:"
    keyboard = get_posts_count_keyboard(channel_username)

    # Редактируем сообщение
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
    except TelegramBadRequest:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=keyboard)


@router.callback_query(F.data == "my_chats")
async def callback_my_chats(callback: CallbackQuery):
    """Показывает список чатов как интерактивные кнопки"""
    user_id = callback.from_user.id

    if not is_owner(user_id):
        await callback.answer("❌ Эта функция доступна только владельцу!", show_alert=True)
        return

    await callback.answer()

    chats = await get_tracked_chats(user_id)

    if not chats:
        text = "У вас нет отслеживаемых чатов.\n\nИспользуйте кнопку \"➕ Добавить чат\""
        try:
            await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_back_button_keyboard())
        except TelegramBadRequest:
            await callback.message.answer(text, parse_mode="HTML", reply_markup=get_back_button_keyboard())
        return

    text = "💬 <b>Ваши отслеживаемые чаты:</b>\n\nВыберите чат для озвучки сообщений:"
    keyboard = get_my_chats_keyboard(chats)

    # Редактируем сообщение
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
    except TelegramBadRequest:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=keyboard)


@router.callback_query(F.data.startswith("chat:"))
async def callback_chat_select(callback: CallbackQuery):
    """Обработчик выбора чата из списка - показывает меню выбора количества сообщений"""
    await callback.answer()

    # Парсим callback_data: chat:chat_id
    chat_id = int(callback.data.split(":", 1)[1])

    text = f"💬 <b>Чат ID: {chat_id}</b>\n\nВыберите количество сообщений для озвучки:"
    keyboard = get_messages_count_keyboard(chat_id)

    # Редактируем сообщение
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
    except TelegramBadRequest:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=keyboard)


@router.callback_query(F.data == "voice_new")
async def callback_voice_new(callback: CallbackQuery):
    """Озвучивает новые посты из всех каналов"""
    await callback.answer()

    user_id = callback.from_user.id

    # Редактируем сообщение вместо создания нового
    try:
        await callback.message.edit_text("⏳ Проверяю новые сообщения...")
    except TelegramBadRequest:
        await callback.message.answer("⏳ Проверяю новые сообщения...")

    try:
        telethon = await get_telethon_service()

        channels = await get_tracked_channels(user_id)

        chats = []
        if is_owner(user_id):
            chats = await get_tracked_chats(user_id)

        if not channels and not chats:
            text = "❌ У вас нет отслеживаемых каналов или чатов!\n\nИспользуйте кнопку '➕ Добавить канал' в меню"
            await callback.message.edit_text(text, reply_markup=get_back_button_keyboard())
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
                await callback.message.edit_text(
                    f"📢 Канал: {channel.channel_title}\n"
                    f"⏳ Озвучиваю {len(messages)} новых сообщений..."
                )

                await voice_messages(
                    callback.message,
                    messages,
                    user_id,
                    source_type='channel',
                    source_id=channel.channel_id,
                    status_msg=None,
                    source_title=channel.channel_title
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
                await callback.message.edit_text(
                    f"💬 Чат: {chat.chat_title}\n"
                    f"⏳ Озвучиваю {len(messages)} новых сообщений..."
                )

                await voice_messages(
                    callback.message,
                    messages,
                    user_id,
                    source_type='chat',
                    source_id=chat.chat_id,
                    status_msg=None,
                    source_title=chat.chat_title
                )

                total_new_messages += len(messages)

        # Показываем результат и возвращаемся в главное меню
        if total_new_messages == 0:
            await callback.message.edit_text(
                "✅ Нет новых сообщений для озвучки!",
                reply_markup=get_back_button_keyboard()
            )
        else:
            await callback.message.edit_text(
                f"✅ Озвучено {total_new_messages} новых сообщений!",
                reply_markup=get_back_button_keyboard()
            )

    except Exception as e:
        logger.error(f"Ошибка при озвучке новых сообщений: {e}")
        await callback.message.edit_text(
            f"❌ Ошибка: {str(e)}",
            reply_markup=get_back_button_keyboard()
        )


# ===== ОБРАБОТЧИКИ ВЫБОРА ГОЛОСА =====


@router.callback_query(F.data == "select_voice")
async def callback_select_voice(callback: CallbackQuery):
    """Показывает меню выбора голоса"""
    await callback.answer()

    text = "🎤 <b>Выбор голоса</b>\n\nВыберите голос для озвучивания:"
    keyboard = get_voice_selection_keyboard()

    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
    except TelegramBadRequest:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=keyboard)


@router.callback_query(F.data.startswith("set_voice:"))
async def callback_set_voice(callback: CallbackQuery):
    """Обрабатывает выбор голоса"""
    await callback.answer()

    # Парсим callback_data: set_voice:voice_id
    voice_id = callback.data.split(":", 1)[1]
    user_id = callback.from_user.id

    # Сохраняем голос
    await set_user_voice(user_id, voice_id)

    voice_name = AVAILABLE_VOICES[voice_id]["name"]
    text = f"✅ <b>Голос сохранен!</b>\n\n🎤 {voice_name}"

    try:
        await callback.message.edit_text(
            text,
            parse_mode="HTML",
            reply_markup=get_back_button_keyboard()
        )
    except TelegramBadRequest:
        await callback.message.answer(
            text,
            parse_mode="HTML",
            reply_markup=get_back_button_keyboard()
        )


# ===== ОБРАБОТЧИКИ ВЫБОРА СКОРОСТИ РЕЧИ =====


@router.callback_query(F.data == "select_rate")
async def callback_select_rate(callback: CallbackQuery):
    """Показывает меню выбора скорости речи"""
    await callback.answer()

    user_id = callback.from_user.id
    current_rate = await get_user_rate(user_id)

    # Форматируем текущую настройку
    from config import AVAILABLE_RATES
    rate_text = AVAILABLE_RATES.get(current_rate, current_rate)

    text = f"⚡ <b>Скорость речи</b>\n\nТекущая настройка: {rate_text}\n\nВыберите новое значение:"
    keyboard = get_rate_selection_keyboard()

    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
    except TelegramBadRequest:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=keyboard)


@router.callback_query(F.data.startswith("set_rate:"))
async def callback_set_rate(callback: CallbackQuery):
    """Обрабатывает выбор скорости речи"""
    await callback.answer()

    # Парсим callback_data: set_rate:rate_value
    rate_value = callback.data.split(":", 1)[1]
    user_id = callback.from_user.id

    # Сохраняем настройку
    await set_user_rate(user_id, rate_value)

    from config import AVAILABLE_RATES
    rate_label = AVAILABLE_RATES.get(rate_value, rate_value)
    text = f"✅ <b>Настройка сохранена!</b>\n\n⚡ Скорость речи: {rate_label}"

    try:
        await callback.message.edit_text(
            text,
            parse_mode="HTML",
            reply_markup=get_back_button_keyboard()
        )
    except TelegramBadRequest:
        await callback.message.answer(
            text,
            parse_mode="HTML",
            reply_markup=get_back_button_keyboard()
        )


# ===== ОБРАБОТЧИКИ ВЫБОРА ДЛИТЕЛЬНОСТИ АУДИО =====


@router.callback_query(F.data == "select_duration")
async def callback_select_duration(callback: CallbackQuery):
    """Показывает меню выбора максимальной длительности аудио"""
    await callback.answer()

    user_id = callback.from_user.id
    current_duration = await get_user_max_duration(user_id)

    # Форматируем текущую настройку
    if current_duration is None:
        duration_text = "♾️ Без лимита"
    else:
        from config import AVAILABLE_DURATIONS
        duration_text = AVAILABLE_DURATIONS.get(current_duration, f"{current_duration} минут")

    text = f"⏱ <b>Максимальная длительность аудио</b>\n\nТекущая настройка: {duration_text}\n\nВыберите новое значение:"
    keyboard = get_duration_selection_keyboard()

    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
    except TelegramBadRequest:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=keyboard)


@router.callback_query(F.data.startswith("set_duration:"))
async def callback_set_duration(callback: CallbackQuery):
    """Обрабатывает выбор длительности"""
    await callback.answer()

    # Парсим callback_data: set_duration:duration_value
    duration_value = callback.data.split(":", 1)[1]
    user_id = callback.from_user.id

    # Преобразуем значение
    if duration_value == "unlimited":
        duration_minutes = None
        duration_label = "♾️ Без лимита"
    else:
        duration_minutes = int(duration_value)
        from config import AVAILABLE_DURATIONS
        duration_label = AVAILABLE_DURATIONS.get(duration_minutes, f"{duration_minutes} минут")

    # Сохраняем настройку
    await set_user_max_duration(user_id, duration_minutes)

    text = f"✅ <b>Настройка сохранена!</b>\n\n⏱ Максимальная длительность аудио: {duration_label}\n\n"

    if duration_minutes is None:
        text += "Текст любой длины будет синтезирован в один аудиофайл."
    else:
        text += f"Если текст превышает {duration_label}, он будет автоматически разбит на несколько аудиофайлов."

    try:
        await callback.message.edit_text(
            text,
            parse_mode="HTML",
            reply_markup=get_back_button_keyboard()
        )
    except TelegramBadRequest:
        await callback.message.answer(
            text,
            parse_mode="HTML",
            reply_markup=get_back_button_keyboard()
        )
