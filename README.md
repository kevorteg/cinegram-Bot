# 🎬 CineGram Bot

**The ultimate automated movie publishing bot for Telegram.**

CineGram is an autonomous assistant that processes video files, identifies the movie (even with typos), fetches official metadata, translates synopses, and generates professional posters.

![Python](https://img.shields.io/badge/Python-3.14-blue?style=flat-square&logo=python)
![Telegram](https://img.shields.io/badge/Telegram-Bot-blue?style=flat-square&logo=telegram)
![Status](https://img.shields.io/badge/Status-Stable-success?style=flat-square)
![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)

---

## 🚀 Key Features

### 🧠 1. CineGram AI (Deep Search)
The bot features a local "Brain" (Ollama) that activates when standard search fails.
- **Spam Detector**: Cleans filenames like *"Movie.Full.Latino.HD.2024.mp4"* to find *"The Matrix"*.
- **Typo Fixer**: Understands inputs like *"Abengers Enfgame"* and searches for *"Avengers: Endgame"*.
- **Safety Net (Fallback)**: If the filename fails, it reads the video "Caption" to infer the movie context.

### 🎨 2. Smart Posters
No more cropped heads.
- **Blurred Background**: Uses a pro design technique where the full poster fits in the center, and the background is filled with a blurred, darkened version of the same image.
- **Cinema Format**: Generates 1920x1080 images ready for high-quality channels.

### 👻 3. Ghost Mode
Keeps your chat and channel clean.
- **Auto-Deletion**: Automatically deletes your uploaded video file from the private chat after successful publishing.
- **Ephemeral Messages**: Status updates ("Searching...", "Generating poster...") self-destruct to avoid clutter.

### � 5. Persistence & Stats (SQLite)
- **Memory**: The bot now uses a **SQLite database** (`cinegram.db`) to remember every movie published. No more duplicates!
- **Admin Stats**: Track your channel growth with real-time reports.
- **Auto-Migration**: Automatically imports your legacy JSON history on first run.

---

## 📖 Usage Guide

### Installation
1. Clone the repository.
2. Create `.env` file (see `.env.example`).
3. Install `requirements.txt`.
    - *New dependency*: `telethon` for history scanning.
4. Install **Ollama** and pull a lightweight model (e.g., `llama3` or `mistral`).

### How to Publish
1. **Send a video** to the bot in private.
2. (Optional) Add a **caption** if the filename is garbage.
3. The bot handles the rest: search, poster gen, and publishing.

### Admin Commands
- `/stats` - View total movies published and authorized users.
- `/today` - List all movies uploaded in the last 24 hours.
- `/search [Name]` - Manually search for a movie.
- **Manual Correction**: If the bot says "Not found", simply reply to that error message with the correct name (e.g., *"Matrix 1999"*) to retry.

---

## � History Scanner (Userbot)

If you have an existing channel with thousands of movies, you can sync them to the bot's database so it remembers them:

1. Obtain `API_ID` and `API_HASH` from [my.telegram.org](https://my.telegram.org).
2. Add them to your `.env` along with your `TELEGRAM_PHONE`.
3. Run the scanner script:
   ```bash
   python scripts/scan_channel.py
   ```
4. Enter the code (and password if requested) sent to your Telegram.
5. Watch as the bot populates its database with your entire history!

---

## 📂 Project Structure

- `cinegram/handlers/`: Logics (Video processing, /stats, /search).
- `cinegram/services/`: Core logic (TMDB, AI, DB, Poster Generator).
- `scripts/`: Maintenance tools (History scanner, Migrations).

---

*Creado con ❤️ para automatizar lo aburrido.*
