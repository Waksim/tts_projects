"""
Text Utils - утилиты для обработки текста перед синтезом речи
"""

import re
import secrets
from typing import List


def clean_text_for_tts(text: str) -> str:
    """
    Очищает текст от символов разметки и артефактов для озвучивания.

    Удаляет:
    - Markdown разметку (заголовки, код, ссылки, таблицы)
    - Служебные символы
    - Лишние пробелы и переносы
    """
    if not text:
        return ""

    # 1. Удаляем маркеры начала/конца отрывка
    lines = text.strip().split('\n')
    if lines and lines[0].strip() == '---':
        lines.pop(0)
    if lines and lines[-1].strip() == '---':
        lines.pop()
    text = '\n'.join(lines)

    # 2. Удаляем markdown заголовки (# ## ### и т.д.)
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)

    # 3. Удаляем блоки кода (``` код ```)
    text = re.sub(r'```[\s\S]*?```', '', text)

    # 4. Удаляем inline код (`код`)
    text = re.sub(r'`([^`]+)`', r'\1', text)

    # 5. Удаляем ссылки markdown [текст](url) - оставляем только текст
    text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)

    # 6. Удаляем изображения ![alt](url)
    text = re.sub(r'!\[([^\]]*)\]\([^\)]+\)', '', text)

    # 7. Удаляем цитаты (> текст)
    text = re.sub(r'^>\s+', '', text, flags=re.MULTILINE)

    # 8. Удаляем выделение жирным (**текст** или __текст__)
    text = re.sub(r'\*\*([^\*]+)\*\*', r'\1', text)
    text = re.sub(r'__([^_]+)__', r'\1', text)

    # 9. Удаляем выделение курсивом (*текст* или _текст_)
    text = re.sub(r'\*([^\*]+)\*', r'\1', text)
    text = re.sub(r'_([^_]+)_', r'\1', text)

    # 10. Удаляем markdown таблицы (строки содержащие |)
    lines = text.split('\n')
    cleaned_lines = []
    for line in lines:
        # Если строка содержит много | символов, считаем её частью таблицы
        if line.count('|') < 2:
            cleaned_lines.append(line)
    text = '\n'.join(cleaned_lines)

    # 11. Удаляем строки, содержащие только разделители сцен (***, ---)
    text = re.sub(r'^\s*[-*_]{3,}\s*$', '', text, flags=re.MULTILINE)

    # 12. Удаляем тире в начале строк (маркеры диалогов)
    text = re.sub(r'^\s*—\s*', '', text, flags=re.MULTILINE)

    # 13. Удаляем списки (- пункт, * пункт, 1. пункт)
    text = re.sub(r'^\s*[-*+]\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'^\s*\d+\.\s+', '', text, flags=re.MULTILINE)

    # 14. Заменяем типографские символы на стандартные
    text = text.replace('«', '"')
    text = text.replace('»', '"')
    text = text.replace('…', '...')
    text = text.replace('–', '-')  # Среднее тире
    text = text.replace('—', '-')  # Длинное тире

    # 15. Удаляем все оставшиеся звездочки
    text = text.replace('*', '')

    # 16. Удаляем символы #
    text = text.replace('#', '')

    # 17. Убираем лишние пробелы и переносы строк
    text = re.sub(r'[ \t]+', ' ', text)  # Множественные пробелы в один
    text = re.sub(r'\n\s*\n\s*\n+', '\n\n', text)  # Множественные переносы в двойной

    return text.strip()


def split_text_into_chunks(text: str, limit: int = 3000) -> List[str]:
    """
    Разделяет большой текст на части (чанки), не превышая заданный лимит.
    Разделяет по абзацам, а слишком длинные абзацы - по предложениям.

    Args:
        text: Текст для разделения
        limit: Максимальный размер чанка в символах

    Returns:
        Список чанков текста
    """
    if not text:
        return []

    # Сначала очищаем текст
    cleaned_text = clean_text_for_tts(text)

    if len(cleaned_text) <= limit:
        return [cleaned_text]

    chunks = []
    current_chunk = ""
    paragraphs = cleaned_text.split('\n\n')

    def add_to_chunks(chunk_to_add):
        """Вспомогательная функция для добавления непустых чанков."""
        nonlocal chunks
        stripped_chunk = chunk_to_add.strip()
        if stripped_chunk:
            chunks.append(stripped_chunk)

    for paragraph in paragraphs:
        paragraph = paragraph.strip()
        if not paragraph:
            continue

        # Если сам по себе абзац уже превышает лимит
        if len(paragraph) > limit:
            # Сначала сохраняем то, что уже было накоплено
            add_to_chunks(current_chunk)
            current_chunk = ""

            # Теперь дробим этот длинный абзац по предложениям
            sentences = re.split(r'(?<=[.!?])\s+', paragraph)
            temp_paragraph_chunk = ""
            for sentence in sentences:
                if len(temp_paragraph_chunk) + len(sentence) + 1 > limit:
                    add_to_chunks(temp_paragraph_chunk)
                    temp_paragraph_chunk = sentence
                else:
                    if temp_paragraph_chunk:
                        temp_paragraph_chunk += " " + sentence
                    else:
                        temp_paragraph_chunk = sentence

            # Добавляем остаток от дробления длинного абзаца
            add_to_chunks(temp_paragraph_chunk)
            continue

        # Стандартная логика: если добавление абзаца превысит лимит
        if len(current_chunk) + len(paragraph) + 2 > limit:
            add_to_chunks(current_chunk)
            current_chunk = paragraph
        else:
            if current_chunk:
                current_chunk += "\n\n" + paragraph
            else:
                current_chunk = paragraph

    # Добавляем последний оставшийся чанк
    add_to_chunks(current_chunk)

    return chunks


def sanitize_filename(text: str, max_length: int = 100) -> str:
    """
    Очищает строку, чтобы она была безопасным именем файла.
    """
    if not text:
        return "audio"

    # Удаляем или заменяем недопустимые символы
    sanitized = re.sub(r'[<>:"/\\|?*\x00-\x1F]', '', str(text))
    # Заменяем пробелы на подчеркивания
    sanitized = re.sub(r'\s+', '_', sanitized)
    # Удаляем дублирующиеся точки и подчеркивания
    sanitized = re.sub(r'__+', '_', sanitized)
    sanitized = sanitized.replace('..', '.')
    # Обрезаем до максимальной длины
    return sanitized.strip('._')[:max_length]


def generate_filename_from_text(text: str, user_id: int, max_words: int = 7) -> str:
    """
    Генерирует имя файла из первых N слов очищенного текста + случайный суффикс.

    Args:
        text: Исходный текст
        user_id: ID пользователя (для префикса)
        max_words: Максимальное количество слов для имени (по умолчанию 7)

    Returns:
        Имя файла в формате: {user_id}_{первые_7_слов}_{random}.mp3
    """
    # Генерируем 6-символьный случайный суффикс (криптостойкий)
    random_suffix = secrets.token_hex(3)  # 3 байта = 6 hex символов

    if not text:
        return f"{user_id}_audio_{random_suffix}.mp3"

    # Очищаем текст от markdown и спецсимволов
    cleaned = clean_text_for_tts(text)

    # Разбиваем на слова и берем первые N
    words = cleaned.split()[:max_words]

    # Если слов меньше, чем ожидалось, берем все что есть
    if not words:
        return f"{user_id}_audio_{random_suffix}.mp3"

    # Объединяем слова в строку
    filename_base = '_'.join(words)

    # Очищаем от недопустимых символов для имени файла
    filename_base = sanitize_filename(filename_base, max_length=100)

    return f"{user_id}_{filename_base}_{random_suffix}.mp3"
