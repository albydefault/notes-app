# app/main.py
from fastapi import FastAPI, UploadFile, File, Request, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import sys
import shutil
import uvicorn
from typing import List
import logging

from scanner import DocumentScanner
from processor import NoteProcessor

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

# Add project root to path
sys.path.append(str(Path(__file__).resolve().parent.parent))
from app.config import UPLOAD_DIR, PROCESSED_DIR, GEMINI_API_KEY

# Initialize FastAPI app
app = FastAPI(title="Notes Scanner")
scanner = DocumentScanner()

# Mount static directories
app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.mount("/processed", StaticFiles(directory="app/processed"), name="processed")
app.mount("/processed_notes", StaticFiles(directory="app/processed_notes"), name="processed_notes")


# Set up templates
templates = Jinja2Templates(directory="app/templates")

@app.get("/")
async def home(request: Request):
    """Serve the home page."""
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/upload")
async def upload_files(files: list[UploadFile]):
    """Handle file uploads and process images."""
    saved_files = []
    processed_files = []
    
    for file in files:
        # Save uploaded file
        file_path = UPLOAD_DIR / file.filename
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        saved_files.append(file_path)
        
        # Process the image
        processed_path = scanner.scan_image(file_path)
        if processed_path:
            # Construct URL for the frontend
            processed_url = f"/processed/{processed_path.name}"
            processed_files.append(processed_url)
    
    if not processed_files:
        raise HTTPException(status_code=400, detail="Could not process any of the uploaded images")
    
    return {
        "message": f"Successfully processed {len(processed_files)} files",
        "original_files": [str(f) for f in saved_files],
        "processed_files": processed_files,
    }

@app.get("/notes")
async def list_notes():
    """List all processed notes."""
    notes = list(PROCESSED_DIR.glob("*.md"))
    return {"notes": [str(note) for note in notes]}

if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)

from processor import NoteProcessor
import os

@app.post("/process-notes")
async def process_notes():
    processor = NoteProcessor(api_key=GEMINI_API_KEY)
    try:
        content = processor.process_notes("app/processed")
        processor.save_markdown(content, "app/processed_notes/notes.md")
        return {
            "status": "success",
            "title": content["title"],
            "summary": content["summary"],
            "markdown_file": "/processed_notes/notes.md"
        }
    except Exception as e:
        logging.error(f"Failed to process notes: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process notes: {str(e)}"
        )