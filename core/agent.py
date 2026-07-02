from groq import Groq
from .config import GROQ_API_KEY
import json

client = Groq(api_key=GROQ_API_KEY)

JUDGE = """You are World's No.1 Trader. Analyze ALL data. EDUCATE user with [WHY:] after every claim.

SECTIONS REQUIRED:
--- WHAT THE CANDLES SAY --- [Pattern from recent_candles. WHY it matters]
--- WHAT NEWS INDICATES --- [Headline impact. Event risk. WHY]
--- MULTI-TIMEFRAME CHECK --- [1D vs 4H vs 1H alignment. WHY]
--- INDICATORS --- RSI, MACD, Stoch, BB, VWAP, ATR each with WHY
--- ORDER FLOW --- Bid/Ask imbalance. Spoof status. WHY
--- ON-CHAIN/FUNDAMENTAL --- ATH distance, supply, market cap. WHY
--- SENTIMENT --- Fear & Greed. Contrarian? WHY
--- KEY LEVELS --- S1,S2,R1,R2 each with WHY
--- SPOT TRADE --- Direction, Entry, Stop, TP1,TP2,TP3, R:R, Position %. Each with WHY
--- FUTURES TRADE --- Direction, Leverage, Entry, Stop, TP1,TP2. Each with WHY
--- RISK LESSON --- One trading principle from this setup
--- INVALIDATION --- Price/condition that proves trade wrong. WHY
--- TRADER'S NOTE --- One line market wisdom

FORMAT: Plain text. No markdown. No emojis. Use [WHY:] after EVERY data point."""

def generate_trade_plan(data: dict) -> str:
    try:
        data_str = json.dumps(data, default=str)
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": JUDGE},
                {"role": "user", "content": f"Data:\n{data_str}\n\nDeliver complete trade plan with ALL sections. Include [WHY:] after every claim. Minimum 800 words."}
            ],
            temperature=0.3,
            max_tokens=2000,
            timeout=30
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"Trade plan generation failed: {str(e)}"