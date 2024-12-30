from pathlib import Path

# Base directory of the project
BASE_DIR = Path(__file__).resolve().parent

# Storage configuration
DATA_DIR = BASE_DIR / "data"
UPLOAD_DIR = DATA_DIR / "uploads"
PROCESSED_DIR = DATA_DIR / "processed"
NOTES_DIR = DATA_DIR / "notes"
DB_PATH = DATA_DIR / "notes.db"
APP_DIR = BASE_DIR / "app"
STATIC_DIR = APP_DIR / "static"

# Ensure all directories exist
for path in [DATA_DIR, UPLOAD_DIR, PROCESSED_DIR, NOTES_DIR]:
    path.mkdir(parents=True, exist_ok=True)

# Scanner settings
SCANNER_CONFIG = {
    'target_width': 595,  # A4 width at 72 DPI (standard PDF point width)
    'min_line_length': 50,
    'max_lines': 100
}

# File settings
ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png'}
MAX_UPLOAD_SIZE_MB = 10
MAX_FILES_PER_SESSION = 50

# Your Gemini API key
GEMINI_API_KEY = "api-key-goes-here"