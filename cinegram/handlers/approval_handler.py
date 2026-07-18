"""
approval_handler.py

Approval system for non-admin video submissions.
Flow:
  1. Any Telegram user sends a video to the bot.
  2. If they are NOT the admin, the bot queues the video and notifies the admin.
  3. Admin sees: "🎬 @username quiere publicar: [movie name]. ¿Apruebas?"
     with [✅ Sí, publicar] and [❌ No, rechazar] buttons.
  4. Admin clicks Sí → bot processes and publishes the video normally.
  5. Admin clicks No → bot notifies the submitter their request was rejected.
"""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from cinegram.config import settings
from cinegram.handlers.auth_handler import is_admin
import logging

logger = logging.getLogger(__name__)

# Pending queue: approval_id -> {user_id, chat_id, video, username, file_name}
_pending: dict = {}
_counter = 0


def _next_id() -> str:
    global _counter
    _counter += 1
    return f"appr_{_counter}"


async def handle_external_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Called when a non-admin user sends a video.
    Queues it and sends approval request to admin.
    """
    if update.effective_user is None:
        return

    user = update.effective_user
    video = update.message.video or update.message.document

    if not video:
        return

    # Build pending entry
    appr_id = _next_id()
    file_name = getattr(video, 'file_name', None) or "video sin nombre"
    _pending[appr_id] = {
        "user_id": user.id,
        "chat_id": update.effective_chat.id,
        "video": video,
        "username": user.username or user.first_name,
        "file_name": file_name,
        "message": update.message,
    }

    # Notify user their submission is pending
    await update.message.reply_text(
        f"📨 *Tu video fue recibido.*\n"
        f"El administrador lo revisará y decidirá si se publica en el canal.\n"
        f"Te avisaré cuando haya una respuesta. 🙏",
        parse_mode="Markdown"
    )

    # Notify admin
    keyboard = [[
        InlineKeyboardButton("✅ Sí, publicar", callback_data=f"APPROVE_{appr_id}"),
        InlineKeyboardButton("❌ No, rechazar", callback_data=f"REJECT_{appr_id}"),
    ]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    admin_text = (
        f"🎬 *Nueva solicitud de publicación*\n\n"
        f"👤 Usuario: @{user.username or 'sin username'} (`{user.id}`)\n"
        f"📁 Archivo: `{file_name}`\n\n"
        f"¿Apruebas la publicación en el canal?"
    )
    try:
        await context.bot.send_video(
            chat_id=settings.ADMIN_ID,
            video=video.file_id,
            caption=admin_text,
            parse_mode="Markdown",
            reply_markup=reply_markup
        )
    except Exception as e:
        logger.error(f"Could not notify admin of pending approval: {e}")
        # Fallback: text-only notification
        await context.bot.send_message(
            chat_id=settings.ADMIN_ID,
            text=admin_text,
            parse_mode="Markdown",
            reply_markup=reply_markup
        )


async def handle_approval_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the admin's approve/reject decision."""
    query = update.callback_query
    await query.answer()

    if update.effective_user is None or not is_admin(update.effective_user.id):
        await query.answer("⛔ Solo el administrador puede decidir esto.", show_alert=True)
        return

    data = query.data
    if data.startswith("APPROVE_"):
        appr_id = data.split("APPROVE_")[1]
        entry = _pending.pop(appr_id, None)
        if not entry:
            await query.edit_message_caption(caption="⚠️ Esta solicitud ya fue procesada o expiró.")
            return

        await query.edit_message_caption(
            caption=f"✅ *Aprobado.* Publicando video de @{entry['username']}...",
            parse_mode="Markdown"
        )

        # Process via the normal video pipeline using the original message
        from cinegram.handlers.video_handler import process_movie_upload
        from cinegram.services.filename_parser import FilenameParser

        video = entry["video"]
        message = entry["message"]
        filename = entry["file_name"]
        parsed = FilenameParser.parse_filename(filename)
        search_title = parsed.get("title", filename)
        extracted_year = parsed.get("year")

        try:
            await process_movie_upload(update, context, message, video, search_title, extracted_year)
            # Notify submitter
            await context.bot.send_message(
                chat_id=entry["user_id"],
                text=f"🎉 *¡Tu video fue aprobado y publicado en el canal!*\nGracias por contribuir 🙌",
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Approval processing failed for @{entry['username']}: {e}")
            await query.edit_message_text(
                text=f"❌ *Error al publicar* el video de @{entry['username']}:\n`{str(e)[:200]}`",
                parse_mode="Markdown"
            )
            try:
                await context.bot.send_message(
                    chat_id=entry["user_id"],
                    text=f"😔 Tu video fue aprobado pero falló al publicarse. El administrador lo revisará.",
                    parse_mode="Markdown"
                )
            except Exception:
                pass

    elif data.startswith("REJECT_"):
        appr_id = data.split("REJECT_")[1]
        entry = _pending.pop(appr_id, None)
        if not entry:
            await query.edit_message_caption(caption="⚠️ Esta solicitud ya fue procesada o expiró.")
            return

        await query.edit_message_caption(
            caption=f"❌ *Rechazado.* El video de @{entry['username']} no será publicado.",
            parse_mode="Markdown"
        )

        # Notify submitter
        try:
            await context.bot.send_message(
                chat_id=entry["user_id"],
                text=f"😔 Tu video no fue aprobado para publicación en el canal esta vez.",
            )
        except Exception:
            pass
