from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler, CommandHandler, MessageHandler, filters
from cinegram.services.tmdb_service import TmdbService
from cinegram.services.image_generator import ImageGenerator
from cinegram.config import settings
import logging
import os

logger = logging.getLogger(__name__)

# State definitions for Conversation (if we used full convo, but here we use simple flow)
# For simplicity in this 'v1' extension, we'll try a 'reply to this message with details' approach 
# or a simplified 'Send Metadata' command if we want state.
# However, the user asked for: "El bot detecta... Te pide o infiere".
# So a ConversationHandler is best.

async def video_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Autonomous entry point for video messages.
    1. Receives Video
    2. Cleans Filename -> Title
    3. Searches TMDB
    4. Generates Poster
    5. Publishes (Image + Video)
    """
    message = update.message
    video = message.video or message.document
    
    if not video:
        return

    # Feedback
    await message.reply_text("⚙️ **Procesando video automáticamente...**", parse_mode="Markdown")

    file_id = video.file_id
    # Fix: getattr might return None, so we must check for truthiness
    filename = getattr(video, 'file_name', None) or "Unknown_Movie.mp4"
    
    # --- 1. CLEAN TITLE & EXTRACT YEAR (Intelligent) ---
    from cinegram.services.filename_parser import FilenameParser
    
    parsed_data = FilenameParser.parse_filename(filename)
    
    if not parsed_data:
        await message.reply_text(
            "⚠️ **Error:** No pude entender el nombre del archivo.\n"
            "Por favor, renómbralo a algo más claro (Ej: 'Titulo Año.mp4') y reenvíalo."
        )
        return

    search_title = parsed_data['title']
    extracted_year = parsed_data['year']
    
    # --- 2. SEARCH TMDB (With "Steroids") ---
    await message.reply_text(f"🔍 Analizando: **{search_title}** ({extracted_year or '?'}) ...", parse_mode="Markdown")
    
    # Try Search with Year first
    tmdb_data = TmdbService.search_movie(search_title, year=extracted_year)
    
    # If no result and had year, try without year (sometimes offsets vary)
    if not tmdb_data and extracted_year:
        tmdb_data = TmdbService.search_movie(search_title)
        
    # --- 3. STRICT VALIDATION ---
    if not tmdb_data:
        await message.reply_text(
            f"🚫 **Cancelado:** No encontré nada en TMDB para '{search_title}'.\n"
            "El archivo no se ha publicado.\n\n"
            "👉 **Solución:** Responde a este mensaje con el **Nombre Correcto** (y año opcional) para buscarlo manualmente."
        )
        # Store context to allow reply handling (we need to route text replies to a search handler logic via a simple check in bot.py?)
        # For now, simplest is asking them to use /search or rely on reply if we restore conversation.
        # But wait, user wants autonomous. If autonomous fails, we stop.
        return

    # Extract Data
    title = tmdb_data.get('title')
    year = tmdb_data.get('release_date', '')[:4]
    poster_path = tmdb_data.get('poster_path')
    description = tmdb_data.get('overview')
    rating = str(round(tmdb_data.get('vote_average', 0), 1))
    genre = TmdbService.get_genres(tmdb_data.get('genre_ids', []))

    # Strict Check: Must have Poster and Year
    if not poster_path or not year:
        await message.reply_text(
            f"🚫 **Incompleto:** Encontré '{title}' pero le falta la portada o el año.\n"
            "No voy a publicar contenido incompleto.\n\n"
            "👉 Intenta buscar otra versión con `/search {title}`"
        )
        return

    # --- 4. GENERATE & PUBLISH ---
    poster_url = TmdbService.get_poster_url(poster_path)
    await message.reply_text("🎨 Generando portada...", parse_mode="Markdown")
    
    try:
        image_path = ImageGenerator.generate_poster(poster_url, title, description)
    except Exception as e:
        await message.reply_text("❌ Error generando la imagen.")
        return

    # --- 5. PUBLISH TO CHANNEL (With Retry Logic) ---
    channel_id = settings.CHANNEL_ID
    
    # Imports for retry logic
    import asyncio
    from telegram.error import RetryAfter

    try:
        # Send Image
        if image_path and os.path.exists(image_path):
            while True:
                try:
                    with open(image_path, 'rb') as photo:
                        await context.bot.send_photo(chat_id=channel_id, photo=photo)
                    break # Success, exit loop
                except RetryAfter as e:
                    logger.warning(f"Flood control exceeded. Sleeping for {e.retry_after} seconds.")
                    await asyncio.sleep(e.retry_after)
                except Exception as e:
                    logger.error(f"Error sending photo: {e}")
                    break # Other error, skip photo

        # Prepare Hashtags
        hashtag_list = []
        if genre:
            # Split by comma usually
            g_list = [g.strip() for g in genre.split(',')]
            for g in g_list[:3]: # Max 3
                # Remove spaces and make it like CamelCase/PascalCase for hashtag
                # e.g. "Ciencia ficción" -> "CienciaFicción"
                clean_tag = "".join(word.capitalize() for word in g.split())
                hashtag_list.append(f"#{clean_tag}")
                
        hashtags = " ".join(hashtag_list)

        # Prepare Caption
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
        
        keyboard = [[InlineKeyboardButton("📸 Instagram", url=settings.INSTAGRAM_URL)]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        while True:
            try:
                await context.bot.send_video(
                    chat_id=channel_id,
                    video=file_id,
                    caption=caption,
                    parse_mode="Markdown",
                    reply_markup=reply_markup
                )
                break # Success
            except RetryAfter as e:
                logger.warning(f"Flood control exceeded for video. Sleeping for {e.retry_after} seconds.")
                await message.reply_text(f"⏳ Telegram me pidió esperar {e.retry_after}s... (Pausando para evitar bloqueo)")
                await asyncio.sleep(e.retry_after)
            
        await message.reply_text(f"✅ **Publicado:** {title} ({year})")
        
    except Exception as e:
        logger.error(f"Error publishing: {e}")
        await message.reply_text(f"❌ Error enviando al canal: {e}")
