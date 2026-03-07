import requests
import logging
from cinegram.config import settings

logger = logging.getLogger(__name__)

class TranslationService:
    OLLAMA_URL = "http://localhost:11434/api/generate"
    # Configurable model
    MODEL = settings.OLLAMA_MODEL

    @staticmethod
    def translate_to_spanish(text: str) -> str:
        """
        Translates text to Spanish using local Ollama model.
        """
        if not text:
            return ""

        # Prompt refined for Latin American Spanish and conciseness
        prompt = (
            "Translate the following movie synopsis to Spanish (Latin American). "
            "Then rewrite it as a short synopsis of maximum 5–6 lines. "
            "Use natural, neutral Latin American Spanish suitable for movie descriptions. "
            "Return ONLY the final text, no intro, no quotes.\n\n"
            f"Text: {text}"
        )

        payload = {
            "model": TranslationService.MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.3 # Low temp for accurate translation
            }
        }

        try:
            logger.info(f"Translating via Ollama ({TranslationService.MODEL})...")
            response = requests.post(TranslationService.OLLAMA_URL, json=payload, timeout=30)
            response.raise_for_status()
            result = response.json()
            translation = result.get('response', '').strip()
            
            if translation:
                return translation
            else:
                return text # Fallback to original
                
        except Exception as e:
            logger.error(f"Ollama translation failed: {e}")
            return text # Fallback to original
    @staticmethod
    def translate_to_english(text: str) -> str:
        """
        Translates a movie title or text to English using local Ollama model.
        Used as a search fallback when TMDB fails with the original language title.
        """
        if not text:
            return text

        prompt = (
            "Translate the following movie title to English. "
            "Return ONLY the translated title. No explanations, no quotes, no punctuation at the end.\n"
            f"Title: {text}"
        )

        payload = {
            "model": TranslationService.MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.1}
        }

        try:
            logger.info(f"Translating to English via Ollama: '{text}'")
            response = requests.post(TranslationService.OLLAMA_URL, json=payload, timeout=20)
            response.raise_for_status()
            translated = response.json().get('response', '').strip().strip('"').strip("'")
            if translated and translated.lower() != text.lower():
                logger.info(f"English translation: '{text}' -> '{translated}'")
                return translated
            return text
        except Exception as e:
            logger.error(f"Ollama English translation failed: {e}")
            return text
