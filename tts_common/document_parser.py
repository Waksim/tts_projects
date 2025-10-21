"""
Document Parser - извлечение текста из различных форматов документов
Поддерживает: txt, docx, pdf, md, rtf, epub, fb2
"""

import os
from typing import Optional
import mimetypes


def parse_txt(file_path: str) -> str:
    """Извлекает текст из TXT файла."""
    encodings = ['utf-8', 'cp1251', 'latin-1']

    for encoding in encodings:
        try:
            with open(file_path, 'r', encoding=encoding) as f:
                return f.read()
        except (UnicodeDecodeError, UnicodeError):
            continue

    # Если все кодировки не подошли, читаем с игнорированием ошибок
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        return f.read()


def parse_docx(file_path: str) -> str:
    """Извлекает текст из DOCX файла."""
    try:
        from docx import Document
    except ImportError:
        raise ImportError("Для работы с DOCX файлами установите: pip install python-docx")

    doc = Document(file_path)
    paragraphs = [para.text for para in doc.paragraphs if para.text.strip()]
    return '\n\n'.join(paragraphs)


def parse_pdf(file_path: str) -> str:
    """Извлекает текст из PDF файла."""
    try:
        import pdfplumber
    except ImportError:
        raise ImportError("Для работы с PDF файлами установите: pip install pdfplumber")

    text_parts = []
    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                text_parts.append(text)

    return '\n\n'.join(text_parts)


def parse_markdown(file_path: str) -> str:
    """Извлекает текст из Markdown файла (просто читает как текст)."""
    return parse_txt(file_path)


def parse_rtf(file_path: str) -> str:
    """Извлекает текст из RTF файла."""
    try:
        from striprtf.striprtf import rtf_to_text
    except ImportError:
        raise ImportError("Для работы с RTF файлами установите: pip install striprtf")

    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        rtf_content = f.read()

    return rtf_to_text(rtf_content)


def parse_epub(file_path: str) -> str:
    """Извлекает текст из EPUB файла."""
    try:
        import ebooklib
        from ebooklib import epub
        from bs4 import BeautifulSoup
    except ImportError:
        raise ImportError("Для работы с EPUB файлами установите: pip install EbookLib beautifulsoup4")

    book = epub.read_epub(file_path)
    chapters = []

    for item in book.get_items():
        if item.get_type() == ebooklib.ITEM_DOCUMENT:
            soup = BeautifulSoup(item.get_content(), 'html.parser')
            text = soup.get_text(separator='\n', strip=True)
            if text:
                chapters.append(text)

    return '\n\n'.join(chapters)


def parse_fb2(file_path: str) -> str:
    """Извлекает текст из FB2 файла."""
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        raise ImportError("Для работы с FB2 файлами установите: pip install beautifulsoup4 lxml")

    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()

    soup = BeautifulSoup(content, 'lxml-xml')

    # Находим все параграфы в теле книги
    paragraphs = soup.find_all('p')
    text_parts = [p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True)]

    return '\n\n'.join(text_parts)


def detect_file_type(file_path: str) -> Optional[str]:
    """
    Определяет тип файла по расширению и MIME-type.

    Returns:
        Тип файла: 'txt', 'docx', 'pdf', 'md', 'rtf', 'epub', 'fb2' или None
    """
    # Сначала пробуем по расширению
    ext = os.path.splitext(file_path)[1].lower()

    extension_map = {
        '.txt': 'txt',
        '.docx': 'docx',
        '.pdf': 'pdf',
        '.md': 'md',
        '.markdown': 'md',
        '.rtf': 'rtf',
        '.epub': 'epub',
        '.fb2': 'fb2',
    }

    if ext in extension_map:
        return extension_map[ext]

    # Пробуем определить по MIME-type
    mime_type, _ = mimetypes.guess_type(file_path)
    if mime_type:
        if 'text/plain' in mime_type:
            return 'txt'
        elif 'pdf' in mime_type:
            return 'pdf'
        elif 'wordprocessingml' in mime_type or 'msword' in mime_type:
            return 'docx'
        elif 'rtf' in mime_type:
            return 'rtf'
        elif 'epub' in mime_type:
            return 'epub'

    return None


def parse_document(file_path: str, file_type: Optional[str] = None) -> str:
    """
    Универсальная функция для извлечения текста из документа.

    Args:
        file_path: Путь к файлу
        file_type: Тип файла (опционально, определится автоматически)

    Returns:
        Извлеченный текст

    Raises:
        ValueError: Если формат файла не поддерживается
        FileNotFoundError: Если файл не найден
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Файл не найден: {file_path}")

    # Автоопределение типа файла
    if file_type is None:
        file_type = detect_file_type(file_path)

    if file_type is None:
        raise ValueError(f"Не удалось определить тип файла: {file_path}")

    # Парсинг в зависимости от типа
    parsers = {
        'txt': parse_txt,
        'docx': parse_docx,
        'pdf': parse_pdf,
        'md': parse_markdown,
        'rtf': parse_rtf,
        'epub': parse_epub,
        'fb2': parse_fb2,
    }

    parser = parsers.get(file_type)
    if parser is None:
        raise ValueError(f"Формат '{file_type}' не поддерживается")

    try:
        text = parser(file_path)
        if not text or not text.strip():
            raise ValueError(f"Файл '{file_path}' не содержит текста или текст не удалось извлечь")
        return text
    except ImportError as e:
        raise ImportError(f"Отсутствует необходимая библиотека: {e}")
    except Exception as e:
        raise ValueError(f"Ошибка при парсинге файла '{file_path}': {e}")


# Список поддерживаемых форматов
SUPPORTED_FORMATS = ['txt', 'docx', 'pdf', 'md', 'markdown', 'rtf', 'epub', 'fb2']
SUPPORTED_EXTENSIONS = ['.txt', '.docx', '.pdf', '.md', '.markdown', '.rtf', '.epub', '.fb2']
