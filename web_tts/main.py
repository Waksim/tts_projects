"""
Web TTS - FastAPI приложение для озвучивания текста через веб-интерфейс
"""

import os
import sys
import asyncio
import uuid
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

# Добавляем путь к tts_common
sys.path.insert(0, str(Path(__file__).parent.parent))

from tts_common import synthesize_text, StorageManager

# Конфигурация
BASE_DIR = Path(__file__).parent
AUDIO_DIR = BASE_DIR / "audio"
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"

MAX_STORAGE_MB = 500
MAX_TEXT_LENGTH = 50000

TTS_VOICE = "ru-RU-DmitryNeural"
DEFAULT_RATE = "+50%"
TTS_PITCH = "+0Hz"

# Инициализация менеджера хранилища
storage_manager = StorageManager(str(AUDIO_DIR), MAX_STORAGE_MB)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager для приложения"""
    # Создаем необходимые директории
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    STATIC_DIR.mkdir(parents=True, exist_ok=True)
    print(f"[INFO] Директория для аудио: {AUDIO_DIR}")
    print(f"[INFO] Приложение запущено")
    yield
    print(f"[INFO] Приложение остановлено")


# Создаем FastAPI приложение
app = FastAPI(title="Web TTS", lifespan=lifespan)

# Подключаем статические файлы
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Настраиваем шаблоны
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Главная страница с формой ввода текста"""
    stats = storage_manager.get_storage_stats()

    return templates.TemplateResponse("index.html", {
        "request": request,
        "max_text_length": MAX_TEXT_LENGTH,
        "default_rate": DEFAULT_RATE,
        "storage_stats": stats
    })


@app.post("/synthesize")
async def synthesize(
    text: str = Form(...),
    rate: str = Form(DEFAULT_RATE)
):
    """
    Эндпоинт для синтеза речи.
    Принимает текст и параметр скорости, возвращает путь к аудиофайлу.
    """

    # Валидация текста
    if not text or not text.strip():
        raise HTTPException(status_code=400, detail="Текст не может быть пустым")

    if len(text) > MAX_TEXT_LENGTH:
        raise HTTPException(
            status_code=400,
            detail=f"Текст слишком длинный ({len(text)} символов). Максимум: {MAX_TEXT_LENGTH}"
        )

    # Валидация rate
    try:
        # Парсим rate (формат: "+50%" или "-20%")
        rate_value = int(rate.replace('%', '').replace('+', ''))
        if rate_value < -50 or rate_value > 100:
            raise ValueError()
        # Форматируем обратно
        rate = f"{'+' if rate_value >= 0 else ''}{rate_value}%"
    except:
        raise HTTPException(status_code=400, detail="Некорректное значение скорости")

    # Генерируем уникальное имя файла
    file_id = str(uuid.uuid4())
    audio_filename = f"{file_id}.mp3"
    audio_path = AUDIO_DIR / audio_filename

    # Проверяем и освобождаем место
    estimated_size = len(text) * 300  # Примерная оценка
    await storage_manager.ensure_space_available_async(estimated_size)

    # Синтезируем речь
    try:
        success = await synthesize_text(
            text,
            str(audio_path),
            voice=TTS_VOICE,
            rate=rate,
            pitch=TTS_PITCH
        )

        if not success or not audio_path.exists():
            raise Exception("Не удалось синтезировать аудио")

    except Exception as e:
        # Удаляем файл, если он был создан
        if audio_path.exists():
            audio_path.unlink()
        raise HTTPException(status_code=500, detail=f"Ошибка синтеза: {str(e)}")

    # Возвращаем ID файла
    return {
        "status": "success",
        "file_id": file_id,
        "message": "Аудио успешно синтезировано"
    }


@app.get("/audio/{file_id}")
async def get_audio(file_id: str):
    """
    Эндпоинт для получения аудиофайла.
    """
    # Проверяем, что file_id это UUID (безопасность)
    try:
        uuid.UUID(file_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Некорректный ID файла")

    audio_path = AUDIO_DIR / f"{file_id}.mp3"

    if not audio_path.exists():
        raise HTTPException(status_code=404, detail="Файл не найден")

    return FileResponse(
        path=str(audio_path),
        media_type='audio/mpeg',
        filename='audio.mp3'
    )


@app.get("/stats")
async def get_stats():
    """Эндпоинт для получения статистики хранилища"""
    stats = storage_manager.get_storage_stats()
    return stats


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8001,
        reload=True
    )
