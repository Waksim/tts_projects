"""
Storage Manager - управление хранилищем аудиофайлов
Автоматически удаляет старые файлы при превышении лимита
"""

import os
import asyncio
from pathlib import Path
from typing import List, Tuple
from datetime import datetime


class StorageManager:
    """
    Менеджер для управления хранилищем аудиофайлов.
    Автоматически очищает старые файлы при превышении лимита.
    """

    def __init__(self, storage_dir: str, max_size_mb: int = 500):
        """
        Args:
            storage_dir: Директория для хранения файлов
            max_size_mb: Максимальный размер хранилища в мегабайтах
        """
        self.storage_dir = Path(storage_dir)
        self.max_size_bytes = max_size_mb * 1024 * 1024  # Конвертируем MB в байты
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def get_directory_size(self) -> int:
        """
        Вычисляет общий размер всех файлов в директории.

        Returns:
            Размер в байтах
        """
        total_size = 0
        for file_path in self.storage_dir.rglob('*'):
            if file_path.is_file():
                try:
                    total_size += file_path.stat().st_size
                except OSError:
                    # Игнорируем файлы, к которым нет доступа
                    pass
        return total_size

    def get_files_sorted_by_age(self) -> List[Tuple[Path, float]]:
        """
        Получает список всех файлов, отсортированных по времени модификации (старые первые).

        Returns:
            Список кортежей (путь_к_файлу, время_модификации)
        """
        files_with_time = []
        for file_path in self.storage_dir.rglob('*'):
            if file_path.is_file():
                try:
                    mtime = file_path.stat().st_mtime
                    files_with_time.append((file_path, mtime))
                except OSError:
                    pass

        # Сортируем по времени модификации (старые первые)
        files_with_time.sort(key=lambda x: x[1])
        return files_with_time

    def cleanup_old_files(self, required_space: int = 0) -> int:
        """
        Удаляет старые файлы, пока размер хранилища не будет меньше лимита.

        Args:
            required_space: Дополнительное место, которое нужно освободить (в байтах)

        Returns:
            Количество удаленных файлов
        """
        current_size = self.get_directory_size()
        target_size = self.max_size_bytes - required_space

        if current_size <= target_size:
            return 0  # Очистка не требуется

        files_sorted = self.get_files_sorted_by_age()
        deleted_count = 0
        freed_space = 0

        print(f"[StorageManager] Текущий размер: {current_size / 1024 / 1024:.2f} MB")
        print(f"[StorageManager] Целевой размер: {target_size / 1024 / 1024:.2f} MB")
        print(f"[StorageManager] Нужно освободить: {(current_size - target_size) / 1024 / 1024:.2f} MB")

        for file_path, mtime in files_sorted:
            if current_size - freed_space <= target_size:
                break

            try:
                file_size = file_path.stat().st_size
                file_path.unlink()
                freed_space += file_size
                deleted_count += 1

                mod_time = datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M:%S')
                print(f"[StorageManager] Удален: {file_path.name} ({file_size / 1024:.2f} KB, {mod_time})")

            except OSError as e:
                print(f"[StorageManager] Не удалось удалить {file_path.name}: {e}")
                continue

        print(f"[StorageManager] Удалено файлов: {deleted_count}, освобождено: {freed_space / 1024 / 1024:.2f} MB")
        return deleted_count

    async def cleanup_old_files_async(self, required_space: int = 0) -> int:
        """
        Асинхронная версия cleanup_old_files.
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.cleanup_old_files, required_space)

    def ensure_space_available(self, required_space: int) -> bool:
        """
        Проверяет и освобождает место для нового файла.

        Args:
            required_space: Требуемое место в байтах

        Returns:
            True если места достаточно или оно было освобождено
        """
        current_size = self.get_directory_size()

        if current_size + required_space <= self.max_size_bytes:
            return True  # Места достаточно

        # Пытаемся освободить место
        self.cleanup_old_files(required_space)

        # Проверяем результат
        new_size = self.get_directory_size()
        return new_size + required_space <= self.max_size_bytes

    async def ensure_space_available_async(self, required_space: int) -> bool:
        """
        Асинхронная версия ensure_space_available.
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.ensure_space_available, required_space)

    def get_storage_stats(self) -> dict:
        """
        Получает статистику хранилища.

        Returns:
            Словарь со статистикой
        """
        current_size = self.get_directory_size()
        files = list(self.storage_dir.rglob('*'))
        file_count = sum(1 for f in files if f.is_file())

        return {
            'total_size_mb': current_size / 1024 / 1024,
            'max_size_mb': self.max_size_bytes / 1024 / 1024,
            'used_percent': (current_size / self.max_size_bytes * 100) if self.max_size_bytes > 0 else 0,
            'file_count': file_count,
            'available_mb': (self.max_size_bytes - current_size) / 1024 / 1024
        }
