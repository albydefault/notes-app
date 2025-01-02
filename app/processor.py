import pathlib
from pathlib import Path
from typing import List, Dict, Optional
import google.generativeai as genai
from PIL import Image
import json
import logging
from tenacity import retry, stop_after_attempt, wait_exponential
import os
from prompt_handler import PromptTemplateHandler
from datetime import datetime

class NoteProcessor:
    def __init__(self, api_key: str):
        """Initialize Gemini with API key and model configuration."""
        if not api_key:
            raise ValueError("Gemini API key is required")
            
        try:
            genai.configure(api_key=api_key)
            self.model = genai.GenerativeModel('gemini-2.0-flash-exp')
            self.prompt_handler = PromptTemplateHandler(Path(__file__).parent / 'templates' / 'prompts')
            logging.info("Gemini API and prompt templates initialized successfully")
        except Exception as e:
            logging.error(f"Failed to initialize: {str(e)}")
            raise

    def _load_images(self, image_paths: List[Path]) -> List[Image.Image]:
        """Load and validate specific image files."""
        if not image_paths:
            raise ValueError("No image paths provided")
            
        images = []
        for path in image_paths:
            try:
                img = Image.open(path)
                # Validate image size is within Gemini's limits (10MB per image)
                if os.path.getsize(path) > 10 * 1024 * 1024:
                    logging.warning(f"Image {path} exceeds 10MB limit, resizing...")
                    img.thumbnail((2000, 2000))
                images.append(img)
            except Exception as e:
                logging.error(f"Failed to load image {path}: {str(e)}")
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

    def transcribe_notes(self, image_paths: List[Path]) -> Dict[str, str]:
        """Transcribe specific notes with improved error handling."""
        logging.info(f"Transcribing {len(image_paths)} notes")
        
        try:
            images = self._load_images(image_paths)
            
            if not images:
                raise ValueError("No valid images to process")
            
            # Get metadata first
            initial_prompt = """
            You are a highly skilled document analyzer. These images are pages of handwritten notes.
            Your task is to analyze the content and return ONLY a JSON object with the following structure:
            {
                "title": "A meaningful and descriptive title (avoid generic terms like 'Untitled Notes')",
                "summary": "A 2-3 sentence summary of the main topics or content"
            }
            """
            
            metadata = self._generate_content(initial_prompt, images)
            
            # Get transcription using template
            transcription_prompt = self.prompt_handler.format_template(
                'transcription',
                title=metadata.get('title', 'Untitled Notes'),
            )
            transcription = self._generate_content(transcription_prompt, images)
            
            return {
                "title": metadata.get("title", "Untitled Notes"),
                "summary": metadata.get("summary", "Content could not be summarized."),
                "content": transcription.get("text", "Failed to transcribe notes.")
            }
            
        except Exception as e:
            logging.error(f"Failed to process notes: {str(e)}")
            raise
    
    def explain_notes(self, transcription_text: str):
        """Explain the transcribed notes using Gemini."""
        logging.info("Explaining transcribed notes")
        
        exposition_prompt = self.prompt_handler.format_template(
            'exposition',
            transcription_text=transcription_text,
            current_date = datetime.now().strftime("%Y-%m-%d"),

        )
        return self.model.generate_content([exposition_prompt])

    def generate_questions(self, exposition_text: str):
        """Generate questions based on the explained content."""
        logging.info("Generating questions from the explained content")

        questions_prompt = self.prompt_handler.format_template(
            'questions',
            exposition_text=exposition_text,
            current_date = datetime.now().strftime("%Y-%m-%d"),
        )
        return self.model.generate_content([questions_prompt])

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