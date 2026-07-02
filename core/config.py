import os
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY")
NEWS_DATA_KEY = os.getenv("NEWS_DATA_KEY")

if not GROQ_API_KEY or not FINNHUB_API_KEY:
    raise ValueError("Missing API keys in .env")