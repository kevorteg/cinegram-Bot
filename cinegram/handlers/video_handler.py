from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler, CommandHandler, MessageHandler, filters
from cinegram.services.tmdb_service import TmdbService
from cinegram.services.image_generator import ImageGenerator
from cinegram.config import settings
from cinegram.utils.helpers import schedule_deletion
import logging
import os
import asyncio
import re

logger = logging.getLogger(__name__)

# Concurrency Control
_SEMAPHORE = None

def get_semaphore():
    global _SEMAPHORE
    if _SEMAPHORE is None:
        _SEMAPHORE = asyncio.Semaphore(5)
    return _SEMAPHORE

# --- BATCH SESSION TRACKER ---
_batch_sessions = {}  # chat_id -> {"movies": [...], "task": asyncio.Task}
SUMMARY_DELAY_SECONDS = 3600

async def _send_batch_summary(chat_id: int, bot):
    """Sends a summary of all movies published in the current session."""
    await asyncio.sleep(SUMMARY_DELAY_SECONDS)
    session = _batch_sessions.pop(chat_id, None)
    if not session or not session["movies"]:
        return
    movies = session["movies"]
    movie_list = "\n".join([f"  {i+1}. \U0001f3ac {m}" for i, m in enumerate(movies)])
    
    private_summary = (
        f"\U0001f37f *\u00a1Sesi\u00f3n completada!*\n"
        f"Se publicaron *{len(movies)} pel\u00edcula(s)* en el canal:\n\n"
        f"{movie_list}\n\n"
        f"\u00a1M\u00e1ndame m\u00e1s cuando quieras! \U0001f680"
    )
    
    channel_summary = (
        f"\U0001f4cb *Resumen de hoy:*\n"
        f"Se subieron *{len(movies)} pel\u00edcula(s)* nuevas:\n\n"
        f"{movie_list}\n\n"
        f"\u2796\u2796\u2796\u2796\u2796\u2796\u2796\u2796\n"
        f"*\u00bfQuieres pedir una pel\u00edcula?*\n"
        f"Escr\u00edbenos por los *mensajes directos del canal*.\n"
        f"\U0001f4ab *Costo: 5 Estrellas de Telegram.*\n"
        f"_Nos ayuda a seguir subiendo contenido. \u00a1Gracias!_ \U0001f64f\n\n"
        f"\U0001f3a5 #cinegram"
    )
    
    try:
        await bot.send_message(chat_id=chat_id, text=private_summary, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Failed to send private batch summary: {e}")
    try:
        await bot.send_message(chat_id=settings.CHANNEL_ID, text=channel_summary, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Failed to send channel batch summary: {e}")

def register_publish(chat_id: int, title: str, year: str, bot):
    """Registers a published movie and resets the summary countdown."""
    session = _batch_sessions.setdefault(chat_id, {"movies": [], "task": None})
    session["movies"].append(f"{title} ({year})")
    if session["task"] and not session["task"].done():
        session["task"].cancel()
    session["task"] = asyncio.create_task(_send_batch_summary(chat_id, bot))

def log_failed_movie(title: str, reason: str = ""):
    """Appends a failed movie search to failed_movies.txt for later review."""
    try:
        log_path = os.path.join(settings.BASE_DIR, "failed_movies.txt")
        from datetime import datetime
        entry = f"[{datetime.now().strftime('%Y-%m-%d %H:%M')}] {title}  →  {reason}\n"
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(entry)
    except Exception as e:
        logger.error(f"Could not write failed_movies.txt: {e}")

def _is_english(text: str) -> bool:
    english_words = {"the", "a", "an", "is", "are", "was", "were", "has", "have",
                     "he", "she", "it", "they", "his", "her", "their", "and", "of",
                     "in", "on", "at", "to", "for", "with", "that", "this", "from"}
    words = set(text.lower().split()[:30])
    return len(words & english_words) >= 2

# --- SHARED LOGIC ---

async def process_movie_upload(update: Update, context: ContextTypes.DEFAULT_TYPE, message, video, search_title, extracted_year=None, attempted_ai=False):
    """Processes and publishes a movie automatically."""
    try:
        if not search_title or search_title.lower() == "unknown":
            await message.reply_text("⚠️ No pude reconocer el nombre. Responde a este mensaje con el título correcto.")
            return

        msg_status = await message.reply_text(f"🔍 Buscando: **{search_title}** ({extracted_year or '?'}) ...", parse_mode="Markdown")
        schedule_deletion(context.bot, message.chat_id, msg_status.message_id)

        from cinegram.services.omdb_service import OmdbService
        from cinegram.services.translation_service import TranslationService

        def split_titles(t):
            parts = [t]
            for sep in [" - ", ": ", " | ", " / "]:
                if sep in t:
                    halves = [p.strip() for p in t.split(sep, 1)]
                    parts.extend(halves)
            return list(dict.fromkeys(parts))

        tmdb_data = await asyncio.to_thread(TmdbService.search_movie, search_title, year=extracted_year)
        if not tmdb_data and extracted_year:
            tmdb_data = await asyncio.to_thread(TmdbService.search_movie, search_title)

        if not tmdb_data:
            for candidate in split_titles(search_title)[1:]:
                tmdb_data = await asyncio.to_thread(TmdbService.search_movie, candidate, year=extracted_year)
                if not tmdb_data: tmdb_data = await asyncio.to_thread(TmdbService.search_movie, candidate)
                if tmdb_data: break

        if not tmdb_data:
            en_title = await asyncio.to_thread(TranslationService.translate_to_english, search_title)
            if en_title and en_title.lower() != search_title.lower():
                tmdb_data = await asyncio.to_thread(TmdbService.search_movie, en_title, year=extracted_year)
                if not tmdb_data: tmdb_data = await asyncio.to_thread(TmdbService.search_movie, en_title)

        if not tmdb_data:
            tmdb_data = await asyncio.to_thread(OmdbService.search_movie, search_title, year=extracted_year)

        if not tmdb_data and not attempted_ai:
            from cinegram.services.ai_service import AiService
            ai_data = await asyncio.to_thread(AiService.extract_metadata, message.caption or getattr(video, 'file_name', ''))
            if ai_data:
                await process_movie_upload(update, context, message, video, ai_data['title'], ai_data.get('year'), True)
                return

        if not tmdb_data:
            await message.reply_text(f"🚫 No encontré nada para '*{search_title}*'. Responde con el nombre correcto.")
            log_failed_movie(search_title, "Not found")
            return

        title = tmdb_data.get('title') or "Título Desconocido"
        year = tmdb_data.get('release_date', '')[:4]
        description = tmdb_data.get('overview') or ''
        rating = str(round(tmdb_data.get('vote_average', 0), 1))

        if description and _is_english(description):
            description = await asyncio.to_thread(TranslationService.translate_to_spanish, description) or description

        if tmdb_data.get('source') == 'omdb':
            genre = tmdb_data.get('genre_str', 'Cine')
            poster_url = tmdb_data.get('poster_url')
        else:
            genre = TmdbService.get_genres(tmdb_data.get('genre_ids', []))
            poster_url = TmdbService.get_poster_url(tmdb_data.get('poster_path'))

        if not poster_url or not year:
            await message.reply_text(f"⚠️ Encontré '{title}' pero faltan datos (portada o año).")
            return

        # Duplicate Check
        from cinegram.services.history_service import HistoryService
        tmdb_id = tmdb_data.get('id')
        if HistoryService.is_duplicate(tmdb_id):
            await message.reply_text(f"🛑 **Detenido por Duplicado**.\nPelícula: {title} (ID: {tmdb_id})")
            return

        # Prepare Image
        msg_gen = await message.reply_text(f"🎨 Generando portada para: *{title}*...", parse_mode="Markdown")
        schedule_deletion(context.bot, message.chat_id, msg_gen.message_id)

        try:
            image_path = await asyncio.to_thread(ImageGenerator.generate_poster, poster_url, title, description)
            
            # Analyze Faith
            from cinegram.services.ai_service import AiService
            faith_data = await asyncio.to_thread(AiService.analyze_faith_content, title, description)
            
            # Trailer Search
            trailer_url = await asyncio.to_thread(TmdbService.get_trailer, tmdb_id)

            # Prepare Hashtags
            tags = ["#cinegram"]
            if genre:
                for g in genre.split(','):
                    tags.append(f"#{''.join(word.capitalize() for word in g.strip().split())}")
            if faith_data.get('is_faith'):
                tags.extend(faith_data.get('hashtags', []))
            
            # --- PUBLISHING ---
            synopsis = (description[:500] + "...") if description and len(description) > 500 else (description or "")
            
            caption = (
                f"🎬 *Película:* {title}\n"
                f"📅 *Año:* {year}\n"
                f"🌎 *Idioma:* Latino 🇨🇴🇲🇽\n"
                f"💿 *Calidad:* HD\n"
                f"⭐️ *Calificación:* {rating}\n"
                f"🎭 *Género:* {genre}\n\n"
                f"📝 *Sinopsis:*\n{synopsis}\n\n"
            )
            if faith_data.get('is_faith') and faith_data.get('verse'):
                caption += f"📖 *Versículo inspira:*\n{faith_data['verse']}\n\n"
            
            caption += f"{' '.join(tags)}\n\n"
            caption += f"🔗 *Síguenos en Instagram:*"

            buttons = [[InlineKeyboardButton("📸 Instagram", url=settings.INSTAGRAM_URL)]]
            if trailer_url:
                buttons[0].append(InlineKeyboardButton("🎥 Ver Trailer", url=trailer_url))
            reply_markup = InlineKeyboardMarkup(buttons)

            # Send Photo and Video to Channel
            with open(image_path, 'rb') as photo:
                await context.bot.send_photo(chat_id=settings.CHANNEL_ID, photo=photo)
            
            with open(image_path, 'rb') as thumb:
                await context.bot.send_video(
                    chat_id=settings.CHANNEL_ID,
                    video=video.file_id,
                    caption=caption,
                    parse_mode="Markdown",
                    reply_markup=reply_markup,
                    thumbnail=thumb
                )

            # Success Tasks
            HistoryService.save_movie(tmdb_id, title)
            register_publish(message.chat_id, title, year, context.bot)
            
            msg_ok = await message.reply_text(f"✅ *{title}* publicada con éxito.", parse_mode="Markdown")
            schedule_deletion(context.bot, message.chat_id, msg_ok.message_id, 8)

            # Cleanup
            if os.path.exists(image_path):
                os.remove(image_path)
            try:
                await message.delete()
            except: pass

        except Exception as e:
            logger.error(f"Publishing failed: {e}")
            await message.reply_text(f"❌ Error publicando: {e}")
            if 'image_path' in locals() and os.path.exists(image_path):
                os.remove(image_path)

    except Exception as e:
        logger.error(f"Error in process_movie_upload: {e}", exc_info=True)
        await message.reply_text(f"❌ Error: {e}")

# --- ENTRY POINTS ---

async def video_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    video = message.video or message.document
    if not video: return
    
    filename = getattr(video, 'file_name', '')
    caption = message.caption or ""
    
    # 1. TRUCO: Si el archivo es reenviado, el caption suele tener el nombre real.
    # Limpiamos el caption para quedarnos con el título
    search_title = "Unknown"
    source_year = None
    
    # Heurística: Si hay caption, úsalo primero porque suele ser más limpio en reenvíos
    if caption:
        # Quitamos emojis
        clean_text = re.sub(r'[\U00010000-\U0010ffff]', '', caption)
        clean_text = clean_text.split('\n')[0].strip() # Solo primera línea
        
        # Extraer el año y eliminar caracteres alrededor del año (ej: " - 2024 ", "(2024)")
        year_match = re.search(r'[-_\s\(\[|]*(\d{4})[-_\s\)\]|]*', clean_text)
        if year_match:
            source_year = year_match.group(1)
            clean_text = clean_text.replace(year_match.group(0), " ").strip()
            
        # Remover cualquier guión o separador que haya quedado al final
        clean_text = re.sub(r'[-_|\(\)\[\]]+\s*$', '', clean_text).strip()
        
        if clean_text:
            search_title = clean_text
        logger.info(f"Using caption for search: '{search_title}' ({source_year})")
    # 2. Si el caption falló o es muy corto, prueba con el nombre del archivo
    if len(search_title) < 3 and filename:
        from cinegram.services.filename_parser import FilenameParser
        parsed = FilenameParser.parse_filename(filename)
        if parsed and len(parsed['title']) > 2:
            search_title = parsed['title']
            source_year = parsed['year'] or source_year
            logger.info(f"Fallback to filename: {search_title}")

    async with get_semaphore():
        await process_movie_upload(update, context, message, video, search_title, source_year)

async def handle_manual_correction(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message: return
    user_text = update.message.text.strip()
    original_video_message = update.message.reply_to_message.reply_to_message
    if not original_video_message: return
    
    video = original_video_message.video or original_video_message.document
    if not video: return

    # Extraer año si viene en formato (2024)
    year_match = re.search(r'[-_\s\(\[|]*(\d{4})[-_\s\)\]|]*', user_text)
    year = year_match.group(1) if year_match else None
    
    if year_match:
        title = user_text.replace(year_match.group(0), " ").strip()
    else:
        title = user_text
        
    title = re.sub(r'[-_|\(\)\[\]]+\s*$', '', title).strip()

    async with get_semaphore():
        await process_movie_upload(update, context, update.message, video, title, year)
