#!/bin/bash
# Скрипт запуска Web TTS

echo "Starting Web TTS Application..."

# Проверка виртуального окружения
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Создание директорий
mkdir -p audio
mkdir -p static

# Запуск приложения
echo "Application will be available at https://demo.example.com/local-service"
python main.py
