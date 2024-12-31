import cv2
import numpy as np
from pathlib import Path
from typing import Optional
import logging
from PIL import Image
from docuwarp.unwarp import Unwarp

class DocumentScanner:
    def __init__(self, target_width: int = 595, use_gpu: bool = False):
        """Initialize the document scanner with Docuwarp."""
        self.target_width = target_width
        
        # Initialize Docuwarp with appropriate provider
        providers = ["CUDAExecutionProvider"] if use_gpu else ["CPUExecutionProvider"]
        try:
            self.unwarp = Unwarp(providers=providers)
            logging.info(f"Initialized Docuwarp with providers: {providers}")
        except Exception as e:
            logging.error(f"Failed to initialize Docuwarp: {str(e)}")
            raise

    def sanitize_filename(self, filename: str) -> str:
        """Replace spaces and special characters with underscores."""
        import re
        return re.sub(r'[^\w\-_.]', '_', filename)

    def find_document_end(self, image: np.ndarray) -> Optional[int]:
        """Find where the document ends by detecting the first significant change
        in intensity scanning from top to bottom.
        
        Args:
            image: CV2 image array
            
        Returns:
            Optional[int]: Y-coordinate of document end or None if detection fails
        """
        # Convert to grayscale if needed
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image

        height = gray.shape[0]
        
        # Calculate mean intensity for each row
        row_means = np.mean(gray, axis=1)
        
        # Get baseline from the first few rows (which we know are part of the document)
        baseline = np.mean(row_means[:20])
        threshold = 50  # Minimum intensity difference to consider significant
        
        # Scan from top to bottom looking for first significant change
        for i in range(20, height):
            if abs(row_means[i] - baseline) > threshold:
                # Back up a few pixels to ensure we include all content
                return min(height, i + 5)
                
        return None

    def crop_to_content(self, image: Image.Image) -> Image.Image:
        """Find where the document ends and crop to it."""
        # Convert PIL Image to CV2 format for processing
        cv_image = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
        doc_end = self.find_document_end(cv_image)
        
        if doc_end is None:
            logging.warning("Could not detect document end, using original image")
            return image
            
        # Crop from top to detected end
        return image.crop((0, 0, image.width, doc_end))

    def scan_image(self, image_path: Path) -> Optional[Path]:
        """Process a single image and return path to processed image."""
        try:
            logging.info(f"Starting processing for image: {image_path}")
            
            # Load image with PIL
            original_image = Image.open(str(image_path))
            if not original_image:
                logging.error(f"Could not read image at {image_path}")
                raise ValueError(f"Could not read image at {image_path}")

            # Process image with Docuwarp
            unwarped_image = self.unwarp.inference(original_image)
            if unwarped_image is None:
                logging.error(f"Could not process image at {image_path}")
                raise ValueError(f"Could not process image at {image_path}")
            
            # Detect content and crop
            cropped_image = self.crop_to_content(unwarped_image)
            
            # Resize to target width while maintaining aspect ratio
            orig_width, orig_height = cropped_image.size
            aspect_ratio = orig_height / orig_width
            target_height = int(self.target_width * aspect_ratio)
            resized_image = cropped_image.resize(
                (self.target_width, target_height), 
                Image.Resampling.LANCZOS
            )
            
            # Prepare output path
            sanitized_filename = self.sanitize_filename(image_path.stem)
            output_path = image_path.parent.parent / "processed" / f"scan_{sanitized_filename}.jpg"
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Save with compression
            self._save_compressed_image(resized_image, output_path)
            
            logging.info(f"Image processed and saved successfully: {output_path}")
            return output_path

        except Exception as e:
            logging.error(f"Error processing {image_path}: {str(e)}")
            return None

    def _save_compressed_image(self, image: Image.Image, output_path: Path, target_size_kb: int = 200):
        """Save image with compression to ensure size is under target_size_kb."""
        quality = 95
        
        while quality > 10:
            # Save the image to a temporary location
            temp_path = str(output_path) + ".temp"
            image.save(temp_path, format="JPEG", quality=quality, optimize=True)
            
            # Check file size
            file_size_kb = Path(temp_path).stat().st_size / 1024
            if file_size_kb <= target_size_kb:
                Path(temp_path).rename(output_path)
                logging.info(f"Compressed image to {file_size_kb:.2f} KB with quality {quality}")
                return
            
            # Reduce quality for next iteration
            quality -= 5
            Path(temp_path).unlink(missing_ok=True)
        
        # If compression fails, save with lowest acceptable quality
        image.save(output_path, format="JPEG", quality=10, optimize=True)
        logging.warning(f"Could not achieve target size. Final size: {Path(output_path).stat().st_size / 1024:.2f} KB")