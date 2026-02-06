import sys
import os

# Add current directory to path so we can resolve cinegram package
sys.path.append(os.getcwd())

try:
    from cinegram.services.ai_service import AiService
    from cinegram.config import settings
    
    # Mock settings if needed (but they should load from .env)
    if not settings.OLLAMA_MODEL:
        settings.OLLAMA_MODEL = "dolphin-llama3:latest"

    print("--- Testing Actual AiService ---")
    
    cases = [
        "Un Amante Latino (2022).mp4",
        "Scary Movie (Pelicula de Miedo).mkv", 
        "El Estreno del Siglo.avi",
        "Batman.Online.Latino.HD.mp4"
    ]

    for c in cases:
        print(f"Input: {c}")
        # Call the synchronous/static method if it is blocking, 
        # but AiService in previous steps seemed to use requests.post (blocking).
        # Let's check signature. It was @staticmethod extract_metadata(text) -> dict
        res = AiService.extract_metadata(c)
        print(f"Output: {res}\n")

except Exception as e:
    print(f"Test failed with error: {e}")
