# TTS Projects - Telegram Bot & Web TTS

Проекты для озвучивания текста с использованием Microsoft Edge TTS API.

## Структура проектов

```
tts_projects/
├── tts_common/           # Общая библиотека для TTS
├── telegram_bot/         # Telegram бот для озвучивания
└── web_tts/              # Веб-приложение для озвучивания
```

## Возможности

### Telegram Bot
- 📝 Озвучивание текстовых сообщений
- 📄 Извлечение и озвучивание текста из документов (txt, docx, pdf, md, rtf, epub, fb2)
- 🌐 Парсинг и озвучивание статей по URL
- ⏱ **НОВОЕ:** Настройка максимальной длительности аудио (автоматическое разбиение на части)
- 🎤 Выбор голоса (Дмитрий, Светлана, Дария)
- 💾 Автоматическое управление хранилищем (лимит 500 MB)
- 📊 История запросов в SQLite
- 📢 Отслеживание и озвучивание каналов Telegram
- ⚡ Скорость речи: +50%

### Web TTS
- ✍️ Ввод текста через веб-интерфейс
- ⚡ Настройка скорости речи (от -50% до +100%)
- 🎧 Прослушивание аудио прямо на сайте
- 💾 Скачивание MP3 файлов
- 📊 Отображение статистики хранилища
- 🔄 Автоматическое удаление старых файлов при превышении лимита

## Требования

### Системные требования
- Python 3.10+
- FFmpeg (для склейки аудио из частей)
- 1 GB RAM (минимум)
- 12 GB SSD (минимум)

### Установка FFmpeg

**Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install ffmpeg
```

**macOS:**
```bash
brew install ffmpeg
```

## Установка и запуск

### 1. Установка общей библиотеки

```bash
cd tts_common
pip install -r requirements.txt
```

### 2. Telegram Bot

```bash
cd telegram_bot

# Установка зависимостей
pip install -r requirements.txt

# Настройка (опционально)
cp .env.example .env
# Отредактируйте .env если нужно изменить токен или настройки

# Запуск
python main.py
```

Бот будет запущен и начнет обрабатывать сообщения.

**Команды бота:**
- `/start` - Приветствие и инструкция
- `/help` - Подробная справка
- `/stats` - Статистика хранилища

### 3. Web TTS

```bash
cd web_tts

# Установка зависимостей
pip install -r requirements.txt

# Запуск
python main.py
```

Веб-приложение будет доступно по адресу: `http://0.0.0.0:8001`

## Развертывание на сервере

### Использование systemd для автозапуска

#### Telegram Bot

Создайте файл `/etc/systemd/system/tts-bot.service`:

```ini
[Unit]
Description=TTS Telegram Bot
After=network.target

[Service]
Type=simple
User=your_user
WorkingDirectory=/path/to/tts_projects/telegram_bot
Environment="PATH=/path/to/venv/bin"
ExecStart=/path/to/venv/bin/python main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Активация:
```bash
sudo systemctl daemon-reload
sudo systemctl enable tts-bot
sudo systemctl start tts-bot
sudo systemctl status tts-bot
```

#### Web TTS

Создайте файл `/etc/systemd/system/tts-web.service`:

```ini
[Unit]
Description=TTS Web Application
After=network.target

[Service]
Type=simple
User=your_user
WorkingDirectory=/path/to/tts_projects/web_tts
Environment="PATH=/path/to/venv/bin"
ExecStart=/path/to/venv/bin/python main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Активация:
```bash
sudo systemctl daemon-reload
sudo systemctl enable tts-web
sudo systemctl start tts-web
sudo systemctl status tts-web
```

### Использование screen (альтернатива)

```bash
# Запуск Telegram Bot
screen -dmS tts-bot bash -c 'cd /path/to/telegram_bot && python main.py'

# Запуск Web TTS
screen -dmS tts-web bash -c 'cd /path/to/web_tts && python main.py'

# Просмотр списка screen сессий
screen -ls

# Подключение к сессии
screen -r tts-bot
screen -r tts-web

# Отключение от сессии (не останавливая): Ctrl+A, затем D
```

## Конфигурация

### Telegram Bot (config.py)

```python
# Telegram
BOT_TOKEN = "your_bot_token"

# TTS настройки
TTS_VOICE = "ru-RU-DmitryNeural"
TTS_RATE = "+50%"
TTS_PITCH = "+0Hz"

# Хранилище
MAX_STORAGE_MB = 500
```

### Web TTS (main.py)

```python
# TTS настройки
TTS_VOICE = "ru-RU-DmitryNeural"
DEFAULT_RATE = "+50%"
TTS_PITCH = "+0Hz"

# Хранилище
MAX_STORAGE_MB = 500

# Сервер
HOST = "0.0.0.0"
PORT = 8001
```

## Логирование

### Telegram Bot
Логи сохраняются в файл `bot.log` в директории бота.

### Web TTS
Логи выводятся в консоль (stdout).

Для сохранения логов в файл при использовании systemd добавьте в service файл:
```ini
StandardOutput=append:/path/to/web_tts.log
StandardError=append:/path/to/web_tts_error.log
```

## Мониторинг

### Проверка статуса сервисов

```bash
# Telegram Bot
sudo systemctl status tts-bot
journalctl -u tts-bot -f

# Web TTS
sudo systemctl status tts-web
journalctl -u tts-web -f
```

### Проверка использования ресурсов

```bash
# Память
free -h

# Диск
df -h

# Процессы Python
ps aux | grep python
```

## Обслуживание

### Обновление кода

```bash
# Остановка сервисов
sudo systemctl stop tts-bot
sudo systemctl stop tts-web

# Обновление кода (git pull или копирование файлов)

# Запуск сервисов
sudo systemctl start tts-bot
sudo systemctl start tts-web
```

### Очистка хранилища

Хранилище очищается автоматически при достижении лимита 500 MB.

Для ручной очистки:
```bash
# Telegram Bot
rm -rf telegram_bot/audio/*

# Web TTS
rm -rf web_tts/audio/*
```

### Очистка логов

```bash
# Telegram Bot
> telegram_bot/bot.log

# Web TTS (если используется journalctl)
sudo journalctl --vacuum-time=7d  # Удалить логи старше 7 дней
```

## Поддерживаемые голоса Microsoft Edge TTS

Для изменения голоса измените параметр `TTS_VOICE`:

**Русские голоса:**
- `ru-RU-DmitryNeural` (мужской, по умолчанию)
- `ru-RU-SvetlanaNeural` (женский)

**Другие языки:**
- `en-US-GuyNeural` (английский, мужской)
- `en-US-JennyNeural` (английский, женский)

Полный список голосов: https://speech.microsoft.com/portal/voicegallery

## Устранение неполадок

### Бот не отвечает
1. Проверьте статус: `sudo systemctl status tts-bot`
2. Проверьте логи: `journalctl -u tts-bot -n 50`
3. Проверьте токен бота в `config.py`
4. Проверьте подключение к интернету

### Web TTS не открывается
1. Проверьте статус: `sudo systemctl status tts-web`
2. Проверьте порт: `netstat -tulpn | grep 8001`
3. Проверьте firewall: `sudo ufw status`
4. Попробуйте открыть: `curl http://localhost:8001`

### Ошибка "No such file or directory: ffmpeg"
Установите FFmpeg:
```bash
sudo apt install ffmpeg
```

### Ошибка импорта модуля
Проверьте установку зависимостей:
```bash
pip install -r requirements.txt
```

### Переполнение диска
1. Проверьте размер аудио директорий
2. Уменьшите `MAX_STORAGE_MB` в конфигурации
3. Очистите старые файлы вручную

## Лицензия

MIT License
