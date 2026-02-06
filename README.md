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

### 🛡️ 4. Bulletproof Stability
- **Smart Retries**: If TMDB fails, the bot retries multiple times with backoff.
- **Spam Protection**: Rejects generic names like "Video.mp4" unless a clear description is provided.
- **Health Check**: Verifies AI availability at startup.

---

## 📖 Usage Guide

### Installation
1. Clone the repository.
2. Create `.env` file (see `.env.example`).
3. Install `requirements.txt`.
4. Install **Ollama** and pull a lightweight model (e.g., `llama3` or `mistral`).

### How to Publish
1. **Send a video** to the bot in private.
2. (Optional) Add a **caption** if the filename is garbage.
3. The bot handles the rest: search, poster gen, and publishing.

### Manual Commands
- `/search [Name]` - Manually search for a movie.
- **Manual Correction**: If the bot says "Not found", simply reply to that error message with the correct name (e.g., *"Matrix 1999"*) to retry.

---

## 📂 Estructura del Proyecto

- `cinegram/handlers/`: Lógica de respuestas (Videos, Comandos).
- `cinegram/services/`: Cerebro del bot (TMDB, IA, Generador de Imágenes).
- `cinegram/utils/`: Herramientas de ayuda.

---

*Creado con ❤️ para automatizar lo aburrido.*
