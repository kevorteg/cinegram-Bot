from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler, CommandHandler, MessageHandler, filters
from cinegram.services.tmdb_service import TmdbService
from cinegram.services.image_generator import ImageGenerator
from cinegram.config import settings
import logging
import os
import asyncio

logger = logging.getLogger(__name__)

# Concurrency Control
_SEMAPHORE = None

def get_semaphore():
    global _SEMAPHORE
    if _SEMAPHORE is None:
        _SEMAPHORE = asyncio.Semaphore(5)
    return _SEMAPHORE

# --- REFACTORED SHARED LOGIC ---

async def process_movie_upload(update: Update, context: ContextTypes.DEFAULT_TYPE, message, video, search_title, extracted_year=None, attempted_ai=False):
    """
    Shared logic to process a movie with a given title/year.
    Used by both automatic video_entry and manual handle_manual_correction.
    """
    
    # Feedback
    msg_status = await message.reply_text(f"🔍 Buscando: **{search_title}** ({extracted_year or '?'}) ...", parse_mode="Markdown")
    schedule_deletion(context.bot, message.chat_id, msg_status.message_id)

    # --- 1. SEARCH TMDB ---
    tmdb_data = TmdbService.search_movie(search_title, year=extracted_year)
    
    # Retry without year if failed
    if not tmdb_data and extracted_year:
         tmdb_data = TmdbService.search_movie(search_title)
    
    # --- 2. VALIDATION ---
    if not tmdb_data:
        # --- FALLBACK: AI DEEP SEARCH (Last Resort) ---
        if not attempted_ai:
             logger.info(f"TMDB failed for '{search_title}'. Attempting AI Fallback...")
             await message.reply_text("🤔 No encontré eso... Probando con **IA (Deep Search)** para leer mejor... 🤖")
             
             # Construct context for AI
             caption = message.caption or ""
             filename = getattr(video, 'file_name', None) or "Unknown"
             text_context = f"Filename: {filename}. Caption: {caption}. Previous search '{search_title}' failed."
             
             from cinegram.services.ai_service import AiService
             ai_data = AiService.extract_metadata(text_context)
             
             if ai_data:
                 new_title = ai_data['title']
                 new_year = ai_data.get('year')
                 logger.info(f"AI Fallback found: {new_title} ({new_year})")
                 
                 # RECURSE with attempted_ai=True to prevent infinite loop
                 await process_movie_upload(
                     update, context, message, video,
                     search_title=new_title,
                     extracted_year=new_year,
                     attempted_ai=True
                 )
                 return

        msg_fail = await message.reply_text(
             f"🚫 **Cancelado:** No encontré nada en TMDB para '{search_title}'.\n"
             "El archivo no se ha publicado.\n\n"
             "👉 **Solución:** Responde a este mensaje con el **Nombre Correcto** (y año opcional) para buscarlo manualmente."
        )
        return

    # Extract Data
    title = tmdb_data.get('title')
    year = tmdb_data.get('release_date', '')[:4]
    poster_path = tmdb_data.get('poster_path')
    description = tmdb_data.get('overview')
    rating = str(round(tmdb_data.get('vote_average', 0), 1))
    genre = TmdbService.get_genres(tmdb_data.get('genre_ids', []))

    if not poster_path or not year:
        msg_inc = await message.reply_text(
             f"🚫 **Incompleto:** Encontré '{title}' pero le falta portada/año. Intenta buscar otra versión."
        )
        schedule_deletion(context.bot, message.chat_id, msg_inc.message_id, 15)
        return

    # --- 3. CONFIG (Single Tenant) ---
    channel_id = settings.CHANNEL_ID
    instagram_url = settings.INSTAGRAM_URL

    # --- 4. GENERATE POSTER ---
    msg_gen = await message.reply_text("🎨 Generando portada...", parse_mode="Markdown")
    schedule_deletion(context.bot, message.chat_id, msg_gen.message_id)

    poster_url = TmdbService.get_poster_url(poster_path)
    # Use output_path definition early to ensure we track it
    image_path = None
    
    try:
        try:
            image_path = ImageGenerator.generate_poster(poster_url, title, description)
        except Exception as e:
            logger.error(f"Poster error: {e}")
            await message.reply_text("❌ Error generando portada.")
            return

        # --- 5. PUBLISH ---
        from telegram.error import RetryAfter

        # Send Photo
        if image_path and os.path.exists(image_path):
            while True:
                try:
                    with open(image_path, 'rb') as photo:
                        await context.bot.send_photo(chat_id=channel_id, photo=photo)
                    break
                except RetryAfter as e:
                    await asyncio.sleep(e.retry_after)
                except Exception:
                    break

        # Prepare Caption
        hashtag_list = []
        if genre:
            g_list = [g.strip() for g in genre.split(',')]
            for g in g_list[:3]:
                clean_tag = "".join(word.capitalize() for word in g.split())
                hashtag_list.append(f"#{clean_tag}")
        hashtags = " ".join(hashtag_list)
        
        caption = (
            f"🎬 *Película:* {title}\n"
            f"📅 *Año:* {year}\n"
            f"🌎 *Idioma:* Latino 🇨🇴🇲🇽\n"
            f"💿 *Calidad:* HD\n"
            f"⭐ *Calificación:* {rating}\n"
            f"🎭 *Género:* {genre}\n\n"
            f"📝 *Sinopsis:*\n{description[:800]}...\n\n"
            f"{hashtags}\n\n"
            f"🔗 *Síguenos en Instagram:*"
        )
        
        keyboard = [[InlineKeyboardButton("📸 Instagram", url=instagram_url)]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        # Send Video
        while True:
            try:
                await context.bot.send_video(chat_id=channel_id, video=video.file_id, caption=caption, parse_mode="Markdown", reply_markup=reply_markup)
                break
            except RetryAfter as e:
                msg_w = await message.reply_text(f"⏳ Esperando {e.retry_after}s (Flood Control)...")
                schedule_deletion(context.bot, message.chat_id, msg_w.message_id, e.retry_after)
                await asyncio.sleep(e.retry_after)
            except Exception as e:
                await message.reply_text(f"❌ Error enviando video: {e}")
                return

        # Success
        msg_ok = await message.reply_text(f"✅ **Publicado:** {title} ({year})")
        schedule_deletion(context.bot, message.chat_id, msg_ok.message_id, 10)
        
        # Clean up User's Video Message (Ghost Mode)
        try:
            await message.delete()
        except Exception as e:
            logger.warning(f"Could not delete user message: {e}")

    finally:
        # Cleanup Temp Image
        if image_path and os.path.exists(image_path):
            try:
                os.remove(image_path)
                logger.info(f"Cleaned up temp image: {image_path}")
            except Exception as e:
                logger.error(f"Failed to cleanup image {image_path}: {e}")


# --- ENTRY POINTS ---

async def video_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Automatic entry point for video files."""
    message = update.message
    video = message.video or message.document
    
    if not video: return

    file_id = video.file_id
    filename = getattr(video, 'file_name', None) or "Unknown.mp4"
    caption = message.caption or ""
    
    # --- STRATEGY 1: Parse Filename ---
    from cinegram.services.filename_parser import FilenameParser
    parsed_data = FilenameParser.parse_filename(filename)
    
    source_title = parsed_data['title'] if parsed_data else "Unknown"
    source_year = parsed_data['year'] if parsed_data else None

    # --- STRATEGY 2: Check Caption (Fallback) ---
    is_generic = False
    if source_title.lower() in ["unknown", "video", "whatsapp video", "vid"]:
        is_generic = True
    
    # Check for spammy titles that Guessit failed to clean
    spam_keywords = ["online", "pelicula", "completa", "homecine", "estreno", "cuevana", "latino", "castellano", "descargar"]
    if any(keyword in source_title.lower() for keyword in spam_keywords):
        is_generic = True
        logger.info(f"Title contains spam keywords: {source_title}")

    # Also check if filename looks like a date (common in whatsapp)
    if not is_generic and len(source_title) < 4: 
        is_generic = True

    if is_generic and caption:
        # If filename is bad but we have caption, prefer caption
        # Simple clean of caption (first line usually)
        clean_caption = caption.split('\n')[0].strip()
        if len(clean_caption) > 3:
             source_title = clean_caption
             # Reset year as we are unsure
             source_year = None
             logger.info(f"Fallback to caption: {source_title}")

    # --- STRATEGY 3: AI Deep Search (Ollama) ---
    # Trigger if generic/spammy.
    # We pass the Caption (if exists) OR the original Filename (if caption is empty) to the AI.
    
    if is_generic:
         # Algorithm: Use Caption if available, otherwise use Filename (to let AI clean the spammy filename)
         text_context = ""
         if caption:
             text_context = f"Caption: {caption}"
         else:
             text_context = f"Filename: {filename}" # AI needs the raw filename to clean it if no caption
         
         await message.reply_text("🤖 **Analizando con IA...** (Deep Search)", parse_mode="Markdown")
         
         from cinegram.services.ai_service import AiService
         ai_data = AiService.extract_metadata(text_context)
         
         if ai_data:
             source_title = ai_data['title']
             source_year = ai_data.get('year')
             logger.info(f"AI found: {source_title} ({source_year})")
         else:
             logger.warning("AI could not extract data.")

    
    if not source_title or source_title.lower() == "unknown":
        await message.reply_text("⚠️ **No pude reconocer la película.**\nEl archivo y la descripción no son claros.\n\n👉 **Fuerza la búsqueda** respondiendo con el nombre exacto.")
        return

    # Call Shared Logic
    # Call Shared Logic
    # Use Semaphore to limit concurrency
    async with get_semaphore():
        await process_movie_upload(
            update, context, message, video, 
            search_title=source_title, 
            extracted_year=source_year
        )

async def handle_manual_correction(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handles text replies to bot error messages.
    """
    message = update.message
    user_text = message.text.strip()
    
    # 1. Validation: Must be a reply to the bot
    if not message.reply_to_message or message.reply_to_message.from_user.id != context.bot.id:
        return 

    # 2. Validation: The bot's message must be an error/cancellation message
    bot_text = message.reply_to_message.text or ""
    if "No encontré nada" not in bot_text and "Solución" not in bot_text and "Cancelado" not in bot_text:
        return 

    # 3. Find the ORIGINAL Video Message
    original_video_message = message.reply_to_message.reply_to_message
    
    if not original_video_message:
        await message.reply_text("⚠️ No puedo encontrar el video original. Por favor reenvía el video.")
        return
        
    video = original_video_message.video or original_video_message.document
    if not video:
        await message.reply_text("⚠️ El mensaje original no parece tener un video.")
        return

    # 4. Trigger Processing with NEW Title
    import re
    year_match = re.search(r'\((\d{4})\)', user_text)
    year = year_match.group(1) if year_match else None
    search_title = re.sub(r'\(\d{4}\)', '', user_text).strip()
    
    await message.reply_text(f"🔄 **Reintentando con:** {search_title} ...")
    
    async with get_semaphore():
        await process_movie_upload(
            update, context, message, video, 
            search_title=search_title, 
            extracted_year=year
        )
