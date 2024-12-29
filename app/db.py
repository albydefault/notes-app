import sqlite3
from pathlib import Path
import logging

# Path to the database file
DB_PATH = Path(__file__).resolve().parent.parent / "db" / "database.db"

# Ensure the database directory exists
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

def init_db():
    """Initialize the database and create tables if they don't exist."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # Create Notes table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS Notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT,
                summary TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Create Images table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS Images (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                note_id INTEGER,
                filename TEXT,
                path TEXT,
                FOREIGN KEY (note_id) REFERENCES Notes (id)
            )
        """)

        # Create Generated Content table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS GeneratedContent (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                note_id INTEGER,
                type TEXT,
                filename TEXT,
                path TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (note_id) REFERENCES Notes (id)
            )
        """)

        conn.commit()
        logging.info("Database initialized successfully.")
    except Exception as e:
        logging.error(f"Error initializing database: {e}")
    finally:
        conn.close()

def get_db_connection():
    """Get a new database connection."""
    return sqlite3.connect(DB_PATH)

def save_generated_content(cursor, note_id, content_type, filename, path):
    """Helper function to save generated content metadata."""
    cursor.execute(
        "INSERT INTO GeneratedContent (note_id, type, filename, path) VALUES (?, ?, ?, ?)",
        (note_id, content_type, filename, path)
    )
