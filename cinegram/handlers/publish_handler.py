import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from cinegram.config import settings

async def send_publication(update: Update, context: ContextTypes.DEFAULT_TYPE, metadata: dict, image_path: str):
    """
    Orchestrates the 2-step publication process.
    1. Send Generated Image to channel
    2. Send link with caption to channel
    3. Confirm to user in private chat
    """
    channel_id = settings.CHANNEL_ID
    user_chat_id = update.effective_chat.id

    caption = (
        f"🎬 *Película:* {metadata['title']}\n"
        f"📅 *Año:* {metadata['year']}\n"
        f"🌎 *Idioma:* Latino 🇨🇴🇲🇽\n"
        f"💿 *Calidad:* HD\n"
        f"⭐️ *Calificación:* {metadata.get('rating', 'N/A')}\n"
        f"🎭 *Género:* {metadata['genre']}\n\n"
        f"📝 *Sinopsis:*\n{metadata.get('description', '')[:800]}\n\n"
        f"🔗 *Síguenos en Instagram:*"
    )

    keyboard = [[InlineKeyboardButton("📸 Instagram", url=settings.INSTAGRAM_URL)]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Step 1: Send Image to channel
    try:
        with open(image_path, 'rb') as photo:
            await context.bot.send_photo(chat_id=channel_id, photo=photo)
    except Exception as e:
        await context.bot.send_message(chat_id=user_chat_id, text=f"❌ Error enviando imagen al canal: {e}")
        return

    # Step 2: Send caption + link to channel
    try:
        await context.bot.send_message(
            chat_id=channel_id,
            text=f"{caption}\n\n[Ver Película en Archive.org]({metadata.get('video_link', 'https://archive.org')})",
            parse_mode="Markdown",
            reply_markup=reply_markup
        )
    except Exception as e:
        await context.bot.send_message(chat_id=user_chat_id, text=f"❌ Error publicando en canal: {e}")
        return

    # Step 3: Confirm to user
    await context.bot.send_message(
        chat_id=user_chat_id,
        text=f"✅ *{metadata['title']}* publicada en el canal.",
        parse_mode="Markdown"
    )
