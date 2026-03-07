import json
import os
import logging
from typing import Set

logger = logging.getLogger(__name__)

class HistoryService:
    HISTORY_FILE = "upload_history.json"
    _history: Set[str] = set()

    @classmethod
    def load_history(cls):
        if not os.path.exists(cls.HISTORY_FILE):
            return
        try:
            with open(cls.HISTORY_FILE, 'r') as f:
                data = json.load(f)
                cls._history = set(str(id) for id in data)
            logger.info(f"Loaded {len(cls._history)} movies from history.")
        except Exception as e:
            logger.error(f"Failed to load history: {e}")

    @classmethod
    def save_movie(cls, tmdb_id: int):
        if not tmdb_id: return
        cls._history.add(str(tmdb_id))
        try:
            with open(cls.HISTORY_FILE, 'w') as f:
                json.dump(list(cls._history), f)
        except Exception as e:
            logger.error(f"Failed to save history: {e}")

    @classmethod
    def is_duplicate(cls, tmdb_id: int) -> bool:
        if not cls._history:
            cls.load_history()
        return str(tmdb_id) in cls._history
