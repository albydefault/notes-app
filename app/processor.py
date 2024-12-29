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

    def transcribe_notes(self, scan_folder: str) -> Dict[str, str]:
        """Transcribe all scanned notes with improved error handling."""
        logging.info(f"Transcribing notes from {scan_folder}")
        
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
            
            
            
            transcription_prompt =  f"""
            You are a highly meticulous and detail-oriented transcriptionist specializing in accurately transcribing handwritten notes into well-structured Markdown documents. Your transcriptions are known for their precision, clarity, and adherence to formatting standards. You are tasked with transcribing the notes titled: '{metadata['title']}'.

            Follow these instructions rigorously:

            1. **Page Separation:** Transcribe each page of the notes as a distinct section. Mark each page break with a horizontal rule (`---`) followed by the page number (e.g., `--- Page 1 ---`).
            2. **Mathematical Equations:** Render all mathematical equations using LaTeX formatting enclosed in dollar signs.
            3. **Diagrams and Special Formatting:** Describe any diagrams, tables, or unusual formatting clearly in brackets (e.g., `[Diagram showing a circuit with a resistor and capacitor]`, `[Table with columns for Name, Age, and City]`).
            4. **Structure and Emphasis:** Preserve the original structure and formatting of the notes. This includes bullet points, numbered lists, headings, underlines, and any other emphasis techniques used in the original.
            5. **Markdown Headers:** Use appropriate Markdown headers (##, ###, etc.) to reflect the hierarchical structure of the content.
            6. **Illegible Text:** If any part of the text is illegible or uncertain, indicate it using brackets like this: `[illegible]` or `[unclear: possible word?]`.
            7. **Context (If Applicable):** These notes are related to the field of [Specify Domain, e.g., 'organic chemistry', '18th-century literature']. This context may be helpful for accurate transcription.
            8. **Output Format:** Output the transcription in pure Markdown format. Do not use a code block.
            9. **Minimize Whitespace:** Minimize vertical whitespace throughout the document. Only use a single blank line between paragraphs, headings, or other elements when necessary for clarity or to signal a significant shift in topic. Do not skip lines unnecessarily.

            **Summary Section:**

            After transcribing all pages, create a comprehensive summary section at the end of the document. This summary should be concise yet informative and include:

            *   **Key Topics:** List the main subjects and themes covered in the notes.
            *   **Main Points:** Briefly summarize the most important points and conclusions.
            *   **Action Items:** If the notes specify any tasks or actions to be taken, list them clearly.
            *   **Questions Raised:** If the notes contain any explicit or implicit questions, document them here.

            Aim for a balance between brevity and comprehensiveness in your summary. Your goal is to create a transcription that is both accurate to the original handwritten notes and easy to read and understand in its Markdown format, adhering to the pure Markdown and minimal whitespace requirements. Please begin the transcription.
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
    
    def explain_notes(self, transcription_text: str):
        """Explain the transcribed notes using Gemini."""
        logging.info("Explaining transcribed notes")
        # Explanation prompt
        exposition_prompt = f"""
                            You are a distinguished professor renowned for your ability to synthesize complex material into clear, comprehensive, and engaging academic guides. Your task is to transform the provided transcribed notes into a complete and rigorous lesson suitable for advanced undergraduate students. Your tone should be formal and academic, yet approachable and conducive to learning. Assume your students have a foundational understanding of the broader subject matter but need a thorough explanation of the specific concepts covered in these notes.

                            Transform the following transcribed notes into a comprehensive academic guide, expanding on each concept with rigorous explanations, logically structured examples, and relevant contextual information. Begin immediately with the content itself, without any introductory phrases.

                            {transcription_text}

                            **Instructions:**

                            1. **Target Audience:** This guide is for advanced undergraduate students. Maintain a formal and academic tone that is also approachable and engaging. Assume students possess prerequisite knowledge but require in-depth clarification of these specific notes.
                            2. **Content Focus:** Begin directly with the reworked content of the notes. Do not include any preamble or introductory statements like "Here is a guide..." or "This document..." Dive straight into the subject matter.
                            3. **Depth of Explanation:** Provide thorough and rigorous explanations for each concept presented in the notes. Interpolate between the lines of the notes, filling in any gaps in reasoning or logic. Extrapolate beyond the notes to provide a broader understanding of the topic, but ensure all extrapolations are directly relevant and build upon the core concepts.
                            4. **Structure:** Reorganize and restructure the content of the notes as needed to create a logical flow that enhances understanding. Use clear headings, subheadings, and appropriate formatting (e.g., bullet points, numbered lists) to create a well-organized and easily navigable document. Maintain the format of the original notes where appropriate.
                            5. **Examples:** Illustrate concepts with well-chosen examples that follow naturally from the material. Where appropriate, present examples in tuples: a simpler introductory example, a more complicated example that builds on the first, and a more advanced example that demonstrates a sophisticated application of the concept. Ensure all examples are directly relevant to the material covered and contribute to a deeper understanding.
                            6. **Contextualization:** Weave in relevant contextual information to enhance understanding. This may include connections to related concepts within the field, brief historical context if it illuminates the topic, or discussions of practical applications where relevant. Ensure all contextual additions are directly tied to the core concepts and enhance the overall understanding.
                            7. **Mathematical Equations:** Use LaTeX format for equations. Explain each equation in detail, defining all variables and providing step-by-step derivations where necessary. Translate the mathematical concepts into clear, concise prose that complements the equations.
                            8. **Visual Aids:** If appropriate, suggest the inclusion of visual aids such as diagrams, charts, or illustrations to enhance understanding. Clearly describe the content and purpose of any suggested visuals.
                            9. **Conclusion:** Conclude with a concise yet thorough summary that reinforces the key concepts and takeaways from the lesson. This summary should serve as a valuable study tool for students.
                            10. **Output Format:** Output the guide in pure Markdown format. Do not use a code block.
                            11. **Minimize Whitespace:**  Minimize vertical whitespace throughout the document. Only use a single blank line between paragraphs, headings, or other elements when necessary for clarity or to signal a significant shift in topic. Do not skip lines unnecessarily.

                            Your goal is to create a definitive academic resource that transforms these transcribed notes into a comprehensive and engaging lesson for advanced undergraduate students. The final product should be a polished, self-contained document that stands alone as a complete guide to the subject matter covered in the notes, and should be formatted in pure markdown with minimal whitespace.
                            """

        exposition_content = self.model.generate_content([exposition_prompt])
        return exposition_content

    def generate_questions(self, exposition_text: str):
        """Generate questions based on the explained content."""
        logging.info("Generating questions from the explained content")

        question_prompt =   f"""
        You are a distinguished professor creating an exam to assess advanced undergraduate students' understanding of the material covered in the following academic guide. Your goal is to develop a comprehensive list of questions that thoroughly test comprehension at various levels of difficulty, categorized by topic.

        Generate a set of exam questions based on the academic guide provided below.

        {exposition_text}

        **Instructions:**

        1. **Target Audience:** The questions are for advanced undergraduate students who have studied the provided academic guide.
        2. **Question Types:** Create a mix of question types, including:
            *   **Recall:** Questions that test basic recall of facts, definitions, and concepts.
            *   **Comprehension:** Questions that assess understanding of the relationships between concepts and the ability to explain them in one's own words.
            *   **Application:** Questions that require students to apply the concepts to new situations or solve problems.
            *   **Analysis:** Questions that ask students to break down complex concepts into their constituent parts and examine the relationships between them.
            *   **Synthesis:** Questions that challenge students to combine different concepts to create new ideas or solutions.
            *   **Evaluation:** Questions that require students to make judgments about the value or validity of concepts or arguments.
        3. **Difficulty Levels:** Include questions of varying difficulty:
            *   **Easy:** Straightforward questions that test basic understanding.
            *   **Medium:** Questions that require a deeper understanding and may involve applying concepts or making connections.
            *   **Hard:** Challenging questions that demand critical thinking, synthesis, or evaluation.
        4. **Topic Categorization:** Organize the questions into categories based on the main topics covered in the academic guide. Use clear headings for each category.
        5. **Coverage:** Ensure that the questions comprehensively cover all the major topics and subtopics presented in the guide.
        6. **Clarity and Precision:** Formulate each question clearly and precisely, avoiding ambiguity or vagueness. Use the same formal, academic, yet approachable tone as the academic guide.
        7. **Mathematical Equations:** If applicable, include questions that involve interpreting, deriving, or applying equations from the guide. Use LaTeX format for all equations.
        8. **Number of Questions:** Aim for a total of [Specify Number] questions, distributed appropriately across the different question types, difficulty levels, and topics. Feel free to modify this as you see fit.
        9. **Answer Key (Optional):** While not required, you may optionally provide a concise answer key for each question.
        10. **Output Format:** Output the list of questions in pure Markdown format. Do not use a code block.
        11. **Minimize Whitespace:** Minimize vertical whitespace throughout the document. Only use a single blank line between questions when necessary for clarity. Do not skip lines unnecessarily.

        Your goal is to create a comprehensive and rigorous exam that effectively assesses advanced undergraduate students' understanding of the material in the provided academic guide.
        """
        
        question_content = self.model.generate_content([question_prompt])
        return question_content

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