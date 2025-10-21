# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Two independent TTS (Text-to-Speech) applications sharing a common library:
- **telegram_bot/** - Telegram bot that synthesizes text, documents, and web pages
- **web_tts/** - FastAPI web application with browser interface for TTS
- **tts_common/** - Shared library for both projects

All projects use Microsoft Edge TTS API (`edge-tts` package) for speech synthesis.

## Architecture

### Shared Library (tts_common/)

The `tts_common` library is the foundation for both applications. Key architectural decisions:

1. **Parallel Processing**: `tts_service.py` uses a semaphore-based approach to process text chunks concurrently (up to 10 concurrent requests). This significantly reduces synthesis time for long texts.

2. **Text Chunking**: Large texts are split into ~3000 character chunks (in `text_utils.py`) with intelligent boundary detection (respects paragraphs and sentences) to avoid cutting words mid-sentence.

3. **FFmpeg Merging**: When text is split into chunks, individual MP3 parts are merged using FFmpeg's concat demuxer (`-c copy` for fast, lossless merging) in `_merge_mp3_parts()`.

4. **Storage Management**: `StorageManager` automatically deletes oldest audio files when storage exceeds 500MB limit (configurable), sorted by modification time.

5. **Retry Logic**: All TTS operations have exponential backoff retry (3 attempts) to handle transient API failures.

6. **Module Exports**: The `__init__.py` provides a clean public API - always import from `tts_common`, not from individual modules.

### Telegram Bot (telegram_bot/)

Built on aiogram 3.x (async Telegram bot framework):

- **Handlers pattern**: All message/command handlers in `handlers.py` using aiogram Router
- **SQLite history**: Uses SQLAlchemy async ORM with aiosqlite for request tracking
- **FSM States**: `StatesGroup` classes for multi-step dialogs (channel tracking, etc.)
- **Progress updates**: Uses `bot.send_chat_action()` for "typing" and "recording voice" status
- **Owner-only commands**: Some features restricted to `OWNER_ID` (set in config.py)

Key handler flow:
1. `handle_text()` - router that determines if message is URL or plain text
2. `handle_document()` - downloads file, uses `parse_document()`, then synthesizes
3. All handlers save request metadata to SQLite via `save_request()`

### Web TTS (web_tts/)

FastAPI application with Jinja2 templates:

- **Single-file architecture**: Everything in `main.py` (under 200 lines)
- **Lifespan manager**: Creates directories on startup
- **Endpoints**:
  - `GET /` - Main page with form
  - `POST /synthesize` - Accepts text and rate parameter, returns JSON with file_id
  - `GET /audio/{file_id}` - Serves generated MP3
  - `GET /stats` - Storage statistics API
- **No database**: Audio files identified by UUID, no persistent storage of requests

## Development Commands

### Running Locally

```bash
# Install dependencies (from project root)
cd tts_common && pip install -r requirements.txt && cd ..
cd telegram_bot && pip install -r requirements.txt && cd ..
cd web_tts && pip install -r requirements.txt && cd ..

# Run Telegram Bot
cd telegram_bot
python main.py

# Run Web TTS (different terminal)
cd web_tts
python main.py  # Serves on http://0.0.0.0:8001
```

### Testing

No automated tests exist. Manual testing approach:

**Telegram Bot:**
```bash
# Check logs
tail -f telegram_bot/bot.log

# Database inspection
sqlite3 telegram_bot/bot_history.db "SELECT * FROM requests ORDER BY created_at DESC LIMIT 10;"
```

**Web TTS:**
```bash
# Check if running
curl http://localhost:8001

# Storage stats
curl http://localhost:8001/stats
```

### Production Deployment

Uses systemd services (see DEPLOYMENT.md). Key points:

- Service files: `tts-bot.service` and `tts-web.service`
- Logs via journalctl: `sudo journalctl -u tts-bot -f`
- Memory limits enforced in systemd units (MemoryMax=300M for 1GB RAM servers)

```bash
# Restart services after code changes
sudo systemctl restart tts-bot tts-web

# Check status
sudo systemctl status tts-bot tts-web
```

## Critical Configuration

### TTS Parameters (in tts_common/tts_service.py)

```python
VOICE = "ru-RU-DmitryNeural"  # Default Russian male voice
DEFAULT_RATE = "+50%"          # Speech speed
CHUNK_CHAR_LIMIT = 3000        # Max chars per API request
TTS_SEMAPHORE = asyncio.Semaphore(10)  # Concurrent requests
```

**For low-memory servers (1GB RAM)**: Reduce `TTS_SEMAPHORE` to 5 or lower to prevent OOM.

### Storage Limits

Both projects use 500MB default (`MAX_STORAGE_MB`). The `StorageManager` automatically cleans old files but does NOT track which files are currently being served/used, so race conditions are possible under heavy load.

### Bot Token

Located in `telegram_bot/config.py`:
```python
BOT_TOKEN = os.getenv("BOT_TOKEN", "7655332484:AAHHYqmzvlaRiZ1536HnFFpAsRgfo1GUooE")
```

⚠️ This token is hardcoded in config.py. Use `.env` file or environment variable to override in production.

## Important Implementation Details

### FFmpeg Dependency

Both projects **require FFmpeg** to be installed on the system. The code calls `ffmpeg` directly as a subprocess. If FFmpeg is missing, synthesis of texts >3000 chars will fail.

Install: `sudo apt install ffmpeg` (Ubuntu) or `brew install ffmpeg` (macOS)

### File Naming

Audio files use UUID-based names (`{uuid.uuid4()}.mp3`) to prevent collisions. The original text is NOT stored in the filename.

### Text Cleaning (text_utils.py)

The `clean_text_for_tts()` function removes markdown formatting:
- Strips: `#`, `*`, `` ` ``, `[]`, `()`, `>` prefixes
- Removes tables, bullet lists
- This is critical because Edge TTS API pronounces markdown syntax literally

### Document Parser Support

Supported formats (in `document_parser.py`):
- `.txt` - with encoding detection (utf-8, cp1251, latin-1)
- `.docx` - via python-docx
- `.pdf` - via pdfplumber
- `.md` - plain text read
- `.rtf` - via striprtf
- `.epub` - via EbookLib
- `.fb2` - via BeautifulSoup XML parsing

### Async/Await Patterns

Both projects are fully async:
- `telegram_bot` uses aiogram's async handlers
- `web_tts` uses FastAPI's async endpoints
- `tts_common` provides both sync-looking functions that are actually async

When calling TTS functions, always use `await synthesize_text(...)`.

## Common Modifications

### Adding a New Voice

1. Edit `TTS_VOICE` in `telegram_bot/config.py` and `web_tts/main.py`
2. Voice IDs: https://speech.microsoft.com/portal/voicegallery
3. Example: `"en-US-GuyNeural"` for English male voice

### Changing Speed/Pitch

Modify `TTS_RATE` and `TTS_PITCH`:
- Rate: `"-50%"` to `"+100%"` (percentage strings)
- Pitch: `"-10Hz"` to `"+10Hz"` (hertz strings)

### Adding New Document Format

1. Add parser logic to `tts_common/document_parser.py` in `parse_document()`
2. Add extension to `SUPPORTED_EXTENSIONS` list
3. Install required library in `tts_common/requirements.txt`

### Reducing Memory Usage

For deployment on limited RAM:
1. Set `TTS_SEMAPHORE = asyncio.Semaphore(3)` in `tts_service.py`
2. Reduce `MAX_STORAGE_MB` to 250 or lower
3. Add memory limits in systemd service files (`MemoryMax=300M`)

## Known Issues

1. **No authentication**: Both bot and web app are publicly accessible. Web TTS has no rate limiting.
2. **Token exposed**: The bot token is hardcoded in config.py (should use .env exclusively)
3. **No file cleanup race condition**: StorageManager may delete files that are currently being served
4. **No test suite**: Manual testing only
5. **Logs grow unbounded**: No log rotation configured by default

## File Paths to Know

- `telegram_bot/bot.log` - Bot logs (not rotated)
- `telegram_bot/bot_history.db` - SQLite database
- `telegram_bot/audio/` - Generated audio files
- `web_tts/audio/` - Generated audio files
- `web_tts/templates/index.html` - Web UI template

## System Requirements

- Python 3.10+ (uses modern type hints and async features)
- FFmpeg (system package, not Python package)
- 1GB RAM minimum (with optimizations), 2GB recommended
- 12GB disk minimum (500MB per project for audio + OS overhead)
