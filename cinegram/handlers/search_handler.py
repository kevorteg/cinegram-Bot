from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import logging
import asyncio

logger = logging.getLogger(__name__)


async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Searches TMDB for movies by title.
    Usage: /search <title>
    """
    if not context.args:
        await update.message.reply_text("🔎 *Uso:* `/search nombre de la película`", parse_mode="Markdown")
        return

    query = " ".join(context.args)
    msg = await update.message.reply_text(f"🔎 Buscando en TMDB: **{query}**...", parse_mode="Markdown")

    from cinegram.services.tmdb_service import TmdbService
    from cinegram.config import settings
    import requests

    base_url = "https://api.themoviedb.org/3/search/movie"
    params = {
        "api_key": settings.TMDB_API_KEY,
        "query": query,
        "language": "es-MX",
        "page": 1,
    }

    try:
        response = await asyncio.to_thread(requests.get, base_url, params=params, timeout=10)
        response.raise_for_status()
        results = response.json().get("results", [])

        if not results:
            await msg.edit_text(f"❌ No encontré resultados en TMDB para *{query}*.", parse_mode="Markdown")
            return

        # Build keyboard with top 5 results
        keyboard = []
        for movie in results[:5]:
            title = movie.get("title", "Unknown")[:35]
            year = movie.get("release_date", "")[:4] or "?"
            tmdb_id = movie.get("id")
            keyboard.append([InlineKeyboardButton(f"🎬 {title} ({year})", callback_data=f"TMDB_{tmdb_id}")])

        reply_markup = InlineKeyboardMarkup(keyboard)
        await msg.edit_text(
            f"🎬 Resultados para *{query}*:\n👇 Selecciona la película:",
            parse_mode="Markdown",
            reply_markup=reply_markup
        )

    except Exception as e:
        logger.error(f"TMDB search error: {e}")
        await msg.edit_text("❌ Error al buscar en TMDB. Intenta de nuevo.")


async def handle_search_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the selection of a TMDB search result — shows movie info."""
    query = update.callback_query
    await query.answer()

    data = query.data
    if not data.startswith("TMDB_"):
        return

    tmdb_id = data.split("TMDB_")[1]

    from cinegram.services.tmdb_service import TmdbService
    from cinegram.config import settings
    import requests

    # Fetch full movie details
    url = f"https://api.themoviedb.org/3/movie/{tmdb_id}"
    params = {
        "api_key": settings.TMDB_API_KEY,
        "language": "es-MX",
    }

    try:
        response = await asyncio.to_thread(requests.get, url, params=params, timeout=10)
        response.raise_for_status()
        movie = response.json()

        title = movie.get("title", "?")
        year = (movie.get("release_date") or "")[:4] or "?"
        overview = (movie.get("overview") or "Sin sinopsis disponible.")[:600]
        rating = round(movie.get("vote_average", 0), 1)
        genres = ", ".join([g["name"] for g in movie.get("genres", [])[:2]])

        text = (
            f"🎬 *{title}* ({year})\n"
            f"⭐ Calificación: {rating}\n"
            f"🎭 Género: {genres}\n\n"
            f"📝 *Sinopsis:*\n{overview}...\n\n"
            f"💡 _Envíame el archivo de video para publicarlo en el canal._"
        )

        await query.edit_message_text(text, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"TMDB detail fetch error: {e}")
        await query.edit_message_text("❌ Error al obtener detalles de TMDB.")
