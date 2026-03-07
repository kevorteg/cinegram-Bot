from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler, CommandHandler, MessageHandler, filters
from cinegram.services.tmdb_service import TmdbService
from cinegram.services.image_generator import ImageGenerator
from cinegram.config import settings
from cinegram.utils.helpers import schedule_deletion
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

# --- BATCH SESSION TRACKER ---
# Tracks movies published in a single session to send a final summary.
_batch_sessions = {}  # chat_id -> {"movies": [...], "task": asyncio.Task}

SUMMARY_DELAY_SECONDS = 3600  # 1 hora de inactividad antes de enviar el resumen

async def _send_batch_summary(chat_id: int, bot):
    """Sends a summary of all movies published in the current session."""
    await asyncio.sleep(SUMMARY_DELAY_SECONDS)
    session = _batch_sessions.pop(chat_id, None)
    if not session or not session["movies"]:
        return
    movies = session["movies"]
    movie_list = "\n".join([f"  {i+1}. \U0001f3ac {m}" for i, m in enumerate(movies)])
    # Summary for the admin's private chat
    private_summary = (
        f"\U0001f37f *\u00a1Sesi\u00f3n completada!*\n"
        f"Se publicaron *{len(movies)} pel\u00edcula(s)* en el canal:\n\n"
        f"{movie_list}\n\n"
        f"\u00a1M\u00e1ndame m\u00e1s cuando quieras! \U0001f680"
    )
    # Summary for the channel
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
        from cinegram.config import settings
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
        from cinegram.config import settings
        log_path = os.path.join(settings.BASE_DIR, "failed_movies.txt")
        from datetime import datetime
        entry = f"[{datetime.now().strftime('%Y-%m-%d %H:%M')}] {title}  →  {reason}\n"
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(entry)
    except Exception as e:
        logger.error(f"Could not write failed_movies.txt: {e}")


def _is_english(text: str) -> bool:
    """Quick heuristic: checks if text is likely English based on common stopwords."""
    english_words = {"the", "a", "an", "is", "are", "was", "were", "has", "have",
                     "he", "she", "it", "they", "his", "her", "their", "and", "of",
                     "in", "on", "at", "to", "for", "with", "that", "this", "from"}
    words = set(text.lower().split()[:30])
    return len(words & english_words) >= 2

# --- REFACTORED SHARED LOGIC ---

async def process_movie_upload(update: Update, context: ContextTypes.DEFAULT_TYPE, message, video, search_title, extracted_year=None, attempted_ai=False):
    """
    Shared logic to process a movie with a given title/year.
    Used by both automatic video_entry and manual handle_manual_correction.
    """
    
    # --- 0. SAFETY NET ---
    try:
        # Feedback
        msg_status = await message.reply_text(f"🔍 Buscando: **{search_title}** ({extracted_year or '?'}) ...", parse_mode="Markdown")
        schedule_deletion(context.bot, message.chat_id, msg_status.message_id)

        # --- 1. SEARCH CHAIN: TMDB → Subtitle Split → English Translation → OMDb → AI ---

        import re
        from cinegram.services.omdb_service import OmdbService
        from cinegram.services.translation_service import TranslationService

        # Helper: split bilingual titles like "DARK HABITS - ENTRE TINIEBLAS"
        def split_titles(t):
            """Returns list of title candidates by splitting on separators."""
            parts = [t]
            for sep in [" - ", ": ", " | ", " / "]:
                if sep in t:
                    halves = [p.strip() for p in t.split(sep, 1)]
                    parts.extend(halves)
            return list(dict.fromkeys(parts))  # deduplicate, preserve order

        # Step 1: TMDB with original title
        tmdb_data = await asyncio.to_thread(TmdbService.search_movie, search_title, year=extracted_year)

        # Step 1b: TMDB without year
        if not tmdb_data and extracted_year:
            tmdb_data = await asyncio.to_thread(TmdbService.search_movie, search_title)

        # Step 2: TMDB with subtitle variants (e.g. strip "- ENTRE TINIEBLAS")
        if not tmdb_data:
            for candidate in split_titles(search_title)[1:]:  # skip first (already tried)
                logger.info(f"Trying subtitle split: '{candidate}'")
                tmdb_data = await asyncio.to_thread(TmdbService.search_movie, candidate, year=extracted_year)
                if not tmdb_data:
                    tmdb_data = await asyncio.to_thread(TmdbService.search_movie, candidate)
                if tmdb_data:
                    logger.info(f"TMDB found via subtitle split '{candidate}'")
                    break

        # Step 3: Translate title to English, then retry TMDB
        if not tmdb_data:
            en_title = await asyncio.to_thread(TranslationService.translate_to_english, search_title)
            if en_title and en_title.lower() != search_title.lower():
                logger.info(f"Retrying TMDB with English title: '{en_title}'")
                tmdb_data = await asyncio.to_thread(TmdbService.search_movie, en_title, year=extracted_year)
                if not tmdb_data:
                    tmdb_data = await asyncio.to_thread(TmdbService.search_movie, en_title)
                # Also try subtitle splits of English title
                if not tmdb_data:
                    for candidate in split_titles(en_title)[1:]:
                        tmdb_data = await asyncio.to_thread(TmdbService.search_movie, candidate)
                        if tmdb_data:
                            break
                if tmdb_data:
                    logger.info(f"TMDB found via English translation")

        # Store the English title for OMDb step
        en_title_for_omdb = locals().get("en_title", search_title)

        # --- 2. VALIDATION + FALLBACK CHAIN ---
        if not tmdb_data:
            # Step 4: OMDb with original AND English title
            logger.info(f"All TMDB attempts failed. Trying OMDb...")
            omdb_status = await message.reply_text("🔍 Probando en OMDb (base de datos alternativa)...", parse_mode="Markdown")
            schedule_deletion(context.bot, message.chat_id, omdb_status.message_id, 5)
            tmdb_data = await asyncio.to_thread(OmdbService.search_movie, search_title, year=extracted_year)
            if not tmdb_data and en_title_for_omdb != search_title:
                tmdb_data = await asyncio.to_thread(OmdbService.search_movie, en_title_for_omdb, year=extracted_year)
            if tmdb_data:
                logger.info(f"OMDb found: {tmdb_data.get('title')}")


        if not tmdb_data:
            # --- FALLBACK 2: AI DEEP SEARCH (Last Resort) ---
            if not attempted_ai:
                 logger.info(f"OMDb also failed for '{search_title}'. Attempting AI Fallback...")
                 await message.reply_text("🤔 No encontré eso... Probando con **IA (Deep Search)** para leer mejor... 🤖", parse_mode="Markdown")
                 
                 # Construct context for AI
                 caption = message.caption or ""
                 filename = getattr(video, 'file_name', None) or "Unknown"
                 text_context = f"Filename: {filename}. Caption: {caption}. Previous search '{search_title}' failed."
                 
                 from cinegram.services.ai_service import AiService
                 ai_data = await asyncio.to_thread(AiService.extract_metadata, text_context)
                 
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
                 f"🚫 **Cancelado:** No encontré nada en TMDB ni OMDb para '*{search_title}*'.\n"
                 "El archivo no se ha publicado.\n\n"
                 "👉 **Solución:** Responde a este mensaje con el **Nombre Correcto** (y año opcional) para buscarlo manualmente.",
                 parse_mode="Markdown"
            )
            # Feature 4: log the failure for /failed review
            log_failed_movie(search_title, "Not found in TMDB, OMDb, or AI")
            return

        # Extract Data — handle both TMDB and OMDb formats
        title = tmdb_data.get('title')
        year = tmdb_data.get('release_date', '')[:4]
        description = tmdb_data.get('overview') or ''
        rating = str(round(tmdb_data.get('vote_average', 0), 1))

        # Feature 3: Auto-translate synopsis to Spanish if English is detected
        if description and _is_english(description):
            from cinegram.services.translation_service import TranslationService as TS
            translated_desc = await asyncio.to_thread(TS.translate_to_spanish, description)
            if translated_desc:
                description = translated_desc

        # Genre: OMDb gives a string directly; TMDB gives genre_ids
        if tmdb_data.get('source') == 'omdb':
            genre = tmdb_data.get('genre_str', 'Cine')
            poster_path = None
            poster_url_direct = tmdb_data.get('poster_url')  # Direct URL
        else:
            genre = TmdbService.get_genres(tmdb_data.get('genre_ids', []))
            poster_path = tmdb_data.get('poster_path')
            poster_url_direct = TmdbService.get_poster_url(poster_path) if poster_path else None

        if not poster_url_direct or not year:
            msg_inc = await message.reply_text(
                 f"🚫 **Incompleto:** Encontré '*{title}*' pero le falta portada/año. Intenta buscar otra versión.",
                 parse_mode="Markdown"
            )
            schedule_deletion(context.bot, message.chat_id, msg_inc.message_id, 15)
            return

        # --- 3. DUPLICATE CHECK (History) ---
        from cinegram.services.history_service import HistoryService
        tmdb_id = tmdb_data.get('id')
        
        # Check if duplicate
        if HistoryService.is_duplicate(tmdb_id):
            await message.reply_text(f"⚠️ **Posible Duplicado:** Ya subiste '{title}' anteriormente. (ID: {tmdb_id})")
            # Optimization: We continue but warn. Or we could stop. User asked to "no se repitan".
            # Let's ask: Force user to confirm? No, for now just WARN strong.
            # Actually user said "no se repitan" (do not repeat). So we should probably STOP or ask confirmation.
            # To avoid complex conversation state, let's STOP and ask to force with manual search if really needed.
            await message.reply_text(f"🛑 **Detenido por Duplicado**.\nSi realmente quieres resubirla, usa el comando `/search {title}` o responde con el nombre manual.")
            return

        # --- 4. CONFIG (Single Tenant) ---
        channel_id = settings.CHANNEL_ID
        instagram_url = settings.INSTAGRAM_URL

        # --- 5. GENERATE POSTER ---
        msg_gen = await message.reply_text("🎨 Generando portada...", parse_mode="Markdown")
        schedule_deletion(context.bot, message.chat_id, msg_gen.message_id)

        # poster_url_direct already resolved above for both TMDB and OMDb
        image_path = None
        
        try:
            try:
                image_path = await asyncio.to_thread(ImageGenerator.generate_poster, poster_url_direct, title, description)
            except Exception as e:
                logger.error(f"Poster error: {e}")
                await message.reply_text("❌ Error generando portada.")
                return

            # --- 6. FAITH ANALYSIS ---
            from cinegram.services.ai_service import AiService
            faith_data = await asyncio.to_thread(AiService.analyze_faith_content, title, description)
            
            # --- 7. PUBLISH ---
            from telegram.error import RetryAfter

            # Build full caption with all movie info
            hashtag_list = ["#cinegram"]
            if genre:
                for g in [g.strip() for g in genre.split(',')]:
                    clean_tag = "".join(word.capitalize() for word in g.split())
                    hashtag_list.append(f"#{clean_tag}")
            
            # Add faith hashtags if applicable
            if faith_data.get('is_faith'):
                for tag in faith_data.get('hashtags', []):
                    if tag not in hashtag_list:
                        hashtag_list.append(tag)
            
            hashtags = " ".join(hashtag_list)

            synopsis = (description[:500] + "...") if description and len(description) > 500 else (description or "")

            # Format Rating with Star emoji
            rating_str = f"{rating}"

            caption = (
                f"🎬 *Película:* {title}\n"
                f"📅 *Año:* {year}\n"
                f"🌎 *Idioma:* Latino 🇨🇴🇲🇽\n"
                f"💿 *Calidad:* HD\n"
                f"⭐️ *Calificación:* {rating_str}\n"
                f"🎭 *Género:* {genre}\n\n"
                f"📝 *Sinopsis:*\n{synopsis}\n\n"
            )

            if faith_data.get('is_faith') and faith_data.get('verse'):
                caption += f"📖 *Versículo inspira:*\n{faith_data['verse']}\n\n"

            caption += f"{hashtags}\n\n"
            caption += f"🔗 *Síguenos en Instagram:*"

            # Send Poster Photo first (separate message)
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

            keyboard = [[InlineKeyboardButton("📸 Instagram", url=instagram_url)]]
            reply_markup = InlineKeyboardMarkup(keyboard)


            # Send Video with Thumbnail
            if image_path and os.path.exists(image_path):
                thumb_file = open(image_path, 'rb')
            else:
                thumb_file = None

            while True:
                try:
                    await context.bot.send_video(
                        chat_id=channel_id, 
                        video=video.file_id, 
                        caption=caption, 
                        parse_mode="Markdown", 
                        reply_markup=reply_markup,
                        thumbnail=thumb_file,
                        write_timeout=60, # Increase timeout for large files
                        read_timeout=60,
                        connect_timeout=60
                    )
                    break
                except RetryAfter as e:
                    msg_w = await message.reply_text(f"⏳ Esperando {e.retry_after}s (Flood Control)...")
                    schedule_deletion(context.bot, message.chat_id, msg_w.message_id, e.retry_after)
                    await asyncio.sleep(e.retry_after)
                except Exception as e:
                    logger.error(f"Send Video Error: {e}")
                    # Fallback recursion for too long caption is likely handled by previous edit logic, 
                    # but here we are replacing the sending block.
                    # I should keep the error handling robust.
                    if "too long" in str(e).lower():
                         caption = caption[:1000] + "..."
                         try:
                            await context.bot.send_video(chat_id=channel_id, video=video.file_id, caption=caption, parse_mode="Markdown", reply_markup=reply_markup, thumbnail=thumb_file)
                            break
                         except: pass
                    
                    await message.reply_text(f"❌ Error enviando video: {e}")
                    if thumb_file: thumb_file.close()
                    return
            
            if thumb_file: thumb_file.close()

            # Save to History
            HistoryService.save_movie(tmdb_id, title)

            # Quick per-movie acknowledgment (auto-deletes)
            msg_ok = await message.reply_text(
                f"✅ *{title} ({year})* publicada en el canal.",
                parse_mode="Markdown"
            )
            schedule_deletion(context.bot, message.chat_id, msg_ok.message_id, 8)

            # Register in batch session — summary fires after 45s of inactivity
            register_publish(message.chat_id, title, year, context.bot)
            
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
    except Exception as grand_error:
        logger.error(f"CRITICAL ERROR in process_movie_upload: {grand_error}", exc_info=True)
        await message.reply_text(f"❌ **Error Interno Crítico:** {grand_error}")


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
         ai_data = await asyncio.to_thread(AiService.extract_metadata, text_context)
         
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
