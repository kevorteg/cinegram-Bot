import requests
import logging
from typing import Optional, Dict
from cinegram.config import settings

logger = logging.getLogger(__name__)

class TmdbService:
    BASE_URL = "https://api.themoviedb.org/3"
    IMAGE_BASE_URL = "https://image.tmdb.org/t/p/original"

    @staticmethod
    def search_movie(title: str, year: str = None) -> Optional[Dict]:
        """
        Searches for a movie on TMDB by title and optional year.
        Returns the best match metadata.
        """
        if not settings.TMDB_API_KEY:
            logger.warning("TMDB_API_KEY is not set. Skipping TMDB search.")
            return None

        url = f"{TmdbService.BASE_URL}/search/movie"
        params = {
            "api_key": settings.TMDB_API_KEY,
            "query": title,
            "language": "es-MX", # Latin Spanish preference
            "page": 1
        }
        if year:
            params["year"] = year

        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            results = response.json().get('results', [])
            
            if not results:
                # RETRY 2: Remove common noise suffixes
                # "Hello Kitty La Pelicula" -> "Hello Kitty"
                # "Sonic La Pelicula" -> "Sonic"
                for noise in [" La Pelicula", " La Película", " The Movie", " El Film"]:
                    if noise.lower() in title.lower():
                        clean_title = title.lower().replace(noise.lower(), "").strip()
                        params["query"] = clean_title
                        params["language"] = "es-MX" # Reset to Spanish
                        response = requests.get(url, params=params)
                        results = response.json().get('results', [])
                        if results: break

            if not results:
                # RETRY 3: English Search (Original strategy)
                params["query"] = title # Reset to full title (or should we use clean? try full english first)
                params["language"] = "en-US"
                response = requests.get(url, params=params)
                response.raise_for_status()
                results = response.json().get('results', [])

            if results:
                # Return the first (best) match
                movie = results[0]
                
                # If we fell back to English, translate the overview
                overview = movie.get('overview')
                if overview and params.get("language") == "en-US":
                    from cinegram.services.translation_service import TranslationService
                    overview = TranslationService.translate_to_spanish(overview)

                return {
                    "title": movie.get('title'),
                    "overview": overview,
                    "release_date": movie.get('release_date'),
                    "poster_path": movie.get('poster_path'),
                    "genre_ids": movie.get('genre_ids'),
                    "vote_average": movie.get('vote_average')
                }
            return None
            
        except requests.RequestException as e:
            logger.error(f"TMDB Search failed: {e}")
            return None

    @staticmethod
    def get_poster_url(poster_path: str) -> Optional[str]:
        if not poster_path:
            return None
        return f"{TmdbService.IMAGE_BASE_URL}{poster_path}"

    @staticmethod
    def get_genres(genre_ids: list) -> str:
        """Converts genre IDs to string string based on cached list (simplified)."""
        # Simplified mapping for common genres
        genres = {
            28: "Acción", 12: "Aventura", 16: "Animación", 35: "Comedia",
            80: "Crimen", 99: "Documental", 18: "Drama", 10751: "Familia",
            14: "Fantasía", 36: "Historia", 27: "Terror", 10402: "Música",
            9648: "Misterio", 10749: "Romance", 878: "Ciencia Ficción",
            10770: "Película de TV", 53: "Suspense", 10752: "Bélica", 37: "Western"
        }
        return ", ".join([genres.get(gid, "Cine") for gid in genre_ids[:2]])
