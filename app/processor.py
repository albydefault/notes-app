import pathlib
from typing import List, Dict, Optional
import google.generativeai as genai
from PIL import Image
import json
import logging
from tenacity import retry, stop_after_attempt, wait_exponential
import os

class NoteProcessor:
    def __init__(self, api_key: str):
        """Initialize Gemini with API key and model configuration."""
        if not api_key:
            raise ValueError("Gemini API key is required")
            
        try:
            genai.configure(api_key=api_key)
            # Update: Using the correct model name
            self.model = genai.GenerativeModel('gemini-2.0-flash-exp')
            logging.info("Gemini API initialized successfully")
        except Exception as e:
            logging.error(f"Failed to initialize Gemini API: {str(e)}")
            raise

    def _load_images(self, scan_folder: str) -> List[Image.Image]:
        """Load and validate images from the scan folder."""
        folder = pathlib.Path(scan_folder)
        if not folder.exists():
            raise FileNotFoundError(f"Scan folder not found: {scan_folder}")
            
        image_files = sorted(
            [f for f in folder.glob("*.jpg") if f.name.startswith("scan_")]
        )
        
        if not image_files:
            raise ValueError(f"No valid image files found in {scan_folder}")
            
        images = []
        for f in image_files:
            try:
                img = Image.open(f)
                # Validate image size is within Gemini's limits (10MB per image)
                if os.path.getsize(f) > 10 * 1024 * 1024:
                    logging.warning(f"Image {f} exceeds 10MB limit, resizing...")
                    img.thumbnail((2000, 2000))  # Resize while maintaining aspect ratio
                images.append(img)
            except Exception as e:
                logging.error(f"Failed to load image {f}: {str(e)}")
                continue
                
        return images

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    def _generate_content(self, prompt: str, images: List[Image.Image]) -> Dict:
        """Send request to Gemini with retry logic."""
        try:
            response = self.model.generate_content([prompt, *images])
            
            if not response.text:
                raise ValueError("Empty response from Gemini")
                
            # Handle both JSON and markdown responses
            if prompt.lower().find("json") != -1:
                try:
                    # Add explicit instruction to ensure response is valid JSON
                    formatted_prompt = prompt.strip() + "\nIMPORTANT: Your response must be ONLY valid JSON with no additional text or formatting."
                    response = self.model.generate_content([formatted_prompt, *images])
                    response_text = response.text.strip()
                    
                    # Clean up common formatting issues
                    if response_text.startswith('```json'):
                        response_text = response_text[7:-3] if response_text.endswith('```') else response_text[7:]
                    return json.loads(response_text)
                except json.JSONDecodeError as e:
                    logging.error(f"Failed to parse JSON response: {str(e)}")
                    logging.error(f"Raw response: {response.text}")
                    return {"error": "Invalid JSON response", "raw_response": response.text}
            return {"text": response.text}
            
        except Exception as e:
            logging.error(f"Gemini API error: {str(e)}")
            raise

    def process_notes(self, scan_folder: str) -> Dict[str, str]:
        """Process all scanned notes with improved error handling."""
        logging.info(f"Processing notes from {scan_folder}")
        
        try:
            images = self._load_images(scan_folder)
            
            # Initial prompt for metadata
            initial_prompt =    """
                                You are a highly skilled document analyzer. These images are pages of handwritten notes.
                                Your task is to analyze the content and return ONLY a JSON object with the following structure, with no additional text or formatting:
                                {
                                    "title": "A meaningful and descriptive title (avoid generic terms like 'Untitled Notes')",
                                    "summary": "A 2-3 sentence summary of the main topics or content"
                                }

                                IMPORTANT: Return ONLY the JSON object with no explanation or additional text.
                                """

            
            metadata = self._generate_content(initial_prompt, images)
            if "error" in metadata:
                metadata = {
                    "title": "Untitled Notes",
                    "summary": "Content could not be summarized."
                }
            
            # Transcription prompt
            transcription_prompt =  f"""
                                    You are a professional transcription assistant. Your task is to transcribe handwritten notes into a structured markdown document.
                                    Use the title: {metadata['title']}.

                                    Follow these requirements:
                                    1. Transcribe each page separately.
                                    2. Mark page breaks with a horizontal rule (`---`) and page numbers.
                                    3. For any mathematical equations, use LaTeX formatting.
                                    4. Clearly label diagrams or special formatting with descriptions in [brackets].
                                    5. Maintain the original structure and emphasis, including bullet points, headings, and underlines.
                                    6. Add appropriate markdown headers (##, ###) based on the content structure.

                                    End the document with a detailed summary section, including:
                                    - Key Topics
                                    - Main Points
                                    - Action Items (if any)
                                    - Questions Raised (if any).
                                    """
            
            transcription = self._generate_content(transcription_prompt, images)
            
            return {
                "title": metadata["title"],
                "summary": metadata["summary"],
                "content": transcription.get("text", "Failed to transcribe notes.")
            }
            
        except Exception as e:
            logging.error(f"Failed to process notes: {str(e)}")
            raise

    def save_markdown(self, content: Dict[str, str], output_file: str):
        """Save processed content as markdown with error handling."""
        output_path = pathlib.Path(output_file)
        
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(f"# {content['title']}\n\n")
                f.write(f"*Summary: {content['summary']}*\n\n")
                f.write("---\n\n")
                f.write(content['content'])
                
            logging.info(f"Markdown file saved: {output_file}")
            
        except Exception as e:
            logging.error(f"Failed to save markdown file: {str(e)}")
            raise