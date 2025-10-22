# GEMINI.md

## Project Overview

This project provides text-to-speech (TTS) functionality through a Telegram bot and a web interface. It utilizes the Microsoft Edge TTS API for speech synthesis and supports a variety of input formats, including plain text, documents (txt, docx, pdf, md, rtf, epub, fb2), and web articles.

The project is structured into three main components:

*   `tts_common/`: A shared library that encapsulates the core TTS logic, document parsing, and web scraping functionalities.
*   `telegram_bot/`: A Telegram bot that allows users to interact with the TTS service. It supports features like voice selection, speech rate adjustment, and automatic audio splitting for long texts.
*   `web_tts/`: A web application that provides a simple interface for TTS conversion, allowing users to input text, adjust speech rate, and download the generated audio.

## Building and Running

### 1. Install Common Library

```bash
cd tts_common
pip install -r requirements.txt
```

### 2. Run the Telegram Bot

```bash
cd telegram_bot
pip install -r requirements.txt
python main.py
```

### 3. Run the Web Application

```bash
cd web_tts
pip install -r requirements.txt
python main.py
```

The web application will be available at `http://0.0.0.0:8001`.

## Development Conventions

*   **Programming Language:** Python 3.10+
*   **Dependencies:** Dependencies are managed using `requirements.txt` files in each component's directory.
*   **Telegram Bot:** The bot is built using the `aiogram` library.
*   **Web Application:** The web application is built with `FastAPI`.
*   **Database:** The Telegram bot uses `SQLAlchemy` with `aiosqlite` for storing user data and request history.
*   **TTS Engine:** The project uses the `edge-tts` library to interact with the Microsoft Edge TTS API.
*   **Deployment:** The `README.md` file provides detailed instructions for deploying the application using `systemd` or `screen`.
