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
import html

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
        f"🍿 <b>¡Sesión completada!</b>\n"
        f"Se publicaron <b>{len(movies)} película(s)</b> en el canal:\n\n"
        f"{movie_list}\n\n"
        f"¡Mándame más cuando quieras! 🚀"
    )
    
    channel_summary = (
        f"📋 <b>Resumen de hoy:</b>\n"
        f"Se subieron <b>{len(movies)} película(s)</b> nuevas:\n\n"
        f"{movie_list}\n\n"
        f"➖➖➖➖➖➖➖➖\n"
        f"<b>¿Quieres pedir una película o serie?</b>\n"
        f"Escríbenos por los <b>mensajes directos del canal</b>.\n"
        f"💫 <b>Costo: 10 Estrellas de Telegram.</b>\n"
        f"<i>Subió (de 5 a 10) ya que las series llevan más tiempo.</i>\n"
        f"<i>Nos ayuda a seguir subiendo contenido. ¡Gracias!</i> 🙏\n\n"
        f"🎬 #cinegram"
    )
    
    try:
        await bot.send_message(chat_id=chat_id, text=private_summary, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Failed to send private batch summary: {e}")
    try:
        await bot.send_message(chat_id=settings.CHANNEL_ID, text=channel_summary, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Failed to send channel batch summary: {e}")

def register_publish(chat_id: int, title: str, year: str, bot):
    """Registers a published movie and resets the summary countdown."""
    session = _batch_sessions.setdefault(chat_id, {"movies": [], "task": None})
    session["movies"].append(f"{html.escape(title)} ({html.escape(str(year))})")
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


_SPAM_WORDS = re.compile(
    r'\b(La\s+Pelicula|La\s+Película|The\s+Movie|El\s+Film|Completa?|Online|'
    r'HomeCine|Pelicula|Película|Latino|Castellano|Subtitulad[oa]|'
    r'1080p|720p|480p|4K|HD|HQ|DVDRip|BRRip|WEBRip|BluRay|HDTV|'
    r'MP4|MKV|AVI|Full)\b',
    re.IGNORECASE
)

_SEQUENTIAL_NUM_RE = re.compile(r'\s+(\d{1,2})\s*$')


def _clean_search_title(raw: str) -> str:
    """Cleans a raw title/filename for TMDB search."""
    text = raw.strip()

    # 1. Convert ALL CAPS (>60% uppercase) to Title Case
    if len(text) > 3 and sum(1 for c in text if c.isupper()) / max(len(text), 1) > 0.6:
        text = text.title()

    # 2. Remove spam words
    text = _SPAM_WORDS.sub('', text)

    # 3. Collapse multiple spaces
    text = re.sub(r'\s{2,}', ' ', text).strip()

    return text


def _split_sequential_number(title: str):
    """Returns (base_title, number) if title ends with a small number like ' 1', ' 2'."""
    m = _SEQUENTIAL_NUM_RE.search(title)
    if m:
        num = m.group(1)
        base = title[:m.start()].strip()
        return base, num
    return title, None

# --- SHARED LOGIC ---

async def process_movie_upload(update: Update, context: ContextTypes.DEFAULT_TYPE, message, video, search_title, extracted_year=None, attempted_ai=False):
    """Processes and publishes a movie automatically."""
    try:
        if not search_title or search_title.lower() == "unknown":
            await message.reply_text("⚠️ No pude reconocer el nombre. Responde a este mensaje con el título correcto.")
            return

        msg_status = await message.reply_text(
            f"🔍 Buscando: <b>{html.escape(search_title)}</b> ({html.escape(str(extracted_year)) or '?'}) ...", 
            parse_mode="HTML"
        )
        schedule_deletion(context.bot, message.chat_id, msg_status.message_id)

        from cinegram.services.omdb_service import OmdbService
        from cinegram.services.translation_service import TranslationService

        def split_titles(t):
            parts = [t]
            for sep in [" * ", " - ", ": ", " | ", " / "]:
                if sep in t:
                    halves = [p.strip() for p in t.split(sep, 1)]
                    parts.extend(halves)
            return list(dict.fromkeys(parts))

        def is_year_valid(data, exp_yr):
            if not exp_yr or not data: return True
            yr = data.get('release_date', '')[:4]
            if not yr: return True
            try: return abs(int(yr) - int(exp_yr)) <= 1
            except ValueError: return True

        tmdb_data = await asyncio.to_thread(TmdbService.search_movie, search_title, year=extracted_year)
        if not tmdb_data and extracted_year:
            fb = await asyncio.to_thread(TmdbService.search_movie, search_title)
            if is_year_valid(fb, extracted_year): tmdb_data = fb

        if not tmdb_data:
            for candidate in split_titles(search_title)[1:]:
                tmdb_data = await asyncio.to_thread(TmdbService.search_movie, candidate, year=extracted_year)
                if not tmdb_data: 
                    fb = await asyncio.to_thread(TmdbService.search_movie, candidate)
                    if is_year_valid(fb, extracted_year): tmdb_data = fb
                if tmdb_data: break

        # Try stripping sequential number (e.g. "Antboy 1" -> "Antboy")
        if not tmdb_data:
            base_title, seq_num = _split_sequential_number(search_title)
            if seq_num and base_title:
                tmdb_data = await asyncio.to_thread(TmdbService.search_movie, base_title, year=extracted_year)
                if not tmdb_data:
                    fb = await asyncio.to_thread(TmdbService.search_movie, base_title)
                    if is_year_valid(fb, extracted_year): tmdb_data = fb

        if not tmdb_data:
            en_title = await asyncio.to_thread(TranslationService.translate_to_english, search_title)
            if en_title and en_title.lower() != search_title.lower():
                tmdb_data = await asyncio.to_thread(TmdbService.search_movie, en_title, year=extracted_year)
                if not tmdb_data:
                    fb = await asyncio.to_thread(TmdbService.search_movie, en_title)
                    if is_year_valid(fb, extracted_year): tmdb_data = fb

        if not tmdb_data:
            tmdb_data = await asyncio.to_thread(OmdbService.search_movie, search_title, year=extracted_year)

        if not tmdb_data and not attempted_ai:
            from cinegram.services.ai_service import AiService
            ai_data = await asyncio.to_thread(AiService.extract_metadata, message.caption or getattr(video, 'file_name', ''))
            if ai_data:
                await process_movie_upload(update, context, message, video, ai_data['title'], ai_data.get('year'), True)
                return

        if not tmdb_data:
            await message.reply_text(
                f"🚫 No encontré nada para '<b>{html.escape(search_title)}</b>'. Responde con el nombre correcto.",
                parse_mode="HTML"
            )
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
            await message.reply_text(
                f"🛑 <b>Detenido por Duplicado</b>.\nPelícula: {html.escape(title)} (ID: {tmdb_id})",
                parse_mode="HTML"
            )
            return

        # Prepare Image
        msg_gen = await message.reply_text(
            f"🎨 Generando portada para: <b>{html.escape(title)}</b>...", 
            parse_mode="HTML"
        )
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
            
            # Fetch extended metadata (director, cast, runtime, etc.)
            details = await asyncio.to_thread(TmdbService.get_movie_details, tmdb_id)
            
            # --- PUBLISHING ---
            # Force description to str to avoid type issues
            description = str(description) if description else ""
            synopsis = (description[:500] + "...") if len(description) > 500 else description
            short_synopsis = (description[:200] + "...") if len(description) > 200 else description
            
            # Build detailed caption line by line (only include fields that have data)
            original_title = details.get("original_title", "") or title
            runtime = details.get("runtime")
            countries = details.get("countries", "")
            screenplay = details.get("screenplay", "")
            companies = details.get("companies", "")
            distributor = details.get("distributor", "")
            
            # Person lists with IDs for link generation
            directors_list = details.get("directors", [])
            composers_list = details.get("composers", [])
            dops_list = details.get("dops", [])
            
            TMDB_PERSON_URL = "https://www.themoviedb.org/person"
            
            def bi(text: str) -> str:
                """Wrap text in bold + italic HTML tags."""
                return f"<b><i>{html.escape(text)}</i></b>"
            
            def person_links(persons: list) -> str:
                """Generate clickable TMDB links for crew members."""
                links = []
                for p in persons:
                    name = html.escape(p.get("name", ""))
                    pid = p.get("id", "")
                    if pid:
                        links.append(f'<a href="{TMDB_PERSON_URL}/{pid}">{name}</a>')
                    else:
                        links.append(f"<b><i>{name}</i></b>")
                return ", ".join(links)
            
            # Detect content type: Documental, Cortometraje, or Película
            genre_ids = tmdb_data.get('genre_ids', [])
            is_documentary = 99 in genre_ids
            is_short = runtime and runtime < 40

            if is_documentary:
                content_emoji = "📽"
                content_label = "Documental"
            elif is_short:
                content_emoji = "🎞"
                content_label = "Cortometraje"
            else:
                content_emoji = "🎬"
                content_label = "Película"

            # Title line: Spanish title / Original title
            if original_title and original_title.lower() != title.lower():
                title_line = f"<b><i>{html.escape(title)} / {html.escape(original_title)}</i></b>"
            else:
                title_line = bi(title)
            
            caption = f"{content_emoji} {content_label}: {title_line}\n"
            caption += f"📅 Año : {bi(str(year))}\n"
            if runtime:
                caption += f"⏱ Duración : {bi(f'{runtime} min.')}\n"
            if countries:
                caption += f"🌎 País : {bi(countries)}\n"
            if directors_list:
                caption += f"🎥 Dirección: {person_links(directors_list)}\n"
            if screenplay:
                caption += f"✍️ Guion: {bi(screenplay)}\n"
            if composers_list:
                caption += f"🎵 Música: {person_links(composers_list)}\n"
            if dops_list:
                caption += f"📷 Fotografía : {person_links(dops_list)}\n"
            caption += "\n"
            if companies:
                companies_list = details.get("companies_list", [])
                TMDB_COMPANY_URL = "https://www.themoviedb.org/company"
                if companies_list:
                    comp_links = []
                    for c in companies_list:
                        cname = html.escape(c.get("name", ""))
                        cid = c.get("id", "")
                        if cid:
                            comp_links.append(f'<a href="{TMDB_COMPANY_URL}/{cid}">{cname}</a>')
                        else:
                            comp_links.append(f"<b><i>{cname}</i></b>")
                    comp_line = ", ".join(comp_links)
                    if distributor:
                        comp_line += f". Distribuidora: {bi(distributor)}"
                    caption += f"🏢 Compañías: {comp_line}\n"
                else:
                    comp_text = companies
                    if distributor:
                        comp_text += f". Distribuidora: {distributor}"
                    caption += f"🏢 Compañías: {bi(comp_text)}\n"
            caption += "\n"
            
            if faith_data.get('is_faith') and faith_data.get('verse'):
                caption += f"📖 Versículo inspira:\n{bi(faith_data['verse'])}\n\n"
            
            # Hashtags: Genre tags + lead actor
            genre_tags = " | ".join([f"#{g.strip().replace(' ', '')}" for g in genre.split(',')])
            lead_actor = details.get("lead_actor", "")
            actor_tag = ""
            if lead_actor:
                actor_tag = f" #{''.join(lead_actor.split())}"
            caption += f"🎞 Género: {genre_tags}{actor_tag}\n\n"
            caption += f"🔗 Síguenos en Instagram:"

            # Short caption for the poster image (synopsis below the photo)
            photo_caption = bi(short_synopsis)

            # Telegram limit: 1024 chars for media captions
            TELEGRAM_CAPTION_LIMIT = 1024
            
            if len(caption) > TELEGRAM_CAPTION_LIMIT:
                # Full details go as a separate text message
                full_details = caption
                # Short caption for the video (fits within limit)
                video_caption = (
                    f"{content_emoji} {content_label}: {title_line}\n"
                    f"📅 Año : {bi(str(year))}\n"
                )
                if runtime:
                    video_caption += f"⏱ Duración : {bi(f'{runtime} min.')}\n"
                video_caption += f"\n🎞 Género: {genre_tags}\n\n"
                video_caption += f"🔗 Síguenos en Instagram:"
            else:
                video_caption = caption
                full_details = None

            buttons = [[InlineKeyboardButton("📸 Instagram", url=settings.INSTAGRAM_URL)]]
            if trailer_url:
                buttons[0].append(InlineKeyboardButton("🎥 Ver Trailer", url=trailer_url))
            reply_markup = InlineKeyboardMarkup(buttons)

            # Send Photo (with short synopsis caption) and Video to Channel
            with open(image_path, 'rb') as photo:
                await context.bot.send_photo(
                    chat_id=settings.CHANNEL_ID,
                    photo=photo,
                    caption=photo_caption,
                    parse_mode="HTML"
                )
            
            # Send full details as a separate message if caption was too long
            if full_details:
                try:
                    await context.bot.send_message(
                        chat_id=settings.CHANNEL_ID,
                        text=full_details,
                        parse_mode="HTML",
                        disable_web_page_preview=True
                    )
                except Exception as e:
                    logger.warning(f"Full details message failed: {e}")

            with open(image_path, 'rb') as thumb:
                await context.bot.send_video(
                    chat_id=settings.CHANNEL_ID,
                    video=video.file_id,
                    caption=video_caption,
                    parse_mode="HTML",
                    reply_markup=reply_markup,
                    thumbnail=thumb
                )

            # Success Tasks
            HistoryService.save_movie(tmdb_id, title)
            register_publish(message.chat_id, title, year, context.bot)
            
            msg_ok = await message.reply_text(
                f"✅ <b>{html.escape(title)}</b> publicada con éxito.", 
                parse_mode="HTML"
            )
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
    
    search_title = "Unknown"
    source_year = None
    
    if caption:
        clean_text = re.sub(r'[\U00010000-\U0010ffff]', '', caption)
        clean_text = clean_text.split('\n')[0].strip()
        
        year_match = re.search(r'[-_\s\(\[|]*(\d{4})[-_\s\)\]|]*', clean_text)
        if year_match:
            source_year = year_match.group(1)
            clean_text = clean_text.replace(year_match.group(0), " ").strip()
            
        clean_text = re.sub(r'[-_|\(\)\[\]]+\s*$', '', clean_text).strip()
        
        if clean_text:
            search_title = clean_text
        logger.info(f"Using caption for search: '{search_title}' ({source_year})")

    if len(search_title) < 3 and filename:
        from cinegram.services.filename_parser import FilenameParser
        parsed = FilenameParser.parse_filename(filename)
        if parsed and len(parsed['title']) > 2:
            search_title = parsed['title']
            source_year = parsed['year'] or source_year
            logger.info(f"Fallback to filename: {search_title}")

    # Clean the title: remove spam words, fix ALL CAPS
    search_title = _clean_search_title(search_title)

    # If title ends with a sequential number (e.g. "Antboy 1"), try without it first
    base_title, seq_num = _split_sequential_number(search_title)
    if seq_num and base_title:
        logger.info(f"Stripped sequential number: '{search_title}' -> base '{base_title}'")

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
