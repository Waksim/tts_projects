# Настройка Google Drive для Web TTS

Это руководство объясняет, как настроить интеграцию с Google Drive для хранения аудиофайлов.

## Зачем это нужно?

- **Экономия места на сервере**: все MP3 файлы хранятся в Google Drive
- **История озвучек**: пользователи могут вернуться и прослушать свои озвучки в течение 7 дней
- **Автоматическая очистка**: старые файлы удаляются автоматически через неделю

---

## Шаг 1: Получение credentials.json

### 1.1 Создание проекта в Google Cloud Console

1. Перейдите на [Google Cloud Console](https://console.cloud.google.com/)
2. Войдите в свой Google аккаунт
3. Создайте новый проект или выберите существующий:
   - Нажмите на выпадающий список проектов (вверху страницы)
   - Нажмите **"New Project"** (Создать проект)
   - Введите название проекта (например, "WebTTS")
   - Нажмите **"Create"** (Создать)

### 1.2 Включение Google Drive API

1. В левом меню выберите **"APIs & Services"** → **"Library"**
2. В поиске введите **"Google Drive API"**
3. Выберите **"Google Drive API"** из результатов
4. Нажмите **"Enable"** (Включить)

### 1.3 Создание OAuth credentials

1. В левом меню выберите **"APIs & Services"** → **"Credentials"**
2. Нажмите **"Create Credentials"** → **"OAuth client ID"**
3. Если появится предупреждение о consent screen:
   - Нажмите **"Configure Consent Screen"**
   - Выберите **"External"** (Внешние пользователи)
   - Заполните обязательные поля:
     - App name: "WebTTS" (или любое имя)
     - User support email: ваш email
     - Developer contact: ваш email
   - Нажмите **"Save and Continue"**
   - На странице **"Scopes"** нажмите **"Save and Continue"**
   - На странице **"Test users"** добавьте свой email в список тестовых пользователей
   - Нажмите **"Save and Continue"**
4. Вернитесь к созданию credentials:
   - **Application type**: выберите **"Desktop app"**
   - **Name**: "WebTTS Client" (или любое имя)
   - Нажмите **"Create"**
5. Скачайте JSON файл:
   - Появится окно с Client ID и Client Secret
   - Нажмите **"Download JSON"**
6. Переименуйте скачанный файл в **`credentials.json`**
7. Положите файл в корень проекта `web_tts/`:
   ```
   web_tts/
   ├── credentials.json  ← сюда
   ├── main.py
   ├── ...
   ```

---

## Шаг 2: Установка зависимостей

```bash
cd web_tts
pip install -r requirements.txt
```

---

## Шаг 3: Создание OAuth токена

### 3.1 Запуск скрипта авторизации

```bash
cd web_tts
python -m google_drive.create_token
```

### 3.2 Процесс авторизации

1. Откроется браузер с окном авторизации Google
2. Войдите в Google аккаунт (который вы добавили в Test Users)
3. Появится предупреждение **"Google hasn't verified this app"**:
   - Нажмите **"Advanced"** (Дополнительно)
   - Нажмите **"Go to WebTTS (unsafe)"** (Перейти в WebTTS)
4. Предоставьте разрешения:
   - Появится список разрешений
   - Нажмите **"Allow"** (Разрешить)
5. Успешная авторизация:
   - В терминале появится сообщение: `✓ Successfully created token.json`
   - Файл `token.json` создан в директории `web_tts/`

---

## Шаг 4: Проверка токена

```bash
python -m google_drive.test_token
```

Должны увидеть:
```
✓ Token is valid!
✓ Successfully connected to Google Drive API!
✓ Your Drive is accessible
```

---

## Шаг 5: Запуск приложения

```bash
python main.py
```

При запуске вы должны увидеть:
```
[GoogleDrive] Service initialized successfully
[INFO] Database initialized
[INFO] Google Drive service initialized
[INFO] Приложение запущено
```

---

## Структура файлов после настройки

```
web_tts/
├── credentials.json         ← OAuth клиент (не коммитить!)
├── token.json              ← Токен доступа (не коммитить!)
├── history.db              ← SQLite база с историей
├── google_drive/
│   ├── __init__.py
│   ├── config.py
│   ├── drive_service.py
│   ├── create_token.py
│   └── test_token.py
├── main.py
└── ...
```

---

## Как это работает?

### 1. Создание озвучки

1. Пользователь вводит текст на сайте
2. Сервер синтезирует MP3 файл локально
3. **Файл загружается в Google Drive** в папку "WebTTS_Audio"
4. Информация сохраняется в SQLite базу (user_id, file_id, drive_file_id, превью текста, дата)
5. Локальный MP3 файл **удаляется сразу после загрузки в Drive**

### 2. Прослушивание озвучки

1. Пользователь открывает вкладку **"История"**
2. Список загружается из базы данных
3. При нажатии на плеер:
   - Проверяется владелец файла (user_id)
   - Проверяется срок давности (< 7 дней)
   - Файл **скачивается из Google Drive**
   - Отдается пользователю

### 3. Автоматическая очистка

- Background task запускается каждые 6 часов
- Находит файлы старше 7 дней в базе данных
- Удаляет файлы из Google Drive
- Удаляет записи из базы данных

---

## Устранение проблем

### Ошибка: "Token file not found"

**Решение**: Запустите `python -m google_drive.create_token`

---

### Ошибка: "invalid_grant" при refresh токена

**Причина**: Токен был отозван или истек срок действия refresh token.

**Решение**:
```bash
rm token.json
python -m google_drive.create_token
```

---

### Ошибка: "Access denied" или 403

**Причина**: Недостаточно прав или scope неправильный.

**Решение**:
1. Проверьте, что в `google_drive/config.py` указан правильный SCOPE:
   ```python
   SCOPES = ['https://www.googleapis.com/auth/drive']
   ```
2. Удалите `token.json` и пересоздайте:
   ```bash
   rm token.json
   python -m google_drive.create_token
   ```

---

### Приложение работает, но файлы не загружаются в Drive

**Проверка**:
1. Откройте [Google Drive](https://drive.google.com/)
2. Найдите папку **"WebTTS_Audio"**
3. Если папки нет, она создастся автоматически при первой загрузке

**Логи**:
Проверьте логи сервера:
```bash
python main.py
```

Должны видеть:
```
[GoogleDrive] Uploading file: <file_id>.mp3
[GoogleDrive] Upload successful: <file_id>.mp3 (ID: <drive_file_id>, Size: <size> bytes)
[Synthesize] Uploaded to Drive and removed local file: <file_id>.mp3
```

---

## Конфигурация

### Изменить срок хранения файлов

По умолчанию файлы хранятся **7 дней**. Чтобы изменить:

**Файл**: `google_drive/config.py`
```python
FILE_RETENTION_DAYS = 14  # Хранить 14 дней
```

### Изменить название папки в Drive

По умолчанию папка называется **"WebTTS_Audio"**. Чтобы изменить:

**Файл**: `google_drive/config.py`
```python
DRIVE_FOLDER_NAME = 'MyCustomFolder'
```

Или через переменную окружения в `.env`:
```bash
DRIVE_FOLDER_NAME=MyCustomFolder
```

### Изменить интервал очистки

По умолчанию очистка запускается **каждые 6 часов**. Чтобы изменить:

**Файл**: `main.py`
```python
# В функции periodic_cleanup()
await asyncio.sleep(12 * 60 * 60)  # Каждые 12 часов
```

---

## Безопасность

### Не коммитить credentials.json и token.json!

Эти файлы уже добавлены в `.gitignore`:
```gitignore
# Google Drive OAuth credentials and tokens
credentials.json
token.json
token.pickle
```

### Проверка перед коммитом:
```bash
git status
```

Не должно быть `credentials.json` или `token.json` в списке файлов для коммита!

---

## FAQ

**Q: Можно ли использовать несколько серверов с одним Google Drive?**
A: Да, но убедитесь, что `token.json` и `credentials.json` одинаковые на всех серверах.

**Q: Что будет, если Google Drive заполнится?**
A: Загрузка новых файлов будет падать с ошибкой. В логах увидите `[GoogleDrive] Error uploading file`. Файлы останутся локально (fallback).

**Q: Можно ли отключить Google Drive и вернуться к локальному хранению?**
A: Да. Просто удалите `token.json`. Приложение продолжит работать без Drive, но история будет недоступна.

**Q: Сколько места занимает в Google Drive?**
A: Примерно 1 MB на 5 минут озвучки. Для 1000 озвучек по 2 минуты = ~400 MB.

---

## Дополнительные ресурсы

- [Google Drive API Documentation](https://developers.google.com/drive/api/guides/about-sdk)
- [OAuth 2.0 для Desktop Apps](https://developers.google.com/identity/protocols/oauth2/native-app)
- [Google Cloud Console](https://console.cloud.google.com/)
