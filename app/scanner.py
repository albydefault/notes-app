import cv2
import numpy as np
from pathlib import Path
from typing import Optional
import logging
from PIL import Image
from PIL.ExifTags import TAGS
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

    def find_document_boundaries(self, image: np.ndarray) -> tuple[int, int]:
        """Find document top and bottom boundaries using rolling intensity analysis.
        
        Args:
            image: CV2 image array
            
        Returns:
            tuple[int, int]: (top_y, bottom_y) coordinates
        """
        # Convert to grayscale if needed
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image

        height = gray.shape[0]
        
        # Calculate mean intensity for each row
        row_means = np.mean(gray, axis=1)
        
        # Calculate rolling average
        window_size = 20
        rolling_avg = np.convolve(row_means, np.ones(window_size)/window_size, mode='valid')
        
        # Calculate rate of change
        intensity_change = np.diff(rolling_avg)
        
        # Find significant changes
        threshold = np.std(intensity_change) * 2  # Adaptive threshold
        
        # Find top boundary
        top_y = 0
        for i in range(window_size, len(intensity_change)):
            if abs(intensity_change[i]) > threshold:
                # Found significant change - roll back by 50 pixels
                top_y = max(0, i - 25)
                break
                
        # If no significant change at top, keep original top
        if top_y == 0:
            logging.info("No significant intensity change found at top, using original top")
        
        # Find bottom boundary
        bottom_y = height
        for i in range(len(intensity_change)-1, window_size, -1):
            if abs(intensity_change[i]) > threshold:
                # Found significant change - add small padding
                bottom_y = min(height, i + 25)
                break
        
        logging.info(f"Found document boundaries - Top: {top_y}, Bottom: {bottom_y}")
        return top_y, bottom_y

    def crop_to_content(self, image: Image.Image) -> Image.Image:
        """Find document boundaries and crop to them."""
        # Convert PIL Image to CV2 format for processing
        cv_image = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
        
        # Find boundaries
        top_y, bottom_y = self.find_document_boundaries(cv_image)
        
        # Crop image
        return image.crop((0, top_y, image.width, bottom_y))

    def scan_image(self, image_path: Path) -> Optional[Path]:
        """Process a single image and return path to processed image."""
        try:
            logging.info(f"Starting processing for image: {image_path}")
        
            # Load image with PIL
            original_image = Image.open(str(image_path))
            
            # Check EXIF orientation
            exif = original_image.getexif()
            if exif and exif.get(274):  # 274 is the orientation tag
                orientation = exif.get(274)
                logging.info(f"EXIF Orientation: {orientation}")
                # Define rotations based on EXIF orientation values
                orientation_to_rotation = {
                    1: 0,      # Normal
                    3: 180,    # Rotate 180
                    6: -90,    # Rotate 270 CCW (same as 90 CW)
                    8: 90      # Rotate 90 CCW
                }
                if orientation in orientation_to_rotation:
                    rotation = orientation_to_rotation[orientation]
                    if rotation != 0:
                        original_image = original_image.rotate(rotation, expand=True)
                        logging.info(f"Rotated image by {rotation} degrees based on EXIF orientation")

            
            
            # Process with Docuwarp and log
            unwarped_image = self.unwarp.inference(original_image)
            if unwarped_image is None:
                logging.error(f"Could not process image at {image_path}")
                raise ValueError(f"Could not process image at {image_path}")
            logging.info(f"Unwarped image dimensions: {unwarped_image.size}")
            
            # Log before cropping
            logging.info(f"Image orientation before crop: {unwarped_image.size}")
            cropped_image = self.crop_to_content(unwarped_image)
            logging.info(f"Image dimensions after crop: {cropped_image.size}")
            
            
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