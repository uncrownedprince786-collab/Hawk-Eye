from groq import Groq
import google.generativeai as genai
from .config import GROQ_API_KEY, GEMINI_API_KEY, OPENAI_API_KEY
import json
import numpy as np
import re

# ----- lazy clients (no crash if keys missing) -----
_groq_client = None
_gemini_model = None

def _get_groq():
    global _groq_client
    if _groq_client is None and GROQ_API_KEY:
        _groq_client = Groq(api_key=GROQ_API_KEY)
    return _groq_client

def _get_gemini():
    global _gemini_model
    if _gemini_model is None and GEMINI_API_KEY:
        genai.configure(api_key=GEMINI_API_KEY)
        _gemini_model = genai.GenerativeModel('gemini-1.5-flash')
    return _gemini_model

# ----- Prompt for AI -----
JUDGE = """You are World's No.1 Trader. Analyze ALL data. Provide a trade plan with precise entry, stop loss, and take profit levels. Explain WHY for each level. Include candlestick pattern analysis and news impact. Format: plain text, no markdown. Always include:
- Direction (LONG/SHORT/NO TRADE)
- Confidence 0-100
- Key support/resistance with reasons
- Spot trade plan
- Futures trade plan
- Risk note
- Invalidation condition"""

# ----- Rule-based engine (fallback) -----
def _rule_based(data: dict) -> str:
    try:
        symbol = data.get("symbol", "???")
        price = data.get("price_data", {}).get("price", 0)
        tech = data.get("technicals_1d", {}) or data.get("technicals", {})
        fg = data.get("fear_greed", {})
        news = data.get("news", [])
        cg = data.get("coingecko", {})
        # Multi-timeframe trend
        mtf = data.get("multi_timeframe", {})
        trend_4h = mtf.get("4H", {}).get("trend", "neutral") if mtf else "neutral"
        trend_1h = mtf.get("1H", {}).get("trend", "neutral") if mtf else "neutral"

        trend = tech.get("trend", "neutral")
        rsi = tech.get("rsi_14", 50)
        macd_dir = tech.get("macd_direction", "neutral")
        stoch_k = tech.get("stoch_k", 50)
        stoch_d = tech.get("stoch_d", 50)
        bb_upper = tech.get("bb_upper", price*1.1)
        bb_lower = tech.get("bb_lower", price*0.9)
        vwap = tech.get("vwap", price)
        atr = tech.get("atr_14", price*0.02)
        support = tech.get("support_20", price*0.95)
        resistance = tech.get("resistance_20", price*1.05)
        ema9 = tech.get("ema_9", price)
        ema21 = tech.get("ema_21", price)
        obv = tech.get("obv_trend", "neutral")
        fg_val = fg.get("value", 50)
        spoof = data.get("order_book", {}).get("spoof_alert", "")

        # Candlestick patterns from recent_candles (30 candles)
        candles = tech.get("recent_candles", [])
        pattern_score = 0
        pattern_desc = []
        if len(candles) >= 3:
            last = candles[-1]
            prev = candles[-2]
            # Doji
            body = abs(last["close"] - last["open"])
            total_range = last["high"] - last["low"]
            if total_range > 0 and body < total_range * 0.1:
                pattern_desc.append("Doji")
            # Hammer
            lower_wick = last["open"] - last["low"] if last["close"] > last["open"] else last["close"] - last["low"]
            upper_wick = last["high"] - last["close"] if last["close"] > last["open"] else last["high"] - last["open"]
            if body > 0 and lower_wick > 2*body and upper_wick < body:
                pattern_desc.append("Hammer (bullish)")
                pattern_score += 2
            # Shooting star
            if body > 0 and upper_wick > 2*body and lower_wick < body:
                pattern_desc.append("Shooting Star (bearish)")
                pattern_score -= 2
            # Engulfing bullish
            if (prev["close"] < prev["open"] and last["close"] > last["open"] and
                last["open"] < prev["close"] and last["close"] > prev["open"]):
                pattern_desc.append("Bullish Engulfing")
                pattern_score += 3
            # Engulfing bearish
            if (prev["close"] > prev["open"] and last["close"] < last["open"] and
                last["open"] > prev["close"] and last["close"] < prev["open"]):
                pattern_desc.append("Bearish Engulfing")
                pattern_score -= 3
        # Three white soldiers / black crows over last 3 candles
        if len(candles) >= 3:
            c3, c2, c1 = candles[-3], candles[-2], candles[-1]
            if all(c["close"] > c["open"] for c in [c3,c2,c1]) and c1["close"] > c2["close"] > c3["close"]:
                pattern_desc.append("Three White Soldiers (strong bullish)")
                pattern_score += 4
            if all(c["close"] < c["open"] for c in [c3,c2,c1]) and c1["close"] < c2["close"] < c3["close"]:
                pattern_desc.append("Three Black Crows (strong bearish)")
                pattern_score -= 4

        # News keyword sentiment
        news_sent = 0
        news_highlights = []
        pos_words = ["surge","rally","bullish","gain","rise","jump","soar","breakout","upgrade","buy","adoption","partnership"]
        neg_words = ["crash","plunge","bearish","drop","fall","decline","sell","downgrade","fear","loss","hack","regulation","ban"]
        for n in news[:5]:
            text = (n.get("headline","") + " " + n.get("summary","")).lower()
            pos = sum(1 for w in pos_words if re.search(r'\b' + w + r'\b', text))
            neg = sum(1 for w in neg_words if re.search(r'\b' + w + r'\b', text))
            score = pos - neg
            if score != 0:
                news_sent += score
                news_highlights.append(n.get("headline","")[:80])

        # Scoring
        reasons = []
        score = 0

        # Primary trend
        if trend == "bullish":
            score += 2; reasons.append("Primary trend bullish")
        elif trend == "bearish":
            score -= 2; reasons.append("Primary trend bearish")

        # Multi-timeframe alignment
        if trend == trend_4h == "bullish":
            score += 2; reasons.append("1D/4H alignment bullish")
        elif trend == trend_4h == "bearish":
            score -= 2; reasons.append("1D/4H alignment bearish")
        elif trend != trend_4h:
            reasons.append("Multi-timeframe conflict, caution")

        # RSI
        if rsi < 30:
            score += 2; reasons.append(f"RSI oversold ({rsi:.1f})")
        elif rsi > 70:
            score -= 2; reasons.append(f"RSI overbought ({rsi:.1f})")

        # MACD
        if macd_dir == "bullish":
            score += 1.5; reasons.append("MACD bullish")
        else:
            score -= 1.5; reasons.append("MACD bearish")

        # Stochastic
        if stoch_k > stoch_d and stoch_k < 80:
            score += 1
        elif stoch_k < stoch_d and stoch_k > 20:
            score -= 1

        # Bollinger Bands
        if price < bb_lower:
            score += 1.5; reasons.append("Price below lower Bollinger Band")
        elif price > bb_upper:
            score -= 1.5; reasons.append("Price above upper Bollinger Band")

        # VWAP
        if price > vwap:
            score += 1
        else:
            score -= 1

        # OBV
        if obv == "rising":
            score += 1; reasons.append("OBV rising")

        # Fear & Greed contrarian
        if fg_val <= 20:
            score += 2; reasons.append(f"Extreme Fear ({fg_val}) - contrarian buy")
        elif fg_val >= 80:
            score -= 2; reasons.append(f"Extreme Greed ({fg_val}) - contrarian sell")

        # Patterns
        score += pattern_score
        if pattern_desc:
            reasons.append("Patterns: " + ", ".join(pattern_desc))

        # News sentiment
        if news_sent > 0:
            score += 2; reasons.append("News sentiment positive")
        elif news_sent < 0:
            score -= 2; reasons.append("News sentiment negative")

        # Supply scarcity (CoinGecko)
        if cg.get("supply_scarcity") == "scarce":
            score += 0.5
        elif cg.get("supply_scarcity") == "abundant":
            score -= 0.3

        # ATH distance
        ath_dist = cg.get("ath_distance_pct")
        if ath_dist is not None and ath_dist < -50:
            score += 1; reasons.append(f"Price {abs(ath_dist):.0f}% below ATH")

        # Spoof detection
        if spoof and "SPOOFING" in spoof.upper():
            score -= 3; reasons.append("Order book spoofing detected!")

        # Final decision
        if score >= 4:
            direction, conf = "LONG", min(90, 50 + int(score * 4))
        elif score <= -4:
            direction, conf = "SHORT", min(90, 50 + int(abs(score) * 4))
        else:
            direction, conf = "NO TRADE", 30

        # Trade parameters
        if direction == "LONG":
            entry = round(price, 2)
            stop = round(min(support, price - 1.5*atr), 2)
            tp1 = round(price + atr*2, 2)
            tp2 = round(price + atr*4, 2)
            tp3 = round(resistance, 2)
            rr = f"1:{round((tp1-price)/max(price-stop,0.01),1)}"
            pos_size = "2%" if conf >= 70 else "1.5%"
        elif direction == "SHORT":
            entry = round(price, 2)
            stop = round(max(resistance, price + 1.5*atr), 2)
            tp1 = round(price - atr*2, 2)
            tp2 = round(price - atr*4, 2)
            tp3 = round(support, 2)
            rr = f"1:{round((price-tp1)/max(stop-price,0.01),1)}"
            pos_size = "2%" if conf >= 70 else "1.5%"
        else:
            entry = stop = tp1 = tp2 = tp3 = 0
            rr = "N/A"
            pos_size = "0%"

        return f"""ASSET: {symbol}
FINAL DECISION: {direction}
CONFIDENCE: {conf}/100 (Self-contained engine)
REASONING: {'; '.join(reasons[:6])}

--- KEY LEVELS EXPLAINED ---
Support: ${support} [WHY: 20-period low, volume cluster]
Resistance: ${resistance} [WHY: 20-period high]
VWAP: ${vwap:.2f} [WHY: institutional reference price]
ATR (14): ${atr:.2f} [WHY: average daily range]

--- CANDLESTICK PATTERNS ---
{', '.join(pattern_desc) if pattern_desc else 'No strong pattern detected'}

--- NEWS SENTIMENT ---
{' ; '.join(news_highlights[:3]) if news_highlights else 'No significant news impact'}

--- SPOT TRADE ---
Direction: {direction}
Entry Zone: ${entry}
Stop Loss: ${stop} [WHY: below support/ATR]
Take Profit 1: ${tp1}
Take Profit 2: ${tp2}
Take Profit 3: ${tp3}
Risk/Reward: {rr}
Position Size: {pos_size}

--- FUTURES TRADE ---
Direction: {direction}
Leverage: 2x (max)
Entry: ${entry}
Stop Loss: ${stop}
Take Profit 1: ${tp1}
Take Profit 2: ${tp2}

--- RISK NOTE ---
Self-contained analysis based on technical, candlestick patterns, and news keywords. Always use proper risk management.

--- INVALIDATION ---
Trade invalid if price closes beyond ${stop}."""
    except Exception as e:
        return f"Trade plan generation failed: {str(e)}"

def generate_trade_plan(data: dict) -> str:
    user_prompt = f"Data:\n{json.dumps(data, default=str)}\n\nDeliver trade plan."

    # 1) Try Groq
    groq = _get_groq()
    if groq:
        try:
            resp = groq.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role":"system","content":JUDGE},{"role":"user","content":user_prompt}],
                temperature=0.3, max_tokens=1500, timeout=20
            )
            return resp.choices[0].message.content.strip()
        except: pass

    # 2) Try Gemini
    gemini = _get_gemini()
    if gemini:
        try:
            full = JUDGE + "\n\n" + user_prompt
            resp = gemini.generate_content(full, generation_config={"temperature":0.3,"max_output_tokens":1200})
            if resp.text: return resp.text.strip()
        except: pass

    # 3) Fallback to rule-based engine
    return _rule_based(data)
