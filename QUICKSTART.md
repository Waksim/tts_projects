# 🚀 Быстрый старт

Краткое руководство для запуска проектов за 5 минут.

## Предварительные требования

```bash
# Проверьте версии
python3 --version  # >= 3.10
ffmpeg -version    # должен быть установлен
```

Если FFmpeg не установлен:
```bash
# macOS
brew install ffmpeg

# Ubuntu/Debian
sudo apt install ffmpeg
```

## Локальный запуск (для тестирования)

### 1. Telegram Bot

```bash
# Перейдите в директорию
cd tts_projects/telegram_bot

# Создайте виртуальное окружение (опционально)
python3 -m venv venv
source venv/bin/activate  # На Windows: venv\Scripts\activate

# Установите зависимости
pip install -r requirements.txt

# Запустите бота
python main.py
```

✅ Бот запущен! Найдите его в Telegram и отправьте `/start`

### 2. Web TTS

```bash
# Откройте новый терминал
cd tts_projects/web_tts

# Активируйте то же виртуальное окружение или создайте новое
source ../telegram_bot/venv/bin/activate

# Установите зависимости
pip install -r requirements.txt

# Запустите приложение
python main.py
```

✅ Откройте браузер: **https://demo.example.com/local-service

## Развертывание на сервере

### Быстрое развертывание (screen)

```bash
# Подключитесь к серверу
ssh user@your-server

# Скопируйте проекты на сервер (с локальной машины)
scp -r tts_projects user@your-server:~/

# На сервере: установите зависимости
cd ~/tts_projects
python3 -m venv venv
source venv/bin/activate

cd tts_common && pip install -r requirements.txt && cd ..
cd telegram_bot && pip install -r requirements.txt && cd ..
cd web_tts && pip install -r requirements.txt && cd ..

# Запустите в screen
screen -dmS tts-bot bash -c 'cd ~/tts_projects/telegram_bot && source ../venv/bin/activate && python main.py'
screen -dmS tts-web bash -c 'cd ~/tts_projects/web_tts && source ../venv/bin/activate && python main.py'

# Проверьте, что запустилось
screen -ls
```

✅ Оба проекта работают в фоне!

### Полное развертывание (systemd)

Следуйте инструкциям в [DEPLOYMENT.md](DEPLOYMENT.md)

## Использование

### Telegram Bot

1. Найдите бота в Telegram
2. Отправьте `/start`
3. Попробуйте:
   - Отправить текст: `Привет! Это тест озвучки.`
   - Отправить документ (docx, pdf, txt)
   - Отправить ссылку: `https://wikipedia.org/...`

### Web TTS

1. Откройте `http://your-server:8001`
2. Введите текст
3. Настройте скорость (слайдер)
4. Нажмите "Озвучить текст"
5. Прослушайте или скачайте MP3

## Управление

### Просмотр логов

```bash
# Telegram Bot (если запущен как скрипт)
tail -f ~/tts_projects/telegram_bot/bot.log

# Telegram Bot (если systemd)
sudo journalctl -u tts-bot -f

# Web TTS (если systemd)
sudo journalctl -u tts-web -f
```

### Остановка

```bash
# Если используется screen
screen -S tts-bot -X quit
screen -S tts-web -X quit

# Если используется systemd
sudo systemctl stop tts-bot tts-web

# Если запущено в терминале
# Нажмите Ctrl+C
```

### Перезапуск

```bash
# Screen
screen -S tts-bot -X quit && screen -dmS tts-bot bash -c 'cd ~/tts_projects/telegram_bot && python main.py'

# Systemd
sudo systemctl restart tts-bot tts-web
```

## Проверка работоспособности

### Telegram Bot

```bash
# Проверьте процесс
ps aux | grep "python main.py" | grep telegram_bot

# Проверьте логи на ошибки
grep ERROR ~/tts_projects/telegram_bot/bot.log

# Проверьте БД
ls -lh ~/tts_projects/telegram_bot/bot_history.db
```

### Web TTS

```bash
# Проверьте, что слушает порт
netstat -tulpn | grep 8001

# Проверьте HTTP запрос
curl https://demo.example.com/local-service

# Проверьте из браузера
# Откройте: http://your-server-ip:8001
```

## Типичные проблемы

### "ModuleNotFoundError: No module named 'edge_tts'"

```bash
# Активируйте виртуальное окружение
source venv/bin/activate

# Переустановите зависимости
pip install -r requirements.txt
```

### "FileNotFoundError: [Errno 2] No such file or directory: 'ffmpeg'"

```bash
# Установите FFmpeg
sudo apt install ffmpeg  # Linux
brew install ffmpeg      # macOS
```

### "Port 8001 already in use"

```bash
# Найдите процесс
lsof -i :8001

# Убейте процесс
kill -9 <PID>

# Или измените порт в main.py
```

### Бот не отвечает в Telegram

```bash
# Проверьте токен в config.py
grep BOT_TOKEN ~/tts_projects/telegram_bot/config.py

# Проверьте логи
tail -f ~/tts_projects/telegram_bot/bot.log

# Перезапустите бота
```

## Полезные команды

```bash
# Узнать размер аудио директорий
du -sh ~/tts_projects/*/audio

# Очистить аудио (освободить место)
rm -rf ~/tts_projects/telegram_bot/audio/*
rm -rf ~/tts_projects/web_tts/audio/*

# Проверить использование памяти
free -h

# Посмотреть статистику в боте
# Отправьте боту: /stats
```

## Что дальше?

- 📖 Прочитайте [README.md](README.md) для полной документации
- 🚀 Изучите [DEPLOYMENT.md](DEPLOYMENT.md) для production развертывания
- 🏗️ Посмотрите [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md) для понимания архитектуры

## Поддержка

Если что-то не работает:
1. Проверьте логи
2. Убедитесь, что FFmpeg установлен
3. Проверьте, что все зависимости установлены
4. Проверьте наличие свободного места на диске

Успехов! 🎉
