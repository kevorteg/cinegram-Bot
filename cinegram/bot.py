import os
import logging
import requests
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    filters, CallbackQueryHandler, PreCheckoutQueryHandler
)
from cinegram.config import settings
from cinegram.handlers import start, archive_handler, video_handler, external_handler, search_handler, auth_handler
from cinegram.handlers import approval_handler

# Configure Logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)


def check_ollama_health():
    """Checks if Ollama is running locally."""
    url = "http://localhost:11434/api/tags"
    try:
        response = requests.get(url, timeout=2)
        if response.status_code == 200:
            logging.info("✅ Ollama is Online.")
            return True
    except Exception:
        pass
    logging.warning("⚠️ WARNING: Ollama is NOT reachable. AI features will fail.")
    return False


async def failed_command(update, context):
    """Shows the list of movies that failed to be found."""
    if not auth_handler.is_admin(update.effective_user.id):
        return
    log_path = os.path.join(settings.BASE_DIR, "failed_movies.txt")
    if not os.path.exists(log_path):
        await update.message.reply_text("✅ No hay películas fallidas registradas.")
        return
    with open(log_path, "r", encoding="utf-8") as f:
        content = f.read().strip()
    if not content:
        await update.message.reply_text("✅ No hay películas fallidas registradas.")
        return
    # Limit to last 50 entries to avoid Telegram message limit
    lines = content.split("\n")[-50:]
    await update.message.reply_text(
        f"🚫 *Películas no encontradas ({len(lines)} entradas):*\n\n" + "\n".join(lines),
        parse_mode="Markdown"
    )


async def clear_failed_command(update, context):
    """Clears the failed movies log."""
    if not auth_handler.is_admin(update.effective_user.id):
        return
    log_path = os.path.join(settings.BASE_DIR, "failed_movies.txt")
    if os.path.exists(log_path):
        os.remove(log_path)
    await update.message.reply_text("🗑️ Lista de fallidas limpiada.")


def main():
    if not settings.BOT_TOKEN:
        print("Error: BOT_TOKEN not found in environment variables.")
        return

    application = ApplicationBuilder().token(settings.BOT_TOKEN).build()

    # --- Legacy stubs (payment system removed but handlers kept to avoid errors) ---
    application.add_handler(PreCheckoutQueryHandler(auth_handler.precheckout_callback))
    application.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, auth_handler.successful_payment_callback))

    # Password Handler: group=0 (runs first, exits early for authorized/admin users)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, auth_handler.handle_password), group=0)

    # Manual Correction (Reply to Bot): group=1
    application.add_handler(MessageHandler(filters.REPLY & filters.TEXT & ~filters.COMMAND, video_handler.handle_manual_correction), group=1)

    # --- Admin Commands ---
    application.add_handler(CommandHandler("start", start.start_command))
    application.add_handler(CommandHandler("search", auth_handler.auth_required(search_handler.search_command)))
    application.add_handler(CommandHandler("failed", failed_command))
    application.add_handler(CommandHandler("clearfailed", clear_failed_command))

    # --- Callback Queries ---
    application.add_handler(CallbackQueryHandler(search_handler.handle_search_callback, pattern="^TMDB_"))
    application.add_handler(CallbackQueryHandler(approval_handler.handle_approval_callback, pattern="^(APPROVE|REJECT)_"))

    # --- Video: Admin publishes directly, others go to approval queue ---
    application.add_handler(MessageHandler(
        filters.VIDEO | filters.Document.VIDEO,
        _route_video
    ))

    # Archive Links (admin only)
    application.add_handler(MessageHandler(filters.Regex(r'archive\.org/details/'), auth_handler.auth_required(archive_handler.handle_archive_link)))

    # Generic Links (admin only)
    application.add_handler(MessageHandler(filters.Entity("url") | filters.Regex(r'^http'), auth_handler.auth_required(external_handler.handle_external_link)))

    print("Bot is running...")
    check_ollama_health()
    application.run_polling()


async def _route_video(update, context):
    """Routes video to admin pipeline or approval queue depending on sender."""
    if update.effective_user is None:
        return
    if auth_handler.is_admin(update.effective_user.id):
        await video_handler.video_entry(update, context)
    else:
        await approval_handler.handle_external_video(update, context)


if __name__ == '__main__':
    main()
