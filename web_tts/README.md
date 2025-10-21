# Web TTS - Веб-приложение для озвучивания текста

Простое и красивое веб-приложение для синтеза речи из текста.

## Возможности

- ✍️ **Ввод текста** - удобный текстовый редактор с подсчетом символов
- ⚡ **Настройка скорости** - слайдер для изменения скорости речи (от -50% до +100%)
- 🎧 **Прослушивание** - встроенный аудиоплеер для прослушивания на сайте
- 💾 **Скачивание** - возможность скачать MP3 файл
- 📊 **Статистика** - отображение использования хранилища
- 🎨 **Темная тема** - автоматическое переключение темной/светлой темы
- 🔄 **Автоочистка** - автоматическое удаление старых файлов (лимит 500 MB)

## Быстрый старт

### 1. Установка

```bash
cd web_tts

# Установите зависимости
pip install -r requirements.txt

# Убедитесь, что установлен FFmpeg
ffmpeg -version
```

### 2. Запуск

```bash
python main.py
```

Приложение будет доступно по адресу: **http://localhost:8001**

## Использование

1. Откройте браузер и перейдите на `http://localhost:8001`
2. Введите текст в текстовое поле
3. Настройте скорость речи с помощью слайдера
4. Нажмите "Озвучить текст"
5. Прослушайте результат или скачайте MP3

## Конфигурация

Файл `main.py` содержит основные настройки:

```python
# Директории
AUDIO_DIR = "audio"  # Директория для аудио файлов

# Хранилище
MAX_STORAGE_MB = 500  # Максимальный размер хранилища

# TTS настройки
TTS_VOICE = "ru-RU-DmitryNeural"
DEFAULT_RATE = "+50%"
TTS_PITCH = "+0Hz"

# Сервер
HOST = "0.0.0.0"  # 0.0.0.0 для доступа с других устройств
PORT = 8001
```

### Изменение порта

```python
# В конце файла main.py
uvicorn.run("main:app", host="0.0.0.0", port=8002, reload=True)
```

### Изменение голоса

```python
TTS_VOICE = "ru-RU-SvetlanaNeural"  # Женский голос
```

Доступные русские голоса:
- `ru-RU-DmitryNeural` (мужской)
- `ru-RU-SvetlanaNeural` (женский)

## API Endpoints

### `GET /`
Главная страница с формой

### `POST /synthesize`
Синтез речи из текста

**Параметры:**
- `text` (form) - текст для озвучивания
- `rate` (form) - скорость речи (например, "+50%")

**Ответ:**
```json
{
    "status": "success",
    "file_id": "uuid-here",
    "message": "Аудио успешно синтезировано"
}
```

### `GET /audio/{file_id}`
Получение аудиофайла

**Параметры:**
- `file_id` - UUID файла

**Ответ:**
MP3 файл

### `GET /stats`
Статистика хранилища

**Ответ:**
```json
{
    "total_size_mb": 123.45,
    "max_size_mb": 500.0,
    "used_percent": 24.7,
    "file_count": 42,
    "available_mb": 376.55
}
```

## Развертывание на сервере

### Systemd Service

Создайте файл `/etc/systemd/system/tts-web.service`:

```ini
[Unit]
Description=TTS Web Application
After=network.target

[Service]
Type=simple
User=your_user
WorkingDirectory=/path/to/web_tts
Environment="PATH=/path/to/venv/bin"
ExecStart=/path/to/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8001
Restart=always
RestartSec=10
StandardOutput=append:/var/log/tts-web.log
StandardError=append:/var/log/tts-web-error.log

[Install]
WantedBy=multi-user.target
```

**Активация:**
```bash
sudo systemctl daemon-reload
sudo systemctl enable tts-web
sudo systemctl start tts-web
```

**Управление:**
```bash
# Статус
sudo systemctl status tts-web

# Перезапуск
sudo systemctl restart tts-web

# Логи
sudo journalctl -u tts-web -f
```

### Использование с Nginx (опционально)

Если нужен reverse proxy:

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:8001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

## Безопасность

### Ограничение доступа по IP

В `main.py` добавьте middleware:

```python
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

ALLOWED_IPS = ["127.0.0.1", "your.server.ip"]

class IPWhitelistMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        client_ip = request.client.host
        if client_ip not in ALLOWED_IPS:
            return HTMLResponse("Access Denied", status_code=403)
        return await call_next(request)

app.add_middleware(IPWhitelistMiddleware)
```

### Базовая аутентификация

Используйте Nginx basic auth или добавьте FastAPI middleware.

## Производительность

### Оптимизация для слабого сервера (1GB RAM)

1. **Ограничьте concurrent запросы** в `tts_common/tts_service.py`:
```python
TTS_SEMAPHORE = asyncio.Semaphore(5)  # Вместо 10
```

2. **Уменьшите лимит хранилища**:
```python
MAX_STORAGE_MB = 250  # Вместо 500
```

3. **Используйте swap**:
```bash
# Создать swap 2GB
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
```

4. **Ограничьте workers uvicorn**:
```python
uvicorn.run("main:app", host="0.0.0.0", port=8001, workers=1)
```

## Мониторинг

### Просмотр использования памяти
```bash
# Общая память
free -h

# Память процесса Python
ps aux | grep uvicorn
```

### Просмотр размера хранилища
```bash
du -sh audio/
```

### Логирование запросов
Все запросы логируются uvicorn в stdout.

## Устранение неполадок

### Приложение не запускается
```bash
# Проверьте зависимости
pip install -r requirements.txt

# Проверьте порт
netstat -tulpn | grep 8001

# Запустите с debug
python main.py
```

### Ошибка 500 при синтезе
```bash
# Проверьте FFmpeg
ffmpeg -version

# Проверьте логи
sudo journalctl -u tts-web -n 50

# Проверьте место на диске
df -h
```

### Медленная работа
- Уменьшите количество concurrent запросов (TTS_SEMAPHORE)
- Увеличьте RAM сервера или добавьте swap
- Очистите старые аудио файлы

## Кастомизация интерфейса

### Изменение цветовой схемы

Отредактируйте `templates/index.html`, секция `<style>`:

```css
:root {
    --button-bg: #your-color;
    --button-hover: #your-hover-color;
    /* и т.д. */
}
```

### Добавление логотипа

```html
<!-- В начале body -->
<div class="logo">
    <img src="/static/logo.png" alt="Logo">
</div>
```

### Изменение текстов

Все тексты находятся в `templates/index.html`.

## Технический стек

- **FastAPI** - веб-фреймворк
- **Uvicorn** - ASGI сервер
- **Jinja2** - шаблонизатор
- **edge-tts** - синтез речи Microsoft Edge
- **Vanilla JavaScript** - без зависимостей на фронтенде

## Лицензия

MIT License
