import requests
import logging
from typing import Optional, Dict
from cinegram.config import settings

logger = logging.getLogger(__name__)


class OmdbService:
    """
    Fallback movie search using OMDb API (Open Movie Database).
    Useful when TMDB fails because the title is in a regional language.
    Free API key: https://www.omdbapi.com/apikey.aspx
    """
    BASE_URL = "http://www.omdbapi.com/"

    @staticmethod
    def search_movie(title: str, year: str = None) -> Optional[Dict]:
        """
        Searches for a movie on OMDb by title and optional year.
        Returns a dict compatible with TmdbService format, or None.
        """
        if not settings.OMDB_API_KEY:
            logger.warning("OMDB_API_KEY not set. Skipping OMDb fallback.")
            return None

        params = {
            "apikey": settings.OMDB_API_KEY,
            "t": title,           # Search by exact title first
            "type": "movie",
            "plot": "full",
        }
        if year:
            params["y"] = year

        try:
            # 1. Try exact title match
            response = requests.get(OmdbService.BASE_URL, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            if data.get("Response") == "True":
                return OmdbService._format(data)

            # 2. Try search list (s= param) if exact match fails
            search_params = {
                "apikey": settings.OMDB_API_KEY,
                "s": title,
                "type": "movie",
            }
            if year:
                search_params["y"] = year

            search_resp = requests.get(OmdbService.BASE_URL, params=search_params, timeout=10)
            search_resp.raise_for_status()
            search_data = search_resp.json()

            if search_data.get("Response") == "True":
                top_result = search_data["Search"][0]
                imdb_id = top_result.get("imdbID")

                # Fetch full details by imdbID
                detail_resp = requests.get(OmdbService.BASE_URL, params={
                    "apikey": settings.OMDB_API_KEY,
                    "i": imdb_id,
                    "plot": "full"
                }, timeout=10)
                detail_resp.raise_for_status()
                detail = detail_resp.json()

                if detail.get("Response") == "True":
                    return OmdbService._format(detail)

            logger.info(f"OMDb: No match found for '{title}'")
            return None

        except Exception as e:
            logger.error(f"OMDb search failed: {e}")
            return None

    @staticmethod
    def _format(data: dict) -> Dict:
        """Convert OMDb response to a TMDB-compatible dict."""
        # OMDb rating is like "6.6/10", TMDB uses float 0-10
        imdb_rating = data.get("imdbRating", "N/A")
        try:
            rating = float(imdb_rating)
        except ValueError:
            rating = 0.0

        # OMDb has a direct poster URL
        poster_url = data.get("Poster", "")
        if poster_url == "N/A":
            poster_url = ""

        return {
            "title": data.get("Title"),
            "overview": data.get("Plot", ""),
            "release_date": data.get("Year", "")[:4] + "-01-01",
            "poster_url": poster_url,       # Direct URL (not a path like TMDB)
            "genre_ids": [],
            "genre_str": data.get("Genre", ""),   # OMDb gives genre as string directly
            "vote_average": rating,
            "source": "omdb",               # Mark source so caller knows poster is a direct URL
            "id": data.get("imdbID"),
        }
