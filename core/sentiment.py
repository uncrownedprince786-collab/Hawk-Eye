from groq import Groq
from .config import GROQ_API_KEY
import json

def _get_groq_client():
    """Return a Groq client only if the API key is available, else None."""
    if not GROQ_API_KEY:
        return None
    return Groq(api_key=GROQ_API_KEY)

def analyze_sentiment(news_items: list) -> dict:
    if not news_items:
        return {"score": 0.0, "summary": "No news available."}

    client = _get_groq_client()
    if not client:
        return {"score": 0.0, "summary": "Sentiment analysis unavailable (no API key)."}

    headlines = "\n".join([n["headline"] for n in news_items[:5]])
    prompt = f"""Analyze the sentiment of these financial news headlines. Return a JSON with keys:
- score: float between -1 (very negative) and 1 (very positive)
- summary: brief explanation (max 200 chars).

Headlines:
{headlines}

Output only the JSON, no extra text."""
    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=150,
            timeout=15
        )
        return json.loads(response.choices[0].message.content)
    except:
        return {"score": 0.0, "summary": "Sentiment analysis failed."}