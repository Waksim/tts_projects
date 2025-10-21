"""
TTS Service - основная логика синтеза речи
Использует Microsoft Edge TTS API
"""

import asyncio
import os
import time
from typing import List

import edge_tts

# --- КОНФИГУРАЦИЯ СИНТЕЗА ---
VOICE = "ru-RU-DmitryNeural"
DEFAULT_RATE = "+50%"
DEFAULT_PITCH = "+0Hz"
MAX_RETRIES = 3
INITIAL_RETRY_DELAY = 10
CHUNK_CHAR_LIMIT = 3000  # Безопасный лимит символов для одного запроса к API

# --- КОНСТАНТЫ ДЛЯ ВАЛИДАЦИИ ФАЙЛА ---
MIN_BYTES_PER_CHAR = 270
VALIDATION_TOLERANCE = 0.7

# Семафор для ограничения одновременных запросов к API
TTS_SEMAPHORE = asyncio.Semaphore(10)


async def _merge_mp3_parts(part_files: List[str], final_path: str) -> bool:
    """
    Сшивает части MP3 в один файл с помощью ffmpeg и удаляет части.
    """
    print(f"   Сшиваю {len(part_files)} частей в {os.path.basename(final_path)}...")
    list_file_path = f"{final_path}.list.txt"

    try:
        # Создаем временный файл-список для ffmpeg
        with open(list_file_path, 'w', encoding='utf-8') as f:
            for part_file in part_files:
                f.write(f"file '{os.path.abspath(part_file)}'\n")

        # Команда для быстрой и бесшовной конкатенации без перекодирования
        command = [
            'ffmpeg',
            '-y',
            '-f', 'concat',
            '-safe', '0',
            '-i', list_file_path,
            '-c', 'copy',
            final_path
        ]

        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            print(f"❌ Ошибка ffmpeg при сшивке файла {os.path.basename(final_path)}:")
            print(stderr.decode(errors='ignore'))
            return False

        print(f"✅ Файл успешно сшит. Удаляю временные части...")
        return True

    except Exception as e:
        print(f"❌ Критическая ошибка в процессе сшивки: {e}")
        return False
    finally:
        # Гарантированно удаляем временные файлы
        for part_file in part_files:
            if os.path.exists(part_file):
                try:
                    os.remove(part_file)
                except OSError:
                    pass
        if os.path.exists(list_file_path):
            try:
                os.remove(list_file_path)
            except OSError:
                pass


async def _synthesize_single_chunk(
    text: str,
    mp3_path: str,
    voice: str = VOICE,
    rate: str = DEFAULT_RATE,
    pitch: str = DEFAULT_PITCH
) -> bool:
    """
    Надежная функция синтеза одного чанка с повторными попытками и валидацией.
    """
    current_delay = INITIAL_RETRY_DELAY
    for attempt in range(MAX_RETRIES):
        try:
            # Создаем Communicate без стилей (они не поддерживаются edge-tts)
            communicate = edge_tts.Communicate(text=text, voice=voice, rate=rate, pitch=pitch)
            await asyncio.wait_for(communicate.save(mp3_path), timeout=600.0)

            if not os.path.exists(mp3_path):
                raise ValueError("Файл не был создан после сохранения.")

            file_size = os.path.getsize(mp3_path)
            expected_min_size = len(text) * MIN_BYTES_PER_CHAR
            min_required_size = int(expected_min_size * VALIDATION_TOLERANCE)

            if file_size < min_required_size:
                raise ValueError(
                    f"Валидация провалена: размер файла {file_size} Б, < требуемых {min_required_size} Б."
                )

            print(f"✅ Успешно создан и проверен файл: {os.path.basename(mp3_path)}")
            return True

        except Exception as e:
            if os.path.exists(mp3_path):
                try:
                    os.remove(mp3_path)
                except OSError:
                    pass

            print(f"⚠️ Ошибка синтеза (попытка {attempt + 1}/{MAX_RETRIES}): {e}")
            if attempt < MAX_RETRIES - 1:
                print(f"   Повторная попытка через {current_delay} секунд...")
                await asyncio.sleep(current_delay)
                current_delay *= 2
            else:
                print(f"❌ Не удалось синтезировать {os.path.basename(mp3_path)} после {MAX_RETRIES} попыток.")
                return False
    return False


async def synthesize_text(
    text: str,
    output_path: str,
    voice: str = VOICE,
    rate: str = DEFAULT_RATE,
    pitch: str = DEFAULT_PITCH,
    chunk_limit: int = CHUNK_CHAR_LIMIT
) -> bool:
    """
    Основная функция синтеза текста в MP3.
    Автоматически разбивает на чанки, если текст длинный, и сшивает результат.

    Args:
        text: Текст для синтеза
        output_path: Путь для сохранения MP3 файла
        voice: Голос TTS (по умолчанию ru-RU-DmitryNeural)
        rate: Скорость речи (например, "+50%")
        pitch: Высота тона (например, "+0Hz")
        chunk_limit: Максимальный размер одного чанка в символах

    Returns:
        True если синтез успешен, False в противном случае
    """
    from .text_utils import split_text_into_chunks

    start_time = time.monotonic()
    print(f"Начинаю синтез для файла: {os.path.basename(output_path)}")

    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    chunks = split_text_into_chunks(text, chunk_limit)
    if not chunks:
        print("❌ Ошибка: текст пустой или некорректный.")
        return False

    print(f"   Текст разбит на {len(chunks)} частей. Начинаю синтез...")

    # Если один чанк - создаем сразу финальный файл
    if len(chunks) == 1:
        async with TTS_SEMAPHORE:
            success = await _synthesize_single_chunk(chunks[0], output_path, voice, rate, pitch)

        duration = time.monotonic() - start_time
        print(f"Синтез завершен за {duration:.2f} с. Статус: {'Успех' if success else 'Провал'}")
        return success

    # Множество чанков - создаем части и сшиваем
    filename_base = os.path.splitext(os.path.basename(output_path))[0]

    tasks = []
    part_filepaths = []

    for i, chunk_text in enumerate(chunks):
        part_filepath = os.path.join(output_dir, f"{filename_base}_part_{i + 1}.mp3")
        part_filepaths.append(part_filepath)

        async def synthesize_chunk_task(text_to_synth, path):
            async with TTS_SEMAPHORE:
                return await _synthesize_single_chunk(text_to_synth, path, voice, rate, pitch)

        tasks.append(synthesize_chunk_task(chunk_text, part_filepath))

    # Запускаем все задачи конкурентно
    results = await asyncio.gather(*tasks, return_exceptions=True)

    created_parts = []
    all_chunks_succeeded = True
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            print(f"❌ Ошибка в задаче синтеза части {i + 1}: {result}")
            all_chunks_succeeded = False
        elif result is True:
            created_parts.append(part_filepaths[i])
        else:
            all_chunks_succeeded = False

    # Если хотя бы одна часть не удалась, чистим и выходим
    if not all_chunks_succeeded:
        print(f"❌ Синтез провален. Очистка...")
        for part_file in created_parts:
            if os.path.exists(part_file):
                try:
                    os.remove(part_file)
                except OSError:
                    pass
        return False

    # Сшиваем части
    created_parts.sort()
    final_success = await _merge_mp3_parts(created_parts, output_path)

    duration = time.monotonic() - start_time
    status_msg = 'Успех' if final_success else 'Провал'
    print(f"Синтез завершен за {duration:.2f} с. Статус: {status_msg}")

    return final_success


async def synthesize_text_chunks(
    chunks: List[str],
    output_path: str,
    voice: str = VOICE,
    rate: str = DEFAULT_RATE,
    pitch: str = DEFAULT_PITCH
) -> bool:
    """
    Синтезирует уже подготовленные чанки текста.
    Удобно когда чанки подготовлены заранее с особой логикой.
    """
    if not chunks:
        return False

    full_text = "\n\n".join(chunks)
    return await synthesize_text(full_text, output_path, voice, rate, pitch)


async def synthesize_text_with_duration_limit(
    text: str,
    output_base_path: str,
    max_duration_minutes: int = None,
    voice: str = VOICE,
    rate: str = DEFAULT_RATE,
    pitch: str = DEFAULT_PITCH,
    chunk_limit: int = CHUNK_CHAR_LIMIT
) -> List[str]:
    """
    Синтезирует текст с учетом максимальной длительности одного файла.
    Если текст превышает лимит, создает несколько файлов.

    Args:
        text: Текст для синтеза
        output_base_path: Базовый путь для сохранения (будет добавлен _part_N если несколько частей)
        max_duration_minutes: Максимальная длительность одного файла в минутах (None = без лимита)
        voice: Голос TTS
        rate: Скорость речи
        pitch: Высота тона
        chunk_limit: Максимальный размер одного чанка в символах

    Returns:
        Список путей к созданным MP3 файлам (пустой список если синтез не удался)
    """
    from .duration_utils import split_text_by_duration, estimate_duration_minutes

    print(f"Начинаю синтез с лимитом длительности: {max_duration_minutes} мин" if max_duration_minutes else "Начинаю синтез без лимита длительности")

    # Разбиваем текст по лимиту длительности
    text_parts = split_text_by_duration(text, max_duration_minutes)

    if not text_parts:
        print("❌ Ошибка: текст пустой или некорректный.")
        return []

    print(f"   Текст разбит на {len(text_parts)} частей по длительности")

    # Если одна часть, создаем обычный файл
    if len(text_parts) == 1:
        success = await synthesize_text(
            text_parts[0],
            output_base_path,
            voice,
            rate,
            pitch,
            chunk_limit
        )
        return [output_base_path] if success else []

    # Если несколько частей, создаем файлы с суффиксами _part_N
    output_dir = os.path.dirname(output_base_path)
    base_name = os.path.basename(output_base_path)
    name_without_ext = os.path.splitext(base_name)[0]

    created_files = []
    tasks = []

    for i, part_text in enumerate(text_parts, start=1):
        part_filename = f"{name_without_ext}_part_{i}.mp3"
        part_path = os.path.join(output_dir, part_filename)

        # Добавляем задачу на синтез
        async def synthesize_part(text_content, file_path):
            success = await synthesize_text(
                text_content,
                file_path,
                voice,
                rate,
                pitch,
                chunk_limit
            )
            return (file_path, success)

        tasks.append(synthesize_part(part_text, part_path))

    # Запускаем все задачи параллельно
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Собираем успешно созданные файлы
    for result in results:
        if isinstance(result, Exception):
            print(f"❌ Ошибка при синтезе части: {result}")
        elif result[1]:  # success == True
            created_files.append(result[0])
        else:
            print(f"❌ Не удалось синтезировать часть: {result[0]}")

    # Если не все части созданы успешно, удаляем все
    if len(created_files) != len(text_parts):
        print(f"❌ Синтез провален: создано только {len(created_files)} из {len(text_parts)} частей. Очистка...")
        for file_path in created_files:
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except OSError:
                    pass
        return []

    print(f"✅ Успешно создано {len(created_files)} аудио файлов")
    return created_files
