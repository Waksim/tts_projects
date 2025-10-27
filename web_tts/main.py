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

# Google Drive integration
from google_drive import get_drive_service
from database import get_db_manager

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

# Инициализация менеджера хранилища (теперь только для temp файлов)
storage_manager = StorageManager(str(AUDIO_DIR), MAX_STORAGE_MB)

# Инициализация Google Drive и Database (lazy init)
drive_service = None
db_manager = None


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


def get_user_id_from_request(request: Request) -> str:
    """Extract user ID from auth cookie.

    Args:
        request: FastAPI request object

    Returns:
        User ID (hash of auth token)
    """
    auth_token = request.cookies.get(AUTH_COOKIE_NAME, "anonymous")
    # Use hash of auth token as user ID
    user_id = hashlib.sha256(auth_token.encode()).hexdigest()[:16]
    return user_id


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager для приложения"""
    global drive_service, db_manager

    # Создаем необходимые директории
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    STATIC_DIR.mkdir(parents=True, exist_ok=True)

    # Инициализация сервисов
    try:
        drive_service = get_drive_service()
        print(f"[INFO] Google Drive service initialized")
    except Exception as e:
        print(f"[WARNING] Google Drive not available: {e}")
        print(f"[WARNING] Running without Google Drive integration")

    try:
        db_manager = get_db_manager()
        print(f"[INFO] Database initialized")
    except Exception as e:
        print(f"[ERROR] Database initialization failed: {e}")

    print(f"[INFO] Директория для аудио: {AUDIO_DIR}")
    print(f"[INFO] Пригласительный код: {INVITE_CODE}")
    print(f"[INFO] Приложение запущено")

    # Start cleanup task
    cleanup_task = asyncio.create_task(periodic_cleanup())

    yield

    # Cancel cleanup task on shutdown
    cleanup_task.cancel()
    try:
        await cleanup_task
    except asyncio.CancelledError:
        pass

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


# ===== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ =====

async def periodic_cleanup():
    """Background task to cleanup old files from Google Drive and database."""
    from google_drive.config import FILE_RETENTION_DAYS

    # Wait before first cleanup (1 hour after startup)
    await asyncio.sleep(60 * 60)

    while True:
        try:
            if drive_service is None or db_manager is None:
                # If services not available, wait and retry
                await asyncio.sleep(60 * 60)
                continue

            print(f"[Cleanup] Starting periodic cleanup...")

            # Get old records from database
            old_records = db_manager.get_old_records(days=FILE_RETENTION_DAYS)

            deleted_count = 0
            loop = asyncio.get_event_loop()

            for record in old_records:
                try:
                    # Delete from Google Drive (run in executor)
                    success = await loop.run_in_executor(
                        None,
                        drive_service.delete_file,
                        record.drive_file_id
                    )
                    if success:
                        # Delete from database
                        db_manager.delete_record(record.file_id)
                        deleted_count += 1
                except Exception as e:
                    print(f"[Cleanup] Error deleting {record.file_id}: {e}")

            print(f"[Cleanup] Deleted {deleted_count} old files")

            # Run cleanup every 6 hours
            await asyncio.sleep(6 * 60 * 60)

        except asyncio.CancelledError:
            print(f"[Cleanup] Cleanup task cancelled")
            break
        except Exception as e:
            print(f"[Cleanup] Error in cleanup task: {e}")
            # Wait before retry on error
            await asyncio.sleep(60 * 60)


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
    request: Request,
    text: str = Form(...),
    rate: str = Form(DEFAULT_RATE)
):
    """
    Эндпоинт для синтеза речи из текста.
    Принимает текст и параметр скорости, возвращает путь к аудиофайлу.
    """

    # Получаем user_id
    user_id = get_user_id_from_request(request)

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

    # Проверяем и освобождаем место (для temp файла)
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

        # Загружаем в Google Drive (если доступен)
        drive_file_id = None
        if drive_service is not None:
            try:
                # Run upload in executor to avoid blocking event loop
                loop = asyncio.get_event_loop()
                drive_file_id = await loop.run_in_executor(
                    None,
                    drive_service.upload_file,
                    str(audio_path),
                    audio_filename
                )

                if drive_file_id:
                    # Сохраняем в базу данных
                    if db_manager is not None:
                        text_preview = text[:200] if len(text) > 200 else text
                        db_manager.add_audio_record(
                            user_id=user_id,
                            file_id=file_id,
                            drive_file_id=drive_file_id,
                            file_name=audio_filename,
                            text_preview=text_preview,
                            voice=TTS_VOICE,
                            rate=rate
                        )

                    # Удаляем локальный файл после успешной загрузки
                    audio_path.unlink()
                    print(f"[Synthesize] Uploaded to Drive and removed local file: {audio_filename}")

            except Exception as e:
                print(f"[Synthesize] Warning: Could not upload to Drive: {e}")
                # Если не удалось загрузить в Drive, файл остается локально
                # и будет удален через StorageManager

    except Exception as e:
        # Удаляем файл, если он был создан
        if audio_path.exists():
            audio_path.unlink()
        raise HTTPException(status_code=500, detail=f"Ошибка синтеза: {str(e)}")

    # Возвращаем ID файла
    return {
        "status": "success",
        "file_id": file_id,
        "message": "Аудио успешно синтезировано",
        "stored_in_drive": drive_file_id is not None
    }


@app.post("/synthesize_document")
async def synthesize_document(
    request: Request,
    file: UploadFile = File(...),
    rate: str = Form(DEFAULT_RATE)
):
    """
    Эндпоинт для синтеза речи из загруженного документа.
    Принимает файл и параметр скорости, возвращает путь к аудиофайлу.
    """

    # Получаем user_id
    user_id = get_user_id_from_request(request)

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

        # Загружаем в Google Drive (если доступен)
        drive_file_id = None
        if drive_service is not None:
            try:
                # Run upload in executor to avoid blocking event loop
                loop = asyncio.get_event_loop()
                drive_file_id = await loop.run_in_executor(
                    None,
                    drive_service.upload_file,
                    str(audio_path),
                    audio_filename
                )

                if drive_file_id:
                    # Сохраняем в базу данных
                    if db_manager is not None:
                        text_preview = text[:200] if len(text) > 200 else text
                        db_manager.add_audio_record(
                            user_id=user_id,
                            file_id=audio_file_id,
                            drive_file_id=drive_file_id,
                            file_name=audio_filename,
                            text_preview=text_preview,
                            voice=TTS_VOICE,
                            rate=rate
                        )

                    # Удаляем локальный файл после успешной загрузки
                    audio_path.unlink()
                    print(f"[SynthesizeDoc] Uploaded to Drive and removed local file: {audio_filename}")

            except Exception as e:
                print(f"[SynthesizeDoc] Warning: Could not upload to Drive: {e}")

        # Возвращаем ID файла
        return {
            "status": "success",
            "file_id": audio_file_id,
            "message": "Документ успешно озвучен",
            "stored_in_drive": drive_file_id is not None
        }

    except HTTPException:
        raise
    except Exception as e:
        # Удаляем временные файлы при ошибке
        if temp_file_path.exists():
            temp_file_path.unlink()
        raise HTTPException(status_code=500, detail=f"Ошибка обработки документа: {str(e)}")


@app.get("/audio/{file_id}")
async def get_audio(request: Request, file_id: str):
    """
    Эндпоинт для получения аудиофайла.
    Проверяет владельца файла и срок давности.
    """
    # Получаем user_id
    user_id = get_user_id_from_request(request)

    # Проверяем, что file_id это UUID (безопасность)
    try:
        uuid.UUID(file_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Некорректный ID файла")

    # Сначала проверяем локальный файл (fallback для старых файлов)
    audio_path = AUDIO_DIR / f"{file_id}.mp3"

    if audio_path.exists():
        return FileResponse(
            path=str(audio_path),
            media_type='audio/mpeg',
            filename='audio.mp3'
        )

    # Если локального файла нет, пробуем получить из Google Drive
    if db_manager is None or drive_service is None:
        raise HTTPException(status_code=404, detail="Файл не найден")

    # Получаем запись из БД
    record = db_manager.get_record_by_file_id(file_id)

    if record is None:
        raise HTTPException(status_code=404, detail="Файл не найден")

    # Проверяем владельца
    if record.user_id != user_id:
        raise HTTPException(status_code=403, detail="Доступ запрещен")

    # Проверяем срок давности (7 дней)
    from google_drive.config import FILE_RETENTION_DAYS
    from datetime import datetime, timedelta

    age = datetime.utcnow() - record.created_at
    if age > timedelta(days=FILE_RETENTION_DAYS):
        raise HTTPException(status_code=410, detail="Файл устарел и был удален")

    # Получаем файл из Google Drive
    try:
        # Run download in executor to avoid blocking event loop
        loop = asyncio.get_event_loop()
        file_content = await loop.run_in_executor(
            None,
            drive_service.get_file_content,
            record.drive_file_id
        )

        if file_content is None:
            raise HTTPException(status_code=404, detail="Файл не найден в хранилище")

        # Возвращаем файл из памяти
        from fastapi.responses import Response

        return Response(
            content=file_content,
            media_type='audio/mpeg',
            headers={
                'Content-Disposition': f'inline; filename="{record.file_name}"'
            }
        )

    except Exception as e:
        print(f"[GetAudio] Error retrieving file from Drive: {e}")
        raise HTTPException(status_code=500, detail="Ошибка при получении файла")


@app.get("/history")
async def get_history(request: Request, limit: int = 50, offset: int = 0):
    """
    Получить историю озвучек для текущего пользователя.

    Args:
        limit: Максимальное количество записей (по умолчанию 50)
        offset: Смещение для пагинации (по умолчанию 0)

    Returns:
        JSON с историей озвучек
    """
    # Получаем user_id
    user_id = get_user_id_from_request(request)

    if db_manager is None:
        return {
            "status": "error",
            "message": "История недоступна",
            "history": []
        }

    try:
        # Получаем историю из БД
        records = db_manager.get_user_history(user_id, limit=limit, offset=offset)

        # Конвертируем в JSON
        history = [record.to_dict() for record in records]

        return {
            "status": "success",
            "total": len(history),
            "history": history
        }

    except Exception as e:
        print(f"[History] Error retrieving history: {e}")
        raise HTTPException(status_code=500, detail="Ошибка при получении истории")


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
