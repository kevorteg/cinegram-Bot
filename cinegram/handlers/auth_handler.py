from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from cinegram.services.auth_service import AuthService
from cinegram.config import settings
from functools import wraps
import logging

logger = logging.getLogger(__name__)

# --- Decorator ---
def auth_required(func):
    """Only the admin (ADMIN_ID) can use protected commands."""
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        # Guard against channel posts / anonymous messages where effective_user is None
        if update.effective_user is None:
            return
        user_id = update.effective_user.id
        if user_id == settings.ADMIN_ID or AuthService.is_authorized(user_id):
            return await func(update, context, *args, **kwargs)
        else:
            await update.message.reply_text(
                "⛔ Solo el administrador puede usar este comando.",
                parse_mode="Markdown"
            )
    return wrapper


def is_admin(user_id: int) -> bool:
    return user_id == settings.ADMIN_ID or AuthService.is_authorized(user_id)


async def handle_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Checks if the user sent the correct password."""
    if update.effective_user is None:
        return
    user_id = update.effective_user.id
    text = update.message.text.strip()

    # If already authorized, skip — let other handlers take over
    if AuthService.is_authorized(user_id) or user_id == settings.ADMIN_ID:
        return

    if text == settings.ACCESS_PASSWORD:
        AuthService.authorize_user(user_id)
        await update.message.reply_text(
            "✅ *¡Acceso Concedido!*\nBienvenido a CineGram. Usa /start para comenzar.",
            parse_mode="Markdown"
        )
    # If it's not the password and not a command — silently ignore
    # (don't send "wrong password" for every message from anonymous users)


# --- Legacy stub handlers (kept to avoid registration errors in bot.py) ---
async def precheckout_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Disabled — payment system has been removed."""
    pass

async def successful_payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Disabled — payment system has been removed."""
    pass
