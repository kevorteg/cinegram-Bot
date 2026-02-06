import re

def is_valid_archive_url(url: str) -> bool:
    """Checks if the URL is a valid Internet Archive identifier."""
    return "archive.org/details/" in url

def extract_identifier(url: str) -> str:
    """Extracts the identifier from an Internet Archive URL."""
    # Pattern to match: ...archive.org/details/IDENTIFIER
    match = re.search(r"archive\.org/details/([^/]+)", url)
    if match:
        return match.group(1)
    return None

# Auto-Deletion Utils
import asyncio
import logging
from telegram import Bot

logger = logging.getLogger(__name__)

async def _delete_task(bot: Bot, chat_id: int, message_id: int, delay: int):
    await asyncio.sleep(delay)
    try:
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
    except Exception as e:
        logger.debug(f"Failed to auto-delete message {message_id}: {e}")

def schedule_deletion(bot: Bot, chat_id: int, message_id: int, delay: int = 5):
    """Schedules a message to be deleted after 'delay' seconds."""
    asyncio.create_task(_delete_task(bot, chat_id, message_id, delay))
