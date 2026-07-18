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
AI_PROVIDER = os.getenv("AI_PROVIDER", "auto")  # auto | groq | ollama | none
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

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

# Poster Layout (Split Style)
POSTER_BG_COLOR = (13, 17, 23)  # #0d1117 dark background
POSTER_LEFT_WIDTH = 0.42        # 42% of canvas width for the poster area
POSTER_MARGIN = 60              # margin around poster
POSTER_SHADOW_OFFSET = 8        # shadow offset for poster
POSTER_SHADOW_BLUR = 20         # shadow blur radius
POSTER_TITLE_SIZE = 80
POSTER_META_SIZE = 40
POSTER_DESC_SIZE = 36
POSTER_TEXT_MARGIN_LEFT = 80    # gap between poster area and text area
