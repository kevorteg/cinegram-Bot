import sqlite3
import os
import logging
from datetime import datetime
from cinegram.config import settings

logger = logging.getLogger(__name__)

class DbService:
    DB_PATH = os.path.join(settings.ASSETS_DIR, "cinegram.db")

    @staticmethod
    def get_connection():
        """Returns a connection to the SQLite database."""
        return sqlite3.connect(DbService.DB_PATH)

    @staticmethod
    def init_db():
        """Initializes the database schema and performs migrations."""
        conn = DbService.get_connection()
        cursor = conn.cursor()

        # Users table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                authorized_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # History table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS history (
                tmdb_id TEXT PRIMARY KEY,
                title TEXT,
                published_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        conn.commit()
        conn.close()
        logger.info("Database initialized.")
        
        # Run migrations from JSON if they exist
        DbService._migrate_from_json()

    @staticmethod
    def _migrate_from_json():
        """Migrates data from legacy JSON files to SQLite."""
        import json
        
        # 1. Migrate Users
        whitelist_path = os.path.join(settings.ASSETS_DIR, "whitelist.json")
        if os.path.exists(whitelist_path):
            try:
                with open(whitelist_path, 'r') as f:
                    user_ids = json.load(f)
                
                conn = DbService.get_connection()
                cursor = conn.cursor()
                for uid in user_ids:
                    cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (uid,))
                conn.commit()
                conn.close()
                logger.info(f"Migrated {len(user_ids)} users from whitelist.json")
                # Rename the file to mark migration as done
                os.rename(whitelist_path, whitelist_path + ".bak")
            except Exception as e:
                logger.error(f"Failed to migrate users: {e}")

        # 2. Migrate History
        history_path = os.path.join(settings.ASSETS_DIR, "upload_history.json")
        if os.path.exists(history_path):
            try:
                with open(history_path, 'r') as f:
                    movie_ids = json.load(f)
                
                conn = DbService.get_connection()
                cursor = conn.cursor()
                for mid in movie_ids:
                    cursor.execute("INSERT OR IGNORE INTO history (tmdb_id, title) VALUES (?, ?)", (str(mid), "Migrated"))
                conn.commit()
                conn.close()
                logger.info(f"Migrated {len(movie_ids)} movies from upload_history.json")
                os.rename(history_path, history_path + ".bak")
            except Exception as e:
                logger.error(f"Failed to migrate history: {e}")
