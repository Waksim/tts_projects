"""
TTS Common Library
Общая библиотека для синтеза речи, используемая в Telegram Bot и Web TTS
"""

from .tts_service import synthesize_text, synthesize_text_chunks
from .text_utils import clean_text_for_tts, split_text_into_chunks, sanitize_filename, generate_filename_from_text
from .document_parser import parse_document
from .web_parser import parse_url, is_valid_url
from .storage_manager import StorageManager

__all__ = [
    'synthesize_text',
    'synthesize_text_chunks',
    'clean_text_for_tts',
    'split_text_into_chunks',
    'sanitize_filename',
    'generate_filename_from_text',
    'parse_document',
    'parse_url',
    'is_valid_url',
    'StorageManager'
]
