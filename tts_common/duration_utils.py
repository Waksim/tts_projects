"""
Duration Utils - утилиты для расчета и работы с длительностью аудио
"""

import os
from typing import List, Tuple
from .text_utils import clean_text_for_tts, split_text_into_chunks


# Константы для расчета длительности
# При скорости речи +50% (как в боте): примерно 1700 символов = 1 минута аудио
CHARS_PER_MINUTE = 1700


def estimate_duration_minutes(text: str) -> float:
    """
    Оценивает длительность аудио в минутах на основе количества символов.

    Args:
        text: Текст для оценки

    Returns:
        Примерная длительность в минутах
    """
    if not text:
        return 0.0

    # Очищаем текст перед расчетом
    cleaned_text = clean_text_for_tts(text)
    char_count = len(cleaned_text)

    return char_count / CHARS_PER_MINUTE


def get_audio_duration_minutes(audio_path: str) -> float:
    """
    Получает реальную длительность MP3 файла в минутах.

    Args:
        audio_path: Путь к MP3 файлу

    Returns:
        Длительность в минутах или 0.0 если файл не найден
    """
    if not os.path.exists(audio_path):
        return 0.0

    try:
        from mutagen.mp3 import MP3
        audio = MP3(audio_path)
        duration_seconds = audio.info.length
        return duration_seconds / 60.0
    except Exception as e:
        print(f"⚠️ Не удалось получить длительность файла {audio_path}: {e}")
        return 0.0


def split_text_by_duration(text: str, max_duration_minutes: int) -> List[str]:
    """
    Разбивает текст на части с учетом максимальной длительности.

    Args:
        text: Исходный текст
        max_duration_minutes: Максимальная длительность одной части в минутах

    Returns:
        Список текстовых частей
    """
    if not text:
        return []

    # Если нет лимита, возвращаем весь текст
    if max_duration_minutes is None:
        return [text]

    # Оцениваем общую длительность
    total_duration = estimate_duration_minutes(text)

    # Если текст укладывается в лимит, возвращаем как есть
    if total_duration <= max_duration_minutes:
        return [text]

    # Рассчитываем максимальное количество символов для одной части
    max_chars_per_part = int(max_duration_minutes * CHARS_PER_MINUTE)

    # Разбиваем текст на чанки с учетом лимита символов
    parts = split_text_into_chunks(text, limit=max_chars_per_part)

    return parts


def format_duration_display(duration_minutes: float) -> str:
    """
    Форматирует длительность для отображения пользователю.

    Args:
        duration_minutes: Длительность в минутах

    Returns:
        Форматированная строка (например, "1ч 23мин" или "45мин")
    """
    if duration_minutes < 1:
        seconds = int(duration_minutes * 60)
        return f"{seconds}сек"

    hours = int(duration_minutes // 60)
    minutes = int(duration_minutes % 60)

    if hours > 0:
        if minutes > 0:
            return f"{hours}ч {minutes}мин"
        else:
            return f"{hours}ч"
    else:
        return f"{minutes}мин"


def calculate_parts_info(text: str, max_duration_minutes: int) -> Tuple[int, float]:
    """
    Рассчитывает информацию о разбиении текста на части.

    Args:
        text: Исходный текст
        max_duration_minutes: Максимальная длительность одной части

    Returns:
        Кортеж (количество частей, длительность одной части в минутах)
    """
    if not text or max_duration_minutes is None:
        return 1, estimate_duration_minutes(text)

    total_duration = estimate_duration_minutes(text)

    if total_duration <= max_duration_minutes:
        return 1, total_duration

    # Рассчитываем количество частей
    parts_count = int(total_duration / max_duration_minutes) + 1
    avg_part_duration = total_duration / parts_count

    return parts_count, avg_part_duration
