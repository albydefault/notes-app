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

# Mount static directories
app.mount("/static", StaticFiles(directory="app/static"), name="static")
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
    logging.info("=== Upload endpoint called ===")
    logging.info(f"Received {len(files)} files")
    
    if not files:
        logging.warning("No files received in request")
        raise HTTPException(status_code=400, detail="No files uploaded")

    # Create new session for this upload
    session_id = db.create_session()
    logging.info(f"Created new session: {session_id}")
    processed_files = []

    try:
        for file in files:
            logging.info(f"Processing file: {file.filename}")
            
            # Validate file extension
            if Path(file.filename).suffix.lower() not in ALLOWED_EXTENSIONS:
                logging.warning(f"Invalid file type: {file.filename}")
                raise HTTPException(status_code=400, 
                                 detail=f"Unsupported file type: {file.filename}")

            # Save uploaded file
            upload_path = UPLOAD_DIR / f"{session_id}_{file.filename}"
            logging.info(f"Saving file to: {upload_path}")
            
            with open(upload_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            
            logging.info(f"File saved successfully: {upload_path}")
            
            # Track original file
            db.add_file(session_id, file.filename, str(upload_path), "original")
            logging.info("File tracked in database")

            # Process the image
            logging.info("Starting image processing")
            processed_path = scanner.scan_image(upload_path)
            if processed_path:
                logging.info(f"Image processed successfully: {processed_path}")
                db.add_file(session_id, processed_path.name, str(processed_path), "scanned")
                processed_files.append(f"/processed/{processed_path.name}")
            else:
                logging.error(f"Failed to process image: {file.filename}")

        if not processed_files:
            logging.error("No files were successfully processed")
            db.update_session(session_id, {"status": "error"})
            raise HTTPException(status_code=400, detail="No files were successfully processed")

        db.update_session(session_id, {"status": "processing"})
        logging.info("Upload processing completed successfully")
        
        return {
            "message": f"Processed {len(processed_files)} files",
            "processed_files": processed_files,
            "session_id": session_id
        }

    except Exception as e:
        logging.error(f"Error during upload processing: {str(e)}")
        db.update_session(session_id, {"status": "error"})
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
        # processor.save_markdown(content, transcription_path)
        with open(transcription_path, "w", encoding="utf-8") as f:
            f.write(content["content"])
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

@app.get("/sessions")
async def list_sessions():
    """Get list of all note sessions."""
    try:
        sessions = db.get_all_sessions()
        return {
            "sessions": [{
                "id": session["id"],
                "title": session["title"],
                "created_at": session["created_at"],
                "status": session["status"],
                "summary": session["summary"]
            } for session in sessions]
        }
    except Exception as e:
        logging.error(f"Error listing sessions: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/sessions/{session_id}")
async def get_session(session_id: str):
    """Get details of a specific session including its files."""
    session = db.get_session_info(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Group files by type and transform paths to URLs
    files = session.get('files', [])
    organized_files = {
        'scanned': [],
        'generated': []
    }
    
    for file in files:
        file_type = file['file_type']
        if file_type == 'scanned':
            # Files in PROCESSED_DIR are mounted at /processed
            organized_files['scanned'].append({
                **file,
                'file': f"/processed/{Path(file['file_path']).name}"
            })
        elif file_type in ['transcription', 'exposition', 'questions']:
            # Files in NOTES_DIR are mounted at /notes
            organized_files['generated'].append({
                **file,
                'file': f"/notes/{Path(file['file_path']).name}"
            })
    
    return {
        "id": session["id"],
        "title": session["title"],
        "created_at": session["created_at"],
        "status": session["status"],
        "summary": session["summary"],
        "files": organized_files
    }

@app.get("/sessions-page")
async def sessions_page(request: Request):
    """Serve the sessions list page."""
    return templates.TemplateResponse("sessions.html", {"request": request})

@app.get("/view/notes/{filename}")
async def view_markdown(request: Request, filename: str):
    """Serve markdown file in a full-page view."""
    file_path = NOTES_DIR / filename
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
        
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
            
        return templates.TemplateResponse(
            "markdown_page.html", 
            {
                "request": request,
                "content": content,
                "title": filename
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/view/notes/{filename}")
async def view_markdown(request: Request, filename: str):
    """Serve markdown file in a full-page view."""
    file_path = NOTES_DIR / filename
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
        
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read().strip()  # Strip any leading/trailing whitespace
            
        # Extract a clean title from the filename
        title = (filename
                .replace('.md', '')
                .replace('_', ' ')
                .replace('-', ' ')
                .title())
        
        # If content starts with a # header, use that as title and remove it
        if content.startswith('# '):
            title_line = content.split('\n')[0]
            title = title_line.replace('# ', '').strip()
            content = '\n'.join(content.split('\n')[1:]).strip()
            
        return templates.TemplateResponse(
            "markdown_page.html", 
            {
                "request": request,
                "content": content,
                "title": title
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)