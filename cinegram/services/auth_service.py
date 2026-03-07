import json
import os
import logging
from cinegram.config import settings

from cinegram.services.db_service import DbService

logger = logging.getLogger(__name__)

class AuthService:
    @staticmethod
    def is_authorized(user_id: int) -> bool:
        # 1. Admin is always authorized
        if user_id == settings.ADMIN_ID:
            return True
            
        # 2. Check Database
        conn = DbService.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM users WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()
        conn.close()
        return result is not None

    @staticmethod
    def authorize_user(user_id: int):
        conn = DbService.get_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
        conn.commit()
        conn.close()
        logger.info(f"User {user_id} authorized in database.")
