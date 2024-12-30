# Notes Scanner

A web application that processes handwritten notes using computer vision and AI to create useful study materials.

## Features

- Upload and process handwritten notes
- Automatic document scanning and enhancement
- AI-powered processing to generate:
  - Text transcription
  - Detailed explanations
  - Study questions
- Session-based organization
- Mobile-friendly interface

## Setup

1. Install requirements:
```
pip install -r requirements.txt
```

2. Create a config.py file based on config_sample.py and add your Gemini API key

3. Run the application:
```
python app/main.py
```

The server will start at http://127.0.0.1:8000

## Usage

1. Visit the homepage and upload images of your handwritten notes
2. The system will process the images to enhance readability
3. AI will analyze the content and generate study materials
4. Access your processed notes and materials from the Sessions page

## Directory Structure

```
app/
├── static/          # Static assets (CSS, JavaScript)
├── templates/       # HTML templates
└── main.py         # Main application file
data/
├── uploads/        # Temporary storage for uploads
├── processed/      # Processed images
└── notes/          # Generated study materials
```

## Requirements

- Python 3.8+
- FastAPI
- OpenCV
- Google Gemini AI
- Other dependencies listed in requirements.txt

## Notes

- Images are processed locally
- Content generation requires internet connection for AI processing
- Recommended image format: JPG or PNG
