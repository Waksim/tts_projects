"""
TTS Common Library
Общая библиотека для синтеза речи, используемая в Telegram Bot и Web TTS
"""

from .tts_service import synthesize_text, synthesize_text_chunks, synthesize_text_with_duration_limit
from .text_utils import clean_text_for_tts, split_text_into_chunks, sanitize_filename, generate_filename_from_text
from .document_parser import parse_document
from .web_parser import parse_url, is_valid_url
from .storage_manager import StorageManager
from .duration_utils import (
    estimate_duration_minutes,
    get_audio_duration_minutes,
    split_text_by_duration,
    format_duration_display,
    calculate_parts_info
)

__all__ = [
    'synthesize_text',
    'synthesize_text_chunks',
    'synthesize_text_with_duration_limit',
    'clean_text_for_tts',
    'split_text_into_chunks',
    'sanitize_filename',
    'generate_filename_from_text',
    'parse_document',
    'parse_url',
    'is_valid_url',
    'StorageManager',
    'estimate_duration_minutes',
    'get_audio_duration_minutes',
    'split_text_by_duration',
    'format_duration_display',
    'calculate_parts_info'
]
