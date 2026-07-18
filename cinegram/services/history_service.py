import logging
from cinegram.services.db_service import DbService

logger = logging.getLogger(__name__)

class HistoryService:
    @staticmethod
    def save_movie(tmdb_id: str, title: str = "Unknown"):
        if not tmdb_id: return
        conn = DbService.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR IGNORE INTO history (tmdb_id, title) VALUES (?, ?)",
            (str(tmdb_id), title)
        )
        conn.commit()
        conn.close()
        logger.info(f"Movie {tmdb_id} saved to database history.")

    @staticmethod
    def is_duplicate(tmdb_id: str) -> bool:
        if not tmdb_id: return False
        conn = DbService.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM history WHERE tmdb_id = ?", (str(tmdb_id),))
        result = cursor.fetchone()
        conn.close()
        return result is not None

    @staticmethod
    def get_stats():
        """Returns total movies and total authorized users."""
        conn = DbService.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM history")
        total_movies = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM users")
        total_users = cursor.fetchone()[0]
        conn.close()
        return total_movies, total_users

    @staticmethod
    def get_today_list():
        """Returns list of movies published in the last 24 hours."""
        conn = DbService.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT title FROM history 
            WHERE published_at >= datetime('now', '-1 day')
            ORDER BY published_at DESC
        """)
        movies = [row[0] for row in cursor.fetchall()]
        conn.close()
        return movies

    @staticmethod
    def get_today_detailed():
        """Returns list of {title, published_at} for movies in the last 24 hours."""
        conn = DbService.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT title, published_at FROM history 
            WHERE published_at >= datetime('now', '-1 day')
            ORDER BY published_at ASC
        """)
        movies = [{"title": row[0], "published_at": row[1]} for row in cursor.fetchall()]
        conn.close()
        return movies
