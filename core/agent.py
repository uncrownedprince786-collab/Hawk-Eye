from groq import Groq
import google.generativeai as genai
from .config import GROQ_API_KEY, GEMINI_API_KEY, OPENAI_API_KEY
import json

# Initialize Groq
groq_client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

# Initialize Gemini
gemini_model = None
if GEMINI_API_KEY:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        gemini_model = genai.GenerativeModel('gemini-1.5-flash')
    except Exception as e:
        print(f"Gemini init warning: {e}")

# Compact Judge prompt
JUDGE = """You are World's No.1 Trader. Analyze ALL data. EDUCATE user with [WHY:] after every claim.

SECTIONS REQUIRED:
--- MARKET SITUATION ---
--- WHAT THE DATA SHOWS --- (5-7 points, each with [WHY:])
--- NEWS IMPACT ---
--- MULTI-TIMEFRAME CHECK ---
--- INDICATORS --- RSI, MACD, Stoch, BB, VWAP, ATR. Each with WHY
--- ORDER FLOW --- Bid/Ask imbalance, spoof. WHY
--- ON-CHAIN/FUNDAMENTALS ---
--- SENTIMENT --- Fear & Greed. WHY
--- KEY LEVELS --- S1,S2,R1,R2 with WHY
--- SPOT TRADE --- Direction, Entry, Stop, TP1,TP2,TP3, R:R, Position %. Each with WHY
--- FUTURES TRADE --- Direction, Leverage, Entry, Stop, TP1,TP2. WHY
--- RISK LESSON ---
--- INVALIDATION --- Price/condition. WHY
--- TRADER'S NOTE ---

FORMAT: Plain text. No markdown. No emojis."""

def generate_trade_plan(data: dict) -> str:
    user_prompt = f"Data:\n{json.dumps(data, default=str)}\n\nDeliver complete trade plan with ALL sections. Include [WHY:] after every claim."

    # 1st: Groq
    if groq_client:
        try:
            resp = groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role":"system","content":JUDGE},{"role":"user","content":user_prompt}],
                temperature=0.3, max_tokens=1500, timeout=20
            )
            return resp.choices[0].message.content.strip()
        except Exception:
            pass

    # 2nd: Gemini (reliable free fallback)
    if gemini_model:
        try:
            full_prompt = JUDGE + "\n\n" + user_prompt
            resp = gemini_model.generate_content(
                full_prompt,
                generation_config={"temperature":0.3,"max_output_tokens":1200}
            )
            if resp.text:
                return resp.text.strip()
        except Exception:
            pass

    # 3rd: OpenAI (if key set)
    if OPENAI_API_KEY:
        try:
            from openai import OpenAI
            oc = OpenAI(api_key=OPENAI_API_KEY)
            resp = oc.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role":"system","content":"You are a trading expert. Provide a clear trade plan with entry, stop loss, take profit, and reasoning."},
                          {"role":"user","content":user_prompt}],
                temperature=0.3, max_tokens=800, timeout=20
            )
            return resp.choices[0].message.content.strip()
        except Exception:
            pass

    # Final fallback: rule-based
    return _rule_based(data)

def _rule_based(data: dict) -> str:
    try:
        p = data.get("price_data", {}).get("price", 0)
        tech = data.get("technicals_1d", {}) or data.get("technicals", {})
        fg = data.get("fear_greed", {})
        trend = tech.get("trend", "neutral")
        rsi = tech.get("rsi_14", 50)
        atr = tech.get("atr_14", p * 0.02)
        support = tech.get("support_20", p * 0.95)
        resistance = tech.get("resistance_20", p * 1.05)
        fg_val = fg.get("value", 50)

        if trend == "bullish" and rsi < 70 and fg_val < 40:
            dir, entry = "LONG", p
            stop = min(support, p - 1.5 * atr)
            tp1, tp2 = p + atr * 2, p + atr * 4
        elif trend == "bearish" and rsi > 30 and fg_val > 60:
            dir, entry = "SHORT", p
            stop = max(resistance, p + 1.5 * atr)
            tp1, tp2 = p - atr * 2, p - atr * 4
        else:
            dir, entry, stop, tp1, tp2 = "NO TRADE", 0, 0, 0, 0

        return f"""ASSET: {data.get('symbol', 'Unknown')}
FINAL DECISION: {dir}
CONFIDENCE: Medium (rule-based fallback)

--- SPOT TRADE ---
Direction: {dir}
Entry: {entry}
Stop Loss: {stop}
Take Profit 1: {tp1}
Take Profit 2: {tp2}
Risk/Reward: approx 1:2
Position Size: 1-2% of capital

--- NOTE ---
Automated plan using technical indicators. AI services were unavailable."""
    except:
        return "Trade plan generation failed completely. Please try again later."