"""
Web Parser - извлечение текста из веб-страниц и статей
Использует trafilatura для извлечения основного контента
"""

import re
from typing import Optional
from urllib.parse import urlparse


def is_valid_url(url: str) -> bool:
    """Проверяет, является ли строка валидным URL."""
    try:
        result = urlparse(url)
        return all([result.scheme in ('http', 'https'), result.netloc])
    except Exception:
        return False


def parse_url(url: str, include_comments: bool = False) -> str:
    """
    Извлекает основной текст из веб-страницы.

    Args:
        url: URL веб-страницы
        include_comments: Включать ли комментарии (по умолчанию False)

    Returns:
        Извлеченный текст

    Raises:
        ValueError: Если URL невалиден или не удалось извлечь текст
        ImportError: Если отсутствует необходимая библиотека
    """
    try:
        import trafilatura
    except ImportError:
        raise ImportError("Для работы с веб-страницами установите: pip install trafilatura")

    if not is_valid_url(url):
        raise ValueError(f"Невалидный URL: {url}")

    try:
        # Загружаем страницу
        downloaded = trafilatura.fetch_url(url)
        if not downloaded:
            raise ValueError(f"Не удалось загрузить страницу: {url}")

        # Извлекаем текст
        text = trafilatura.extract(
            downloaded,
            include_comments=include_comments,
            include_tables=False,
            no_fallback=False
        )

        if not text or not text.strip():
            raise ValueError(f"Не удалось извлечь текст из страницы: {url}")

        return text

    except Exception as e:
        if isinstance(e, (ValueError, ImportError)):
            raise
        raise ValueError(f"Ошибка при обработке URL '{url}': {e}")


async def parse_url_async(url: str, include_comments: bool = False) -> str:
    """
    Асинхронная версия parse_url.
    Использует asyncio для неблокирующей загрузки.
    """
    import asyncio
    from concurrent.futures import ThreadPoolExecutor

    # Т.к. trafilatura синхронный, запускаем его в пуле потоков
    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor() as pool:
        return await loop.run_in_executor(
            pool,
            parse_url,
            url,
            include_comments
        )


def extract_urls_from_text(text: str) -> list[str]:
    """
    Извлекает все URL из текста.

    Returns:
        Список найденных URL
    """
    url_pattern = r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
    urls = re.findall(url_pattern, text)
    return [url for url in urls if is_valid_url(url)]
