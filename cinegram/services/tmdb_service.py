import requests
import logging
from typing import Optional, Dict
from cinegram.config import settings

logger = logging.getLogger(__name__)

class TmdbService:
    BASE_URL = "https://api.themoviedb.org/3"
    IMAGE_BASE_URL = "https://image.tmdb.org/t/p/original"

    @staticmethod
    def _normalize(text: str) -> str:
        """Removes accents and lowercases text for fuzzy comparison."""
        import unicodedata
        if not text: return ""
        return ''.join(c for c in unicodedata.normalize('NFD', text) if unicodedata.category(c) != 'Mn').lower().strip()

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

        # Session with Retry Strategy
        session = requests.Session()
        retries = requests.adapters.HTTPAdapter(max_retries=3)
        session.mount('https://', retries)

        try:
            response = session.get(url, params=params, timeout=10)
            response.raise_for_status()
            results = response.json().get('results', [])
            
            if not results:
                # RETRY 2: Remove common noise suffixes
                for noise in [" La Pelicula", " La Película", " The Movie", " El Film"]:
                    if noise.lower() in title.lower():
                        clean_title = title.lower().replace(noise.lower(), "").strip()
                        params["query"] = clean_title
                        params["language"] = "es-MX"
                        response = requests.get(url, params=params)
                        results = response.json().get('results', [])
                        if results: break

            if not results:
                # RETRY 3: English Search (Original strategy)
                params["query"] = title 
                params["language"] = "en-US"
                response = requests.get(url, params=params)
                response.raise_for_status()
                results = response.json().get('results', [])

            if results:
                # --- FUZZY MATCH VALIDATION ---
                from difflib import SequenceMatcher
                
                best_match = None
                best_score = 0.0
                
                query_norm = TmdbService._normalize(title)

                # Check the top 5 results
                for movie in results[:5]:
                    candidate_title = movie.get('title', '')
                    candidate_orig = movie.get('original_title', '')
                    
                    cand_norm_local = TmdbService._normalize(candidate_title)
                    cand_norm_orig = TmdbService._normalize(candidate_orig)
                    
                    # Compute similarity
                    score_local = SequenceMatcher(None, query_norm, cand_norm_local).ratio()
                    score_orig = SequenceMatcher(None, query_norm, cand_norm_orig).ratio()
                    max_score = max(score_local, score_orig)
                    
                    # Logic: If query has a year, enforce it strictly
                    if year:
                        re_date = movie.get('release_date', '')[:4]
                        if re_date and re_date != str(year):
                            # Penalize strict year mismatch
                             max_score -= 0.5 # Heavy penalty
                    
                    logger.info(f"Candidate: '{candidate_title}' (Score: {max_score:.2f}) vs Input: '{title}'")

                    # SUBSTRING RESCUE:
                    if query_norm in cand_norm_local or query_norm in cand_norm_orig:
                         if len(query_norm) > 5:
                             logger.info(f"Substring Match Detected! Boosting score for '{candidate_title}'")
                             max_score = max(max_score, 0.9)

                    if max_score > best_score:
                         best_score = max_score
                         best_match = movie

                # THRESHOLD: 0.8 (80% match required)
                if best_match and best_score >= 0.8:
                    movie = best_match
                else:
                    if best_match:
                         logger.warning(f"Rejected best match '{best_match.get('title')}' due to low score ({best_score:.2f} < 0.8)")
                    else:
                         logger.warning(f"No match found for '{title}'")
                    return None

                return {
                    "id": movie.get('id'),
                    "title": movie.get('title'),
                    "overview": movie.get('overview'),
                    "release_date": movie.get('release_date'),
                    "poster_path": movie.get('poster_path'),
                    "genre_ids": movie.get('genre_ids'),
                    "vote_average": movie.get('vote_average'),
                    "source": "tmdb"
                }
            return None
            
        except Exception as e:
            logger.error(f"TMDB Search failed (CRITICAL): {e}", exc_info=True)
            return None

    @staticmethod
    def get_poster_url(poster_path: str) -> Optional[str]:
        if not poster_path:
            return None
        return f"{TmdbService.IMAGE_BASE_URL}{poster_path}"

    @staticmethod
    def get_genres(genre_ids: list) -> str:
        """Converts genre IDs to string string based on cached list (simplified)."""
        genres = {
            28: "Acción", 12: "Aventura", 16: "Animación", 35: "Comedia",
            80: "Crimen", 99: "Documental", 18: "Drama", 10751: "Familia",
            14: "Fantasía", 36: "Historia", 27: "Terror", 10402: "Música",
            9648: "Misterio", 10749: "Romance", 878: "Ciencia Ficción",
            10770: "Película de TV", 53: "Suspense", 10752: "Bélica", 37: "Western"
        }
        return ", ".join([genres.get(gid, "Cine") for gid in genre_ids[:3]])

    @staticmethod
    def get_trailer(movie_id: int) -> Optional[str]:
        """Fetches the YouTube trailer URL for a movie ID."""
        if not settings.TMDB_API_KEY:
            return None
            
        url = f"{TmdbService.BASE_URL}/movie/{movie_id}/videos"
        params = {"api_key": settings.TMDB_API_KEY, "language": "es-MX"}
        
        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            videos = response.json().get('results', [])
            
            # 1. Look for trailer in Spanish
            for v in videos:
                if v.get('site') == 'YouTube' and v.get('type') == 'Trailer':
                    return f"https://www.youtube.com/watch?v={v['key']}"
            
            # 2. Fallback to English trailers
            params["language"] = "en-US"
            response = requests.get(url, params=params, timeout=10)
            videos = response.json().get('results', [])
            for v in videos:
                if v.get('site') == 'YouTube' and v.get('type') == 'Trailer':
                    return f"https://www.youtube.com/watch?v={v['key']}"
                    
            return None
        except Exception as e:
            logger.error(f"Trailer fetch failed: {e}")
            return None
