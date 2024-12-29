from fastapi import FastAPI, UploadFile, HTTPException, Request
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import logging
from typing import List
import shutil
import sys

# Add project root to path for relative imports
sys.path.append(str(Path(__file__).resolve().parent.parent))

from scanner import DocumentScanner
from processor import NoteProcessor
from db import DatabaseManager
from config import *

# Initialize logging
logging.basicConfig(level=logging.DEBUG, format="%(asctime)s [%(levelname)s] %(message)s")

# Initialize app
app = FastAPI(title="Notes Scanner")

# Mount directories for file access
app.mount("/processed", StaticFiles(directory=str(PROCESSED_DIR)), name="processed")
app.mount("/notes", StaticFiles(directory=str(NOTES_DIR)), name="notes")

# Set up templates
templates = Jinja2Templates(directory="app/templates")

# Initialize core components
scanner = DocumentScanner(target_width=SCANNER_CONFIG['target_width'])
processor = NoteProcessor(api_key=GEMINI_API_KEY)
db = DatabaseManager(DB_PATH)

@app.get("/")
async def home(request: Request):
    """Serve the home page."""
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/upload")
async def upload_files(files: List[UploadFile]):
    """Handle file uploads and process images."""
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded")

    # Create new session for this upload
    session_id = db.create_session()
    processed_files = []

    try:
        for file in files:
            # Validate file extension
            if Path(file.filename).suffix.lower() not in ALLOWED_EXTENSIONS:
                raise HTTPException(status_code=400, 
                                 detail=f"Unsupported file type: {file.filename}")

            # Save uploaded file
            upload_path = UPLOAD_DIR / f"{session_id}_{file.filename}"
            with open(upload_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            
            # Track original file
            db.add_file(session_id, file.filename, str(upload_path), "original")

            # Process the image
            processed_path = scanner.scan_image(upload_path)
            if processed_path:
                db.add_file(session_id, processed_path.name, str(processed_path), "scanned")
                processed_files.append(f"/processed/{processed_path.name}")

        if not processed_files:
            db.update_session(session_id, {"status": "error"})
            raise HTTPException(status_code=400, detail="No files were successfully processed")

        db.update_session(session_id, {"status": "processing"})
        
        return {
            "message": f"Processed {len(processed_files)} files",
            "processed_files": processed_files,
            "session_id": session_id
        }

    except Exception as e:
        db.update_session(session_id, {"status": "error"})
        logging.error(f"Error processing upload: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/process-notes/{session_id}")
async def process_notes(session_id: str):
    """Generate content from processed images."""
    session_info = db.get_session_info(session_id)
    if not session_info:
        raise HTTPException(status_code=404, detail="Session not found")

    try:
        # Get scanned files for this session
        scanned_files = db.get_session_files(session_id, "scanned")
        if not scanned_files:
            raise HTTPException(status_code=400, detail="No processed images found")

        # Get paths of scanned images for this session
        image_paths = [Path(file['file_path']) for file in scanned_files]

        # Step 1: Generate transcription
        content = processor.transcribe_notes(image_paths)  # Now passing specific image paths
        transcription_path = NOTES_DIR / f"transcription_{session_id}.md"
        processor.save_markdown(content, transcription_path)
        db.add_file(session_id, transcription_path.name, str(transcription_path), "transcription")


        # Update session with title and summary
        db.update_session(session_id, {
            "title": content["title"],
            "summary": content["summary"]
        })

        # Step 2: Generate exposition
        with open(transcription_path, "r", encoding="utf-8") as f:
            transcription_text = f.read()
        
        exposition_content = processor.explain_notes(transcription_text)
        exposition_path = NOTES_DIR / f"exposition_{session_id}.md"
        with open(exposition_path, "w", encoding="utf-8") as f:
            f.write(exposition_content.text)
        db.add_file(session_id, exposition_path.name, str(exposition_path), "exposition")

        # Step 3: Generate questions
        with open(exposition_path, "r", encoding="utf-8") as f:
            exposition_text = f.read()
        
        question_content = processor.generate_questions(exposition_text)
        question_path = NOTES_DIR / f"questions_{session_id}.md"
        with open(question_path, "w", encoding="utf-8") as f:
            f.write(question_content.text)
        db.add_file(session_id, question_path.name, str(question_path), "questions")

        # Update session status
        db.update_session(session_id, {"status": "completed"})

        return {
            "message": "Notes processed successfully",
            "title": content["title"],
            "summary": content["summary"],
            "files": [
                {"type": "transcription", "file": f"/notes/{transcription_path.name}"},
                {"type": "exposition", "file": f"/notes/{exposition_path.name}"},
                {"type": "questions", "file": f"/notes/{question_path.name}"}
            ]
        }

    except Exception as e:
        db.update_session(session_id, {"status": "error"})
        logging.error(f"Error processing notes: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)