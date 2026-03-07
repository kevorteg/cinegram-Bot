import requests
import logging
import json
import re
from typing import Optional, Dict
from cinegram.config import settings

logger = logging.getLogger(__name__)

class AiService:
    OLLAMA_URL = "http://localhost:11434/api/generate"
    # Use the same model as configured for translation
    MODEL = settings.OLLAMA_MODEL

    @staticmethod
    def extract_metadata(text: str) -> Optional[Dict]:
        """
        Uses LLM to extract a likely movie title and year from messy text.
        Returns a dict: {'title': str, 'year': str | None} or None if failed.
        """
        if not text:
            return None

        # Robust prompt for extraction
        prompt = (
            "Analyze the messy text to extract the MOVIE TITLE and YEAR.\n"
            "Rules:\n"
            "1. Remove technical tags (1080p, HD, MP4).\n"
            "2. Remove spam words (Online, Pelicula, Completa, HomeCine) ONLY if they are NOT part of the title.\n"
            "3. BE CAREFUL with 'Latino': Keep it if it's the title (e.g. 'Un Amante Latino'), remove it if it's language (e.g. 'Batman Latino').\n\n"
            "Examples:\n"
            "- 'Batman.Latino.Online.mp4' -> {'title': 'Batman', 'year': null}\n"
            "- 'Un Amante Latino (2022)' -> {'title': 'Un Amante Latino', 'year': '2022'}\n"
            "- 'Mision.Completa.2000.avi' -> {'title': 'Mision Completa', 'year': '2000'}\n"
            "- 'Spiderman.Pelicula.Completa' -> {'title': 'Spiderman', 'year': null}\n\n"
            f"Input Text: {text}\n"
            "JSON Output:"
        )

        payload = {
            "model": AiService.MODEL,
            "prompt": prompt,
            "stream": False,
            "format": "json", 
            "options": {
                "temperature": 0.1 
            }
        }

        try:
            logger.info(f"🤖 AI Deep Search on: '{text[:50]}...'")
            response = requests.post(AiService.OLLAMA_URL, json=payload, timeout=45)
            response.raise_for_status()
            result = response.json()
            
            # Parse the response
            answer = result.get('response', '{}').strip()
            
            # Clean possible markdown ```json wrap
            copy_ans = answer
            if "```" in copy_ans:
                 copy_ans = copy_ans.replace("```json", "").replace("```", "")
            
            data = json.loads(copy_ans)
            
            title = data.get('title')
            year = data.get('year')
            
            if title and str(title).lower() not in ["unknown", "desconocido", "video", "none"]:
                return {
                    "title": str(title),
                    "year": str(year) if year else None
                }
            
            return None

        except json.JSONDecodeError:
            logger.warning(f"AI returned invalid JSON: {answer}")
            return None
        except Exception as e:
            logger.error(f"AI Metadata extraction failed: {e}")
            return None

    @staticmethod
    def analyze_faith_content(title: str, overview: str) -> Optional[Dict]:
        """
        Analyzes if a movie is Christian/Faith-based and provides a Bible verse.
        """
        prompt = (
            f"Analyze if the movie '{title}' (Overview: {overview}) is explicitly Christian or Faith-based.\n"
            "If YES:\n"
            "  1. Select a relevant Bible Verse (Reina Valera 1960) that matches the movie's theme.\n"
            "  2. If no specific theme fits, use a generic Salvation verse (e.g. John 3:16, Romans 10:9).\n"
            "If NO: Return is_faith=False.\n\n"
            "Return JSON: { 'is_faith': bool, 'verse': 'citation and text', 'hashtags': ['#Jesuseselcamino', '#Diosteama', '#motivando'] }"
        )

        payload = {
            "model": AiService.MODEL,
            "prompt": prompt,
            "stream": False,
            "format": "json",
            "options": {
                "temperature": 0.2
            }
        }

        try:
            response = requests.post(AiService.OLLAMA_URL, json=payload, timeout=90)
            response.raise_for_status()
            data = response.json()
            answer = data.get('response', '{}')
            parsed = json.loads(answer)
            return parsed
        except Exception as e:
            logger.error(f"Faith Analysis failed: {e}")
            return {'is_faith': False}
