import logging
from cinegram.config import settings

logger = logging.getLogger(__name__)


class TranslationService:
    """Translation service using the unified AI backend (Groq / Ollama / None)."""

    @staticmethod
    def translate_to_spanish(text: str) -> str:
        """
        Translates text to Spanish using the configured AI provider.
        Falls back to original text if AI is unavailable or fails.
        """
        if not text or settings.AI_PROVIDER == "none":
            return text

        prompt = (
            "Translate the following movie synopsis to Spanish (Latin American). "
            "Then rewrite it as a short synopsis of maximum 5–6 lines. "
            "Use natural, neutral Latin American Spanish suitable for movie "
            "descriptions. "
            "Return ONLY the final text, no intro, no quotes.\n\n"
            f"Text: {text}"
        )

        try:
            from cinegram.services.ai_service import AiService
            logger.info("Translating synopsis to Spanish via AI...")
            result = AiService._call_ai(prompt, temperature=0.3)
            if result and result.strip():
                return result.strip()
            return text
        except Exception as e:
            logger.error(f"Spanish translation failed: {e}")
            return text

    @staticmethod
    def translate_to_english(text: str) -> str:
        """
        Translates a movie title or text to English using the configured AI
        provider.  Used as a search fallback when TMDB fails with the
        original-language title.
        """
        if not text or settings.AI_PROVIDER == "none":
            return text

        prompt = (
            "Translate the following movie title to English. "
            "Return ONLY the translated title. No explanations, no quotes, "
            "no punctuation at the end.\n"
            f"Title: {text}"
        )

        try:
            from cinegram.services.ai_service import AiService
            logger.info(f"Translating to English via AI: '{text}'")
            translated = AiService._call_ai(prompt, temperature=0.1)
            if translated:
                translated = translated.strip().strip('"').strip("'")
                if translated and translated.lower() != text.lower():
                    logger.info(f"English translation: '{text}' -> '{translated}'")
                    return translated
            return text
        except Exception as e:
            logger.error(f"English translation failed: {e}")
            return text
