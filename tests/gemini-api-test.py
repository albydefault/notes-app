import google.generativeai as genai
from config import GEMINI_API_KEY

api_key = GEMINI_API_KEY
genai.configure(api_key=api_key)
model = genai.GenerativeModel("gemini-2.0-flash-exp")

prompt = "Summarize the following text: Python is a versatile programming language."
response = model.generate_content([prompt])
print(response.text)
