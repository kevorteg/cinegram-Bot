from telegram import Update
from telegram.ext import ContextTypes
from cinegram.services.history_service import HistoryService
from cinegram.handlers.auth_handler import is_admin
from cinegram.config import settings
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

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

async def reporte_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Generates a report of today's movies and sends it to the channel."""
    if update.effective_user is None: return
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Solo el administrador puede generar reportes.")
        return

    movies = HistoryService.get_today_detailed()

    if not movies:
        await update.message.reply_text("📅 No se han publicado películas en las últimas 24 horas.")
        return

    today_str = datetime.now().strftime("%d de %B %Y").replace("January", "enero").replace("February", "febrero").replace("March", "marzo").replace("April", "abril").replace("May", "mayo").replace("June", "junio").replace("July", "julio").replace("August", "agosto").replace("September", "septiembre").replace("October", "octubre").replace("November", "noviembre").replace("December", "diciembre")

    movie_lines = []
    for i, m in enumerate(movies, 1):
        title = m["title"]
        pub_time = ""
        if m["published_at"]:
            try:
                dt = datetime.strptime(m["published_at"], "%Y-%m-%d %H:%M:%S")
                pub_time = f" — {dt.strftime('%I:%M %p').lstrip('0')}"
            except (ValueError, TypeError):
                pass
        movie_lines.append(f"  {i}. 🎬 {title}{pub_time}")

    movie_list = "\n".join(movie_lines)

    channel_report = (
        f"📋 <b>Resumen del día — {today_str}</b>\n\n"
        f"🎬 Se publicaron <b>{len(movies)} película(s)</b>:\n\n"
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
        await context.bot.send_message(
            chat_id=settings.CHANNEL_ID,
            text=channel_report,
            parse_mode="HTML"
        )
        await update.message.reply_text(
            f"✅ Reporte publicado en el canal ({len(movies)} peli{'s' if len(movies) != 1 else ''}).",
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Failed to send report to channel: {e}")
        await update.message.reply_text(f"❌ Error enviando reporte al canal: {e}")
