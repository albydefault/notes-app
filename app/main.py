from fastapi import FastAPI, UploadFile, HTTPException, Request
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import sqlite3
import logging
from typing import List
import shutil
import sys

# Add project root to path for relative imports
sys.path.append(str(Path(__file__).resolve().parent.parent))

from scanner import DocumentScanner
from processor import NoteProcessor
from db import DB_PATH, init_db, save_generated_content
from config import *

# Initialize logging
logging.basicConfig(level=logging.DEBUG, format="%(asctime)s [%(levelname)s] %(message)s")

# Initialize app
app = FastAPI(title="Notes Scanner")

# Mount static directories
app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.mount("/processed", StaticFiles(directory="app/processed"), name="processed")
app.mount("/processed_notes", StaticFiles(directory="app/processed_notes"), name="processed_notes")

# Set up templates
templates = Jinja2Templates(directory="app/templates")

# Initialize scanner and processor
scanner = DocumentScanner()
processor = NoteProcessor(api_key=GEMINI_API_KEY)

# Initialize database
init_db()

@app.get("/")
async def home(request: Request):
    """Serve the home page."""
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/upload")
async def upload_files(files: List[UploadFile]):
    """Handle file uploads and store metadata."""
    ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png"}
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Create a new note set
    cursor.execute("INSERT INTO Notes (title, summary) VALUES (?, ?)", ("Untitled", ""))
    note_id = cursor.lastrowid
    logging.info(f"New note created with ID: {note_id}")


    saved_files = []
    processed_files = []

    for file in files:
        # Validate file type
        if Path(file.filename).suffix.lower() not in ALLOWED_EXTENSIONS:
            raise HTTPException(status_code=400, detail=f"Unsupported file type: {file.filename}")

        # Save uploaded file
        file_path = UPLOAD_DIR / file.filename
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        saved_files.append(file_path)

        # Process the image
        processed_path = scanner.scan_image(file_path)
        if processed_path:
            processed_files.append(f"/processed/{processed_path.name}")
            cursor.execute(
                "INSERT INTO Images (note_id, filename, path) VALUES (?, ?, ?)",
                (note_id, processed_path.name, str(processed_path))
            )

    conn.commit()
    conn.close()

    if not processed_files:
        raise HTTPException(status_code=400, detail="No files were successfully processed.")

    return {"message": f"Processed {len(processed_files)} files", "processed_files": processed_files}

@app.post("/process-notes")
async def process_notes():
    """Generate content from the most recent note set."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Get the most recent note
    cursor.execute("SELECT id FROM Notes ORDER BY created_at DESC LIMIT 1")
    note_row = cursor.fetchone()
    if not note_row:
        raise HTTPException(status_code=404, detail="No notes found to process.")
    note_id = note_row[0]

    logging.info(f"Processing note with ID: {note_id}")

    try:
        # Step 1: Generate transcription
        content = processor.transcribe_notes("app/processed")
        transcription_path = PROCESSED_NOTES_DIR / f"transcription_{note_id}.md"
        processor.save_markdown(content, transcription_path)
        save_generated_content(cursor, note_id, "transcription", transcription_path.name, str(transcription_path))

        # Step 2: Generate exposition using transcription
        with open(transcription_path, "r", encoding="utf-8") as f:
            transcription_text = f.read()
        
        exposition_content = processor.explain_notes(transcription_text)
        exposition_path = PROCESSED_NOTES_DIR / f"exposition_{note_id}.md"
        with open(exposition_path, "w", encoding="utf-8") as f:
            f.write(exposition_content.text)
        save_generated_content(cursor, note_id, "exposition", exposition_path.name, str(exposition_path))

        # Step 3: Generate question sheet using exposition
        with open(exposition_path, "r", encoding="utf-8") as f:
            exposition_text = f.read()

        
        question_content = processor.generate_questions(exposition_text)
        question_path = PROCESSED_NOTES_DIR / f"questions_{note_id}.md"
        with open(question_path, "w", encoding="utf-8") as f:
            f.write(question_content.text)
        save_generated_content(cursor, note_id, "questions", question_path.name, str(question_path))

        # Commit the database changes
        conn.commit()

        return {
            "message": "Notes processed successfully.",
            "title": content["title"],
            "summary": content["summary"],
            "files": [
                {"type": "transcription", "file": f"/processed_notes/{transcription_path.name}"},
                {"type": "exposition", "file": f"/processed_notes/{exposition_path.name}"},
                {"type": "questions", "file": f"/processed_notes/{question_path.name}"}
            ]
        }

    except Exception as e:
        conn.rollback()
        logging.error(f"Error processing notes: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to process notes: {e}")
    finally:
        conn.close()

# Run the application if executed directly
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
