from telegram import Update
from telegram.ext import ContextTypes
from cinegram.services.history_service import HistoryService
from cinegram.handlers.auth_handler import is_admin

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Shows global statistics of the bot."""
    if update.effective_user is None: return
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Solo administradores pueden ver estadísticas.")
        return

    total_movies, total_users = HistoryService.get_stats()
    
    text = (
        f"📊 *Estadísticas de CineGram*\n\n"
        f"🎬 *Películas publicadas:* {total_movies}\n"
        f"👤 *Usuarios autorizados:* {total_users}\n"
    )
    await update.message.reply_text(text, parse_mode="Markdown")

async def today_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lists movies published in the last 24 hours."""
    if update.effective_user is None: return
    if not is_admin(update.effective_user.id):
        return

    movies = HistoryService.get_today_list()
    
    if not movies:
        await update.message.reply_text("📅 No se han publicado películas en las últimas 24 horas.")
        return

    movie_list = "\n".join([f"• {m}" for m in movies])
    text = (
        f"📅 *Películas de hoy ({len(movies)}):*\n\n"
        f"{movie_list}"
    )
    await update.message.reply_text(text, parse_mode="Markdown")
