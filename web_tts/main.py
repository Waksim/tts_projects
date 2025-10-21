"""
Web TTS - FastAPI приложение для озвучивания текста через веб-интерфейс
"""

import os
import sys
import asyncio
import uuid
import hashlib
import secrets
from pathlib import Path
from contextlib import asynccontextmanager
from typing import Optional
from dotenv import load_dotenv

from fastapi import FastAPI, Request, Form, HTTPException, UploadFile, File, Cookie, Response
from fastapi.responses import HTMLResponse, FileResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

# Добавляем путь к tts_common
sys.path.insert(0, str(Path(__file__).parent.parent))

# Загружаем переменные окружения из .env файла
load_dotenv()

from tts_common import synthesize_text, StorageManager, parse_document
from tts_common.document_parser import SUPPORTED_EXTENSIONS

# Конфигурация
BASE_DIR = Path(__file__).parent
AUDIO_DIR = BASE_DIR / "audio"
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"

MAX_STORAGE_MB = 500

TTS_VOICE = "ru-RU-DmitryNeural"
DEFAULT_RATE = "+50%"
TTS_PITCH = "+0Hz"

# Авторизация
INVITE_CODE = os.getenv("WEB_INVITE_CODE", "tts2025secret")  # Пригласительный код

AUTH_COOKIE_NAME = "tts_auth_token"

# Генерируем секретный токен для авторизованных пользователей
AUTH_TOKEN = hashlib.sha256(INVITE_CODE.encode()).hexdigest()

# Инициализация менеджера хранилища
storage_manager = StorageManager(str(AUDIO_DIR), MAX_STORAGE_MB)


# Middleware для проверки авторизации
class AuthMiddleware(BaseHTTPMiddleware):
    """Middleware для проверки авторизации через cookie."""

    async def dispatch(self, request: Request, call_next):
        # Пути, доступные без авторизации
        public_paths = ["/auth", "/login", "/static"]

        # Проверяем, является ли путь публичным
        if any(request.url.path.startswith(path) for path in public_paths):
            return await call_next(request)

        # Проверяем наличие cookie с токеном
        auth_token = request.cookies.get(AUTH_COOKIE_NAME)

        if auth_token != AUTH_TOKEN:
            # Если не авторизован - редирект на страницу авторизации
            return RedirectResponse(url="/auth", status_code=303)

        # Если авторизован - продолжаем обработку
        return await call_next(request)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager для приложения"""
    # Создаем необходимые директории
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    STATIC_DIR.mkdir(parents=True, exist_ok=True)
    print(f"[INFO] Директория для аудио: {AUDIO_DIR}")
    print(f"[INFO] Пригласительный код: {INVITE_CODE}")
    print(f"[INFO] Приложение запущено")
    yield
    print(f"[INFO] Приложение остановлено")


# Создаем FastAPI приложение
app = FastAPI(title="Web TTS", lifespan=lifespan)

# Добавляем middleware для авторизации
app.add_middleware(AuthMiddleware)

# Подключаем статические файлы
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Настраиваем шаблоны
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


# ===== ЭНДПОИНТЫ ДЛЯ АВТОРИЗАЦИИ =====

@app.get("/auth", response_class=HTMLResponse)
async def auth_page(request: Request, error: Optional[str] = None):
    """Страница авторизации с вводом пригласительного кода"""
    return templates.TemplateResponse("auth.html", {
        "request": request,
        "error": error
    })


@app.post("/login")
async def login(request: Request, invite_code: str = Form(...)):
    """Обработка ввода пригласительного кода"""
    if invite_code == INVITE_CODE:
        # Создаем редирект на главную страницу
        response = RedirectResponse(url="/", status_code=303)
        # Устанавливаем cookie с токеном авторизации
        response.set_cookie(
            key=AUTH_COOKIE_NAME,
            value=AUTH_TOKEN,
            httponly=True,
            max_age=60 * 60 * 24 * 365,  # 1 год
            samesite="lax"
        )
        return response
    else:
        # Неверный код - возвращаем на страницу авторизации с ошибкой
        return RedirectResponse(url="/auth?error=invalid", status_code=303)


# ===== ГЛАВНАЯ СТРАНИЦА =====

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Главная страница с формой ввода текста и загрузки документов"""
    stats = storage_manager.get_storage_stats()

    return templates.TemplateResponse("index.html", {
        "request": request,
        "default_rate": DEFAULT_RATE,
        "storage_stats": stats,
        "supported_extensions": ", ".join(SUPPORTED_EXTENSIONS)
    })


@app.post("/synthesize")
async def synthesize(
    text: str = Form(...),
    rate: str = Form(DEFAULT_RATE)
):
    """
    Эндпоинт для синтеза речи из текста.
    Принимает текст и параметр скорости, возвращает путь к аудиофайлу.
    """

    # Валидация текста
    if not text or not text.strip():
        raise HTTPException(status_code=400, detail="Текст не может быть пустым")

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


@app.post("/synthesize_document")
async def synthesize_document(
    file: UploadFile = File(...),
    rate: str = Form(DEFAULT_RATE)
):
    """
    Эндпоинт для синтеза речи из загруженного документа.
    Принимает файл и параметр скорости, возвращает путь к аудиофайлу.
    """

    # Читаем содержимое файла
    file_content = await file.read()
    await file.seek(0)  # Возвращаем указатель в начало

    # Проверяем расширение файла
    file_ext = os.path.splitext(file.filename)[1].lower()
    if file_ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Формат файла '{file_ext}' не поддерживается. Поддерживаемые: {', '.join(SUPPORTED_EXTENSIONS)}"
        )

    # Валидация rate
    try:
        rate_value = int(rate.replace('%', '').replace('+', ''))
        if rate_value < -50 or rate_value > 100:
            raise ValueError()
        rate = f"{'+' if rate_value >= 0 else ''}{rate_value}%"
    except:
        raise HTTPException(status_code=400, detail="Некорректное значение скорости")

    # Сохраняем временный файл
    temp_file_id = str(uuid.uuid4())
    temp_file_path = AUDIO_DIR / f"temp_{temp_file_id}{file_ext}"

    try:
        # Сохраняем загруженный файл
        with open(temp_file_path, "wb") as f:
            f.write(file_content)

        # Извлекаем текст из документа
        try:
            text = parse_document(str(temp_file_path))
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Ошибка при извлечении текста: {str(e)}")

        # Удаляем временный файл
        temp_file_path.unlink()

        if not text or len(text.strip()) < 10:
            raise HTTPException(status_code=400, detail="Документ не содержит достаточно текста для озвучки")

        # Генерируем уникальное имя для аудиофайла
        audio_file_id = str(uuid.uuid4())
        audio_filename = f"{audio_file_id}.mp3"
        audio_path = AUDIO_DIR / audio_filename

        # Проверяем и освобождаем место
        estimated_size = len(text) * 300
        await storage_manager.ensure_space_available_async(estimated_size)

        # Синтезируем речь
        success = await synthesize_text(
            text,
            str(audio_path),
            voice=TTS_VOICE,
            rate=rate,
            pitch=TTS_PITCH
        )

        if not success or not audio_path.exists():
            raise Exception("Не удалось синтезировать аудио")

        # Возвращаем ID файла
        return {
            "status": "success",
            "file_id": audio_file_id,
            "message": "Документ успешно озвучен"
        }

    except HTTPException:
        raise
    except Exception as e:
        # Удаляем временные файлы при ошибке
        if temp_file_path.exists():
            temp_file_path.unlink()
        raise HTTPException(status_code=500, detail=f"Ошибка обработки документа: {str(e)}")


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
