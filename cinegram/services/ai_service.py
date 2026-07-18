import requests
import logging
import json
import re
from typing import Optional, Dict
from cinegram.config import settings

logger = logging.getLogger(__name__)


class AiService:
    OLLAMA_URL = "http://localhost:11434/api/generate"
    GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
    GROQ_MODEL = settings.GROQ_MODEL
    OLLAMA_MODEL = settings.OLLAMA_MODEL

    # ── Low-level callers ────────────────────────────────────────────────

    @staticmethod
    def _call_groq(prompt: str, temperature: float = 0.1,
                   format_json: bool = False) -> Optional[str]:
        """Call Groq cloud API (OpenAI-compatible)."""
        headers = {
            "Authorization": f"Bearer {settings.GROQ_API_KEY}",
            "Content-Type": "application/json",
        }
        payload: dict = {
            "model": AiService.GROQ_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
            "max_tokens": 2048,
        }
        if format_json:
            payload["response_format"] = {"type": "json_object"}

        resp = requests.post(AiService.GROQ_URL, json=payload,
                             headers=headers, timeout=30)
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]

    @staticmethod
    def _call_ollama(prompt: str, temperature: float = 0.1,
                     format_json: bool = False) -> Optional[str]:
        """Call local Ollama API."""
        payload = {
            "model": AiService.OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False,
            "format": "json" if format_json else None,
            "options": {"temperature": temperature},
        }
        resp = requests.post(AiService.OLLAMA_URL, json=payload, timeout=45)
        resp.raise_for_status()
        return resp.json().get("response", "")

    @staticmethod
    def _call_ai(prompt: str, temperature: float = 0.1,
                 format_json: bool = False) -> Optional[str]:
        """
        Unified AI caller with fallback:  Groq → Ollama → None.
        Respects AI_PROVIDER setting.
        """
        provider = settings.AI_PROVIDER

        # ── Groq ────────────────────────────────────────────────────────
        if provider in ("auto", "groq") and settings.GROQ_API_KEY:
            try:
                logger.info("🤖 Calling Groq cloud AI...")
                result = AiService._call_groq(prompt, temperature, format_json)
                if result:
                    return result
            except Exception as e:
                logger.warning(f"Groq failed: {e}")
                if provider == "groq":
                    return None

        # ── Ollama ──────────────────────────────────────────────────────
        if provider in ("auto", "ollama"):
            try:
                logger.info("🤖 Calling local Ollama AI...")
                result = AiService._call_ollama(prompt, temperature, format_json)
                if result:
                    return result
            except Exception as e:
                logger.warning(f"Ollama failed: {e}")
                if provider == "ollama":
                    return None

        # ── All failed or AI disabled ───────────────────────────────────
        if provider == "none":
            logger.info("AI disabled (AI_PROVIDER=none)")
        else:
            logger.warning("All AI providers failed")
        return None

    # ── High-level helpers ───────────────────────────────────────────────

    @staticmethod
    def extract_metadata(text: str) -> Optional[Dict]:
        """
        Uses LLM to extract a likely movie title and year from messy text.
        Returns {'title': str, 'year': str | None} or None.
        """
        if not text or settings.AI_PROVIDER == "none":
            return None

        prompt = (
            "Analyze the messy text to extract the MOVIE TITLE and YEAR.\n"
            "Rules:\n"
            "1. Remove technical tags (1080p, HD, MP4).\n"
            "2. Remove spam words (Online, Pelicula, Completa, HomeCine) "
            "ONLY if they are NOT part of the title.\n"
            "3. BE CAREFUL with 'Latino': Keep it if it's the title "
            "(e.g. 'Un Amante Latino'), remove it if it's language "
            "(e.g. 'Batman Latino').\n\n"
            "Examples:\n"
            "- 'Batman.Latino.Online.mp4' -> {'title': 'Batman', 'year': null}\n"
            "- 'Un Amante Latino (2022)' -> {'title': 'Un Amante Latino', 'year': '2022'}\n"
            "- 'Mision.Completa.2000.avi' -> {'title': 'Mision Completa', 'year': '2000'}\n"
            "- 'Spiderman.Pelicula.Completa' -> {'title': 'Spiderman', 'year': null}\n\n"
            f"Input Text: {text}\n"
            "JSON Output:"
        )

        try:
            logger.info(f"🤖 AI Deep Search on: '{text[:50]}...'")
            answer = AiService._call_ai(prompt, temperature=0.1, format_json=True)
            if not answer:
                return None

            # Clean possible markdown ```json wrap
            copy_ans = answer.strip()
            if "```" in copy_ans:
                copy_ans = copy_ans.replace("```json", "").replace("```", "")

            data = json.loads(copy_ans)
            title = data.get("title")
            year = data.get("year")

            if title and str(title).lower() not in (
                "unknown", "desconocido", "video", "none"
            ):
                return {
                    "title": str(title),
                    "year": str(year) if year else None,
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
        """Analyzes if a movie is Christian/Faith-based and provides a Bible verse."""
        if settings.AI_PROVIDER == "none":
            return {"is_faith": False}

        prompt = (
            f"Analyze if the movie '{title}' (Overview: {overview}) is "
            "explicitly Christian or Faith-based.\n"
            "If YES:\n"
            "  1. Select a relevant Bible Verse (Reina Valera 1960) that "
            "matches the movie's theme.\n"
            "  2. If no specific theme fits, use a generic Salvation verse "
            "(e.g. John 3:16, Romans 10:9).\n"
            "If NO: Return is_faith=False.\n\n"
            "Return JSON: { 'is_faith': bool, 'verse': 'citation and text', "
            "'hashtags': ['#Jesuseselcamino', '#Diosteama', '#motivando'] }"
        )

        try:
            logger.info(f"✝️  Faith analysis for: '{title}'")
            answer = AiService._call_ai(prompt, temperature=0.2, format_json=True)
            if not answer:
                return {"is_faith": False}

            parsed = json.loads(answer)
            return parsed
        except Exception as e:
            logger.error(f"Faith Analysis failed: {e}")
            return {"is_faith": False}
