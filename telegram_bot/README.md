# TTS Telegram Bot

Telegram бот для озвучивания текста, документов и веб-статей.

## Возможности

- 📝 **Текст** - отправьте боту текст, получите озвученный MP3
- 📄 **Документы** - поддержка форматов: txt, docx, pdf, md, rtf, epub, fb2
- 🌐 **Веб-страницы** - отправьте ссылку на статью, бот извлечет и озвучит текст
- 💾 **Управление хранилищем** - автоматическое удаление старых файлов (лимит 500 MB)
- 📊 **История запросов** - все действия сохраняются в SQLite
- 🎤 **Качественный голос** - ru-RU-DmitryNeural, скорость +50%

## Быстрый старт

### 1. Установка

```bash
# Клонируйте репозиторий или перейдите в директорию
cd telegram_bot

# Установите зависимости
pip install -r requirements.txt

# Убедитесь, что установлен FFmpeg
ffmpeg -version
```

### 2. Настройка

Токен бота уже настроен в `config.py`. Если хотите изменить:

```bash
cp .env.example .env
nano .env  # Отредактируйте токен
```

### 3. Запуск

```bash
python main.py
```

Бот запущен! Найдите его в Telegram и отправьте `/start`

## Команды бота

- `/start` - Приветственное сообщение и инструкция
- `/help` - Подробная справка по использованию
- `/stats` - Статистика хранилища (объем, количество файлов)

## Использование

### Озвучивание текста
Просто отправьте боту текстовое сообщение:
```
Привет! Это текст для озвучивания.
```

Бот обработает текст и отправит вам MP3 файл.

### Озвучивание документа
Отправьте файл в одном из поддерживаемых форматов:
- `.txt` - текстовые файлы
- `.docx` - документы Word
- `.pdf` - PDF документы
- `.md` - Markdown файлы
- `.rtf` - Rich Text Format
- `.epub` - электронные книги
- `.fb2` - FictionBook

Бот извлечет текст и озвучит его.

### Озвучивание веб-статьи
Отправьте ссылку на статью или веб-страницу:
```
https://example.com/article
```

Бот загрузит страницу, извлечет основной текст и озвучит его.

## Конфигурация

Файл `config.py`:

```python
# Telegram Bot Token
BOT_TOKEN = "ваш_токен"

# Директории
AUDIO_DIR = "audio"  # Директория для аудио файлов
DB_PATH = "bot_history.db"  # Путь к базе данных

# TTS настройки
TTS_VOICE = "ru-RU-DmitryNeural"
TTS_RATE = "+50%"
TTS_PITCH = "+0Hz"

# Хранилище
MAX_STORAGE_MB = 500  # Максимальный размер хранилища

# Лимиты
MAX_TEXT_LENGTH = 50000  # Максимальная длина текста
MAX_FILE_SIZE_MB = 20    # Максимальный размер файла
```

## База данных

Бот сохраняет историю всех запросов в SQLite (`bot_history.db`).

**Структура таблицы `requests`:**
- `id` - уникальный ID запроса
- `user_id` - Telegram ID пользователя
- `username` - имя пользователя
- `request_type` - тип запроса ('text', 'document', 'url')
- `content` - содержимое запроса
- `audio_path` - путь к созданному аудио
- `status` - статус ('success', 'error')
- `error_message` - сообщение об ошибке (если есть)
- `created_at` - время создания

### Просмотр истории

```bash
sqlite3 bot_history.db "SELECT * FROM requests ORDER BY created_at DESC LIMIT 10;"
```

## Логирование

Логи сохраняются в файл `bot.log` и в консоль.

**Уровни логирования:**
- INFO - общая информация
- WARNING - предупреждения
- ERROR - ошибки

**Просмотр логов:**
```bash
tail -f bot.log
```

## Развертывание на сервере

### Systemd Service

Создайте файл `/etc/systemd/system/tts-bot.service`:

```ini
[Unit]
Description=TTS Telegram Bot
After=network.target

[Service]
Type=simple
User=your_user
WorkingDirectory=/path/to/telegram_bot
Environment="PATH=/path/to/venv/bin"
ExecStart=/path/to/venv/bin/python main.py
Restart=always
RestartSec=10
StandardOutput=append:/var/log/tts-bot.log
StandardError=append:/var/log/tts-bot-error.log

[Install]
WantedBy=multi-user.target
```

**Активация:**
```bash
sudo systemctl daemon-reload
sudo systemctl enable tts-bot
sudo systemctl start tts-bot
```

**Управление:**
```bash
# Статус
sudo systemctl status tts-bot

# Перезапуск
sudo systemctl restart tts-bot

# Логи
sudo journalctl -u tts-bot -f
```

## Устранение неполадок

### Бот не запускается
```bash
# Проверьте зависимости
pip install -r requirements.txt

# Проверьте токен
grep BOT_TOKEN config.py

# Проверьте FFmpeg
ffmpeg -version
```

### Бот не отвечает на сообщения
```bash
# Проверьте логи
tail -n 50 bot.log

# Проверьте процесс
ps aux | grep "python main.py"

# Перезапустите бота
sudo systemctl restart tts-bot
```

### Ошибка при обработке документов
- Проверьте формат файла (должен быть в списке поддерживаемых)
- Проверьте размер файла (макс. 20 MB)
- Убедитесь, что установлены все библиотеки для парсинга

### Ошибка при обработке URL
- Проверьте, что URL валиден и доступен
- Проверьте подключение к интернету
- Некоторые сайты могут блокировать автоматический доступ

## Обслуживание

### Очистка старых файлов
Хранилище очищается автоматически. Для ручной очистки:
```bash
rm -rf audio/*
```

### Очистка базы данных
```bash
# Удалить записи старше 30 дней
sqlite3 bot_history.db "DELETE FROM requests WHERE created_at < datetime('now', '-30 days');"

# Оптимизировать БД
sqlite3 bot_history.db "VACUUM;"
```

### Резервное копирование
```bash
# Создать резервную копию БД
cp bot_history.db bot_history_backup_$(date +%Y%m%d).db

# Создать архив аудио файлов
tar -czf audio_backup_$(date +%Y%m%d).tar.gz audio/
```

## Смена голоса

Доступные русские голоса:
- `ru-RU-DmitryNeural` (мужской, по умолчанию)
- `ru-RU-SvetlanaNeural` (женский)

Измените в `config.py`:
```python
TTS_VOICE = "ru-RU-SvetlanaNeural"
```

## Технический стек

- **aiogram 3.x** - фреймворк для Telegram Bot
- **SQLAlchemy** - ORM для работы с БД
- **edge-tts** - синтез речи Microsoft Edge
- **trafilatura** - извлечение текста из веб-страниц
- **pdfplumber** - парсинг PDF
- **python-docx** - парсинг DOCX
- **EbookLib** - парсинг EPUB
- **BeautifulSoup** - парсинг HTML/XML

## Лицензия

MIT License
