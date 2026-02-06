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
            "Analyze the following text which contains a messy movie filename or spammy description. "
            "Extract ONLY the REAL MOVIE TITLE and YEAR (if present). "
            "STRICTLY REMOVE terms like: 'Online', 'Pelicula', 'Completa', 'Latino', 'Castellano', 'HD', '1080p', 'HomeCine', 'Cuevana', 'Estreno'. "
            "If the text is 'Perdidos en el Artico Online Pelicula', the title is just 'Perdidos en el Artico'. "
            "Correct common typos. "
            "Return ONLY a JSON object with keys 'title' (string) and 'year' (string or null). "
            "Do not output markdown code blocks, just the raw JSON string.\n\n"
            f"Text: {text}"
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
