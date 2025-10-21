#!/bin/bash
# Скрипт запуска Telegram Bot

echo "Starting TTS Telegram Bot..."

# Проверка виртуального окружения
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Проверка зависимостей
if [ ! -f "bot_history.db" ]; then
    echo "First run - initializing database..."
fi

# Создание директории для аудио
mkdir -p audio

# Запуск бота
python main.py
