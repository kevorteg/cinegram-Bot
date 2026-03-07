import os
import sys
import asyncio
import logging
import re
from telethon import TelegramClient
from dotenv import load_dotenv

# Add project root to path
sys.path.append(os.getcwd())

from cinegram.config import settings
from cinegram.services.db_service import DbService
from cinegram.services.tmdb_service import TmdbService
from cinegram.services.history_service import HistoryService
from cinegram.services.filename_parser import FilenameParser

# Configure Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def scan():
    # Load credentials from .env
    load_dotenv()
    api_id = os.getenv("TELEGRAM_API_ID")
    api_hash = os.getenv("TELEGRAM_API_HASH")
    phone = os.getenv("TELEGRAM_PHONE")
    channel_id = os.getenv("CHANNEL_ID")

    if not api_id or not api_hash:
        logger.error("TELEGRAM_API_ID or TELEGRAM_API_HASH not set in .env")
        return

    # Initialize DB (Ensures tables exist)
    DbService.init_db()

    client = TelegramClient('cinegram_scanner', api_id, api_hash)
    
    await client.connect()
    if not await client.is_user_authorized():
        if not phone:
            logger.error("TELEGRAM_PHONE not set in .env")
            return
        await client.send_code_request(phone)
        code = input('Enter the code you received on Telegram: ')
        from telethon.errors import SessionPasswordNeededError
        try:
            await client.sign_in(phone, code)
        except SessionPasswordNeededError:
            password = input('Two-step verification is enabled. Enter your password: ')
            await client.sign_in(password=password)

    logger.info(f"Connected to Telegram. Scanning channel: {channel_id}")
    
    # Try to resolve channel entity
    try:
        # channel_id in .env might be -100... format
        entity = await client.get_entity(int(channel_id))
    except Exception as e:
        logger.error(f"Could not find channel {channel_id}: {e}")
        return

    count = 0
    scanned = 0
    
    async for message in client.iter_messages(entity):
        scanned += 1
        
        # We look for messages with video or document (video)
        if not (message.video or (message.document and "video" in (message.document.mime_type or ""))):
            continue

        # Extract title
        caption = message.text or ""
        filename = getattr(message.file, 'name', "") or ""
        
        search_title = ""
        year = None
        
        # 1. Try to parse from caption (usually "🎬 Película: Name")
        match = re.search(r'🎬 \*?Película:\*?\s*(.+)', caption)
        if match:
            search_title = match.group(1).strip()
            # Try to extract year from title like "Name (2024)"
            year_match = re.search(r'\((\d{4})\)', search_title)
            if year_match:
                year = year_match.group(1)
                search_title = re.sub(r'\s*\(\d{4}\)', '', search_title).strip()
        
        # 2. Fallback to filename if caption is empty or doesn't match
        if not search_title and filename:
            parsed = FilenameParser.parse_filename(filename)
            if parsed:
                search_title = parsed['title']
                year = parsed['year']

        if not search_title:
            continue

        # Check if already in DB
        # Note: We don't have the tmdb_id yet, but we can check if a movie with this title exists
        # Actually, let's just search TMDB to get the real ID.
        
        logger.info(f"[{scanned}] Found: {search_title} " + (f"({year})" if year else ""))
        
        # Search TMDB to get the canonical ID
        tmdb_data = TmdbService.search_movie(search_title, year=year)
        if not tmdb_data and year:
            tmdb_data = TmdbService.search_movie(search_title)
            
        if tmdb_data:
            tmdb_id = tmdb_data['id']
            title = tmdb_data['title']
            
            # Save to DB
            if not HistoryService.is_duplicate(str(tmdb_id)):
                HistoryService.save_movie(str(tmdb_id), title)
                count += 1
                if count % 10 == 0:
                    logger.info(f"✅ Progress: {count} movies added to SQLite.")
            else:
                # logger.debug(f"Skipping duplicate: {title}")
                pass
        else:
            logger.warning(f"Could not find TMDB match for: {search_title}")

    logger.info(f"Scan finished. Added {count} new movies to the database history.")
    await client.disconnect()

if __name__ == "__main__":
    asyncio.run(scan())
