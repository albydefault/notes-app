# config.py
from pathlib import Path

# Base directory of the project
BASE_DIR = Path(__file__).resolve().parent

# Directory configurations
UPLOAD_DIR = BASE_DIR / "app" / "uploads"
PROCESSED_DIR = BASE_DIR / "app" / "processed"
PROCESSED_NOTES_DIR = BASE_DIR / "app" / "processed_notes"

# Ensure directories exist
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
PROCESSED_NOTES_DIR.mkdir(parents=True, exist_ok=True)

# Your Gemini API key
GEMINI_API_KEY = "AIzaSyC15gYSaQit8jzj2t22OrjaVmH2DNRxhLY"