# app/scanner.py
import cv2
import numpy as np
from pathlib import Path
from typing import Optional, List, Tuple
import logging
import re

class DocumentScanner:
    def __init__(self, target_height: int = 842):  # A4 height at 100 DPI
        self.target_height = target_height
    
    def sanitize_filename(self, filename: str) -> str:
        """Replace spaces and special characters with underscores."""
        return re.sub(r'[^\w\-_.]', '_', filename)

    def scan_image(self, image_path: Path) -> Optional[Path]:
        """Process a single image and return path to processed image."""
        try:
            logging.info(f"Starting processing for image: {image_path}")
            
            # Read image
            original_image = cv2.imread(str(image_path))
            if original_image is None:
                logging.error(f"Could not read image at {image_path}")
                raise ValueError(f"Could not read image at {image_path}")
            
            # Process image
            processed = self.process_image(original_image)
            if processed is None:
                logging.error(f"Could not process image at {image_path}")
                raise ValueError(f"Could not process image at {image_path}")
            
            # Save processed image
            sanitized_name = self.sanitize_filename(image_path.stem)
            output_path = image_path.parent.parent / "processed" / f"scan_{sanitized_name}.jpg"
            cv2.imwrite(str(output_path), processed)
            logging.info(f"Image processed successfully: {output_path}")
            
            return output_path

        except Exception as e:
            logging.error(f"Error processing {image_path}: {str(e)}")
            return None

    

    def process_image(self, image: np.ndarray) -> Optional[np.ndarray]:
        """Process a single image."""
        logging.debug("Converting image to grayscale")
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        logging.debug("Creating binary mask")
        mask = self._create_binary_mask(gray)
        logging.debug(f"Binary mask created with shape: {mask.shape}")
        
        logging.debug("Finding edge lines")
        vertical_lines, horizontal_lines = self._find_edge_lines(mask)
        logging.info(f"Found {len(vertical_lines)} vertical lines and {len(horizontal_lines)} horizontal lines")
        
        if not vertical_lines or not horizontal_lines:
            logging.warning("No sufficient lines found for intersection")
            return None

        logging.debug("Finding intersections")
        corners = self._find_intersections(vertical_lines, horizontal_lines, gray.shape[:2])
        logging.info(f"Found {len(corners)} corners")
        
        if corners is None:
            logging.error("Not enough corners detected; skipping image")
            return None


        if len(corners) < 4:
            logging.warning("Detected fewer than 4 corners, using all detected points as fallback")
            return corners


        logging.debug("Sorting corners and applying perspective transform")
        corners = self._sort_corners(corners)
        return self._perspective_transform(image, corners)


    def _create_binary_mask(self, gray: np.ndarray) -> np.ndarray:
        logging.debug("Applying Gaussian Blur")
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        logging.debug("Creating binary mask using adaptive threshold")
        mask = cv2.adaptiveThreshold(
            blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
            cv2.THRESH_BINARY_INV, 15, 10
        )
        return mask

    def _adaptive_threshold(self, gray: np.ndarray) -> np.ndarray:
        return cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
            cv2.THRESH_BINARY_INV, 15, 10
        )

    def _otsu_threshold(self, gray: np.ndarray) -> np.ndarray:
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        return binary

    def _canny_edges(self, gray: np.ndarray) -> np.ndarray:
        return cv2.Canny(gray, 100, 250)

    def _find_edge_lines(self, mask: np.ndarray, min_length: int = 50, max_lines: int = 100) -> Tuple[List[np.ndarray], List[np.ndarray]]:
        """Find vertical and horizontal lines in the image."""
        logging.debug("Running Canny edge detection and Hough line transform")
        edges = cv2.Canny(mask, 50, 150)
        
        lines = cv2.HoughLinesP(
            edges, 1, np.pi / 180, 30,
            minLineLength=min_length,
            maxLineGap=20
        )
        
        if lines is None:
            logging.warning("No lines found in the image")
            return [], []

        vertical_lines = []
        horizontal_lines = []
        
        for line in lines[:max_lines]:  # Limit the number of lines processed
            x1, y1, x2, y2 = line[0]
            angle = np.abs(np.degrees(np.arctan2(y2 - y1, x2 - x1)))
            
            if x2 - x1 == 0:  # Vertical line
                a, b, c = 1, 0, -x1
            else:
                a = (y2 - y1) / (x2 - x1)
                b = -1
                c = y1 - a * x1

            line_params = np.array([a, b, c]) / np.sqrt(a * a + b * b)  # Normalize

            if angle < 45 or angle > 135:  # Classify as vertical
                vertical_lines.append(line_params)
            else:  # Classify as horizontal
                horizontal_lines.append(line_params)

        logging.info(f"Filtered to {len(vertical_lines)} vertical and {len(horizontal_lines)} horizontal lines")
        return vertical_lines[:max_lines], horizontal_lines[:max_lines]


    def _find_intersections(self, vertical_lines, horizontal_lines, shape):
        """Find intersection points of vertical and horizontal lines."""
        logging.debug(f"Shape of image: {shape}")
        logging.debug(f"Number of vertical lines: {len(vertical_lines)}, horizontal lines: {len(horizontal_lines)}")
        intersections = []
        height, width = shape
        
        for v_line in vertical_lines:
            for h_line in horizontal_lines:
                a1, b1, c1 = v_line
                a2, b2, c2 = h_line
                
                det = a1 * b2 - a2 * b1
                if abs(det) < 1e-10:
                    continue
                
                x = (b1 * c2 - b2 * c1) / det
                y = (c1 * a2 - c2 * a1) / det
                
                margin = 0.2
                if (-width * margin <= x <= width * (1 + margin) and 
                    -height * margin <= y <= height * (1 + margin)):
                    intersections.append([x, y])
        
        logging.debug(f"Found {len(intersections)} intersection points")
        if not intersections:
            return np.array([])
        
        points = np.array(intersections)
        logging.debug(f"Clustering intersections, total points: {len(points)}")
        
        from sklearn.cluster import DBSCAN
        clustering = DBSCAN(eps=20, min_samples=1).fit(points)
        
        corners = []
        for label in set(clustering.labels_):
            if label == -1:
                continue
            cluster_points = points[clustering.labels_ == label]
            corner = np.mean(cluster_points, axis=0)
            corners.append(corner)
        
        logging.info(f"Detected {len(corners)} corners after clustering")
        
        # Ensure exactly 4 corners
        if len(corners) > 4:
            corners = self._select_best_corners(corners, width, height)
        elif len(corners) < 4:
            logging.warning("Fewer than 4 corners detected")
            return None  # Cannot process
        
        return np.array(corners)

    def _select_best_corners(self, corners: List[np.ndarray], width: int, height: int) -> List[np.ndarray]:
        """Select the 4 most relevant corners."""
        logging.debug("Selecting best corners")
        # Sort corners by proximity to the image corners
        image_corners = np.array([[0, 0], [width, 0], [width, height], [0, height]])
        selected_corners = []

        for img_corner in image_corners:
            distances = [np.linalg.norm(corner - img_corner) for corner in corners]
            selected_corners.append(corners[np.argmin(distances)])
        
        return selected_corners


    def _sort_corners(self, corners: np.ndarray) -> np.ndarray:
        """Sort corners: top-left, top-right, bottom-right, bottom-left."""
        center = np.mean(corners, axis=0)
        return np.array(sorted(corners, key=lambda p: np.arctan2(p[1] - center[1], p[0] - center[0]) + np.pi))

    def _perspective_transform(self, image: np.ndarray, corners: np.ndarray) -> np.ndarray:
        """Apply perspective transform with proper output size."""
        width = max(
            np.linalg.norm(corners[0] - corners[1]),
            np.linalg.norm(corners[2] - corners[3])
        )
        height = max(
            np.linalg.norm(corners[0] - corners[3]),
            np.linalg.norm(corners[1] - corners[2])
        )
        
        scale = self.target_height / height
        target_width = int(width * scale)
        target_height = self.target_height
        
        dst_points = np.array([
            [0, 0],
            [target_width - 1, 0],
            [target_width - 1, target_height - 1],
            [0, target_height - 1]
        ], dtype=np.float32)
        
        transform_matrix = cv2.getPerspectiveTransform(
            corners.astype(np.float32),
            dst_points
        )
        
        return cv2.warpPerspective(image, transform_matrix, (target_width, target_height))