import os
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY")
NEWS_DATA_KEY = os.getenv("NEWS_DATA_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")  # optional