import os
from dotenv import load_dotenv

load_dotenv()

# Bot Configuration
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
INSTAGRAM_URL = os.getenv("INSTAGRAM_URL", "https://instagram.com")
TMDB_API_KEY = os.getenv("TMDB_API_KEY")
OMDB_API_KEY = os.getenv("OMDB_API_KEY", "")  # https://www.omdbapi.com/apikey.aspx (free)
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "dolphin-llama3:latest")

# Access Control & Payments
ADMIN_ID = int(os.getenv("ADMIN_ID", "0")) # Owner ID
ACCESS_PASSWORD = os.getenv("ACCESS_PASSWORD", "cinegram123") # Fallback password
STARS_PRICE = 50 # Cost in Stars to unlock

# Paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMP_DIR = os.path.join(BASE_DIR, "temp")
ASSETS_DIR = os.path.join(BASE_DIR, "assets")
FONTS_DIR = os.path.join(ASSETS_DIR, "fonts")

# Make sure directories exist
os.makedirs(TEMP_DIR, exist_ok=True)
os.makedirs(ASSETS_DIR, exist_ok=True)
os.makedirs(FONTS_DIR, exist_ok=True)

# Image Generation Defaults
DEFAULT_FONT_PATH = os.path.join(FONTS_DIR, "Roboto-Bold.ttf") # User needs to provide this or we fallback
IMAGE_SIZE = (1920, 1080)
