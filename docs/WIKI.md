# 📖 CineGram Wiki

Welcome to the official **CineGram** Wiki. Here you will find detailed documentation on internal mechanics.

---

## 🛠️ Troubleshooting Guide

### 1. Bot checks out but never leaves
- **Cause**: Python process might be hung.
- **Solution**: Check the terminal. Ensure internet connectivity.

### 2. "TMDB Error" or no movies found
- **Cause**: Invalid API Key or TMDB is blocked on your network.
- **Solution**: Verify `TMDB_API_KEY` in `.env`. Restart router if using dynamic IP.

### 3. AI Features not working (Deep Search fails)
- **Cause**: Ollama is not running.
- **Solution**: Open terminal and run `ollama serve`. The bot performs a "Health Check" at startup to warn you.

### 4. Black/Empty Posters
- **Cause**: Timeout downloading image from TMDB.
- **Solution**: The bot has a 10s timeout. If your net is slow, it might fail. Only a black placeholder is used to prevent crashing.

---

## 🧠 Deep Search Logic Explained

CineGram uses a 3-layer system to identify movies:

1.  **Regex Filtering (Fast)**:
    - Uses `guessit` to split "Movie.2024.mp4" into Name and Year.
    - If valid and found on TMDB, stops here.

2.  **Spam Cleaning (Intermediate)**:
    - If name contains "CUEVANA", "LATINO", "1080p", it aggressively strips these terms.

3.  **Artificial Inference (Slow but Precise)**:
    - If all else fails, it sends the filename and caption to **Ollama**.
    - System prompt: *"Act as a movie expert. Extract the real title from this garbage text..."*.
    - AI returns clean JSON: `{"title": "The Matrix", "year": "1999"}`.

---

## 🎨 Smart Poster System

To prevent cropping heads in vertical posters when fitting to horizontal (Youtube/Telegram):

1.  Take original image.
2.  Create 1920x1080 background.
3.  Stretch original to fill background, apply Blur (30px) and Darkening.
4.  Paste original (aspect fit) in center.
5.  Overlay text and logos.

Ensures 100% readability and premium aesthetics.
