from groq import Groq
import google.generativeai as genai
from .config import GROQ_API_KEY, GEMINI_API_KEY, OPENAI_API_KEY
import json
import numpy as np
import re
from datetime import datetime, timezone

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

# ----- Prompt for AI (if used) -----
JUDGE = """You are World's No.1 Trader. Analyze ALL data. Provide a trade plan with precise entry, stop loss, and take profit levels. Explain WHY for each level. Include candlestick pattern analysis and news impact. Format: plain text, no markdown. Always include:
- Direction (LONG/SHORT/NO TRADE)
- Confidence 0-100
- Key support/resistance with reasons
- Spot trade plan
- Futures trade plan
- Risk note
- Invalidation condition"""

# =====================================================================
#  IMPROVED RULE‑BASED ENGINE (production‑grade)
# =====================================================================
def _rule_based(data: dict) -> str:
    try:
        symbol = data.get("symbol", "???")
        price = data.get("price_data", {}).get("price", 0) or 0
        tech = data.get("technicals", {}) or data.get("technicals_1d", {})
        fg = data.get("fear_greed", {})
        news = data.get("news", [])
        cg = data.get("coingecko", {})
        timestamp = data.get("timestamp_utc", datetime.now(timezone.utc).isoformat())
        order_book = data.get("order_book", {})

        # Basic indicators
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
        spoof = order_book.get("spoof_alert", "")

        # ----- Candlestick Patterns (extended) -----
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
            # Hammer / Hanging Man
            lower_wick = (last["open"] if last["close"] > last["open"] else last["close"]) - last["low"]
            upper_wick = last["high"] - (last["close"] if last["close"] > last["open"] else last["open"])
            if body > 0 and lower_wick > 2*body and upper_wick < body:
                pattern_desc.append("Hammer (bullish)")
                pattern_score += 2
            if body > 0 and upper_wick > 2*body and lower_wick < body:
                pattern_desc.append("Shooting Star (bearish)")
                pattern_score -= 2
            # Engulfing
            if (prev["close"] < prev["open"] and last["close"] > last["open"] and
                last["open"] < prev["close"] and last["close"] > prev["open"]):
                pattern_desc.append("Bullish Engulfing")
                pattern_score += 3
            if (prev["close"] > prev["open"] and last["close"] < last["open"] and
                last["open"] > prev["close"] and last["close"] < prev["open"]):
                pattern_desc.append("Bearish Engulfing")
                pattern_score -= 3
            # Morning / Evening Star (3 candles)
            if len(candles) >= 3:
                c3, c2, c1 = candles[-3], candles[-2], candles[-1]
                # Morning Star
                if (c3["close"] < c3["open"] and
                    abs(c2["close"]-c2["open"]) < (c2["high"]-c2["low"])*0.3 and
                    c1["close"] > c1["open"] and
                    c1["close"] > (c3["open"] + c3["close"])/2):
                    pattern_desc.append("Morning Star (bullish reversal)")
                    pattern_score += 4
                # Evening Star
                if (c3["close"] > c3["open"] and
                    abs(c2["close"]-c2["open"]) < (c2["high"]-c2["low"])*0.3 and
                    c1["close"] < c1["open"] and
                    c1["close"] < (c3["open"] + c3["close"])/2):
                    pattern_desc.append("Evening Star (bearish reversal)")
                    pattern_score -= 4

        # Three White Soldiers / Black Crows
        if len(candles) >= 3:
            c3, c2, c1 = candles[-3], candles[-2], candles[-1]
            if all(c["close"] > c["open"] for c in [c3,c2,c1]) and c1["close"] > c2["close"] > c3["close"]:
                pattern_desc.append("Three White Soldiers (strong bullish)")
                pattern_score += 4
            if all(c["close"] < c["open"] for c in [c3,c2,c1]) and c1["close"] < c2["close"] < c3["close"]:
                pattern_desc.append("Three Black Crows (strong bearish)")
                pattern_score -= 4

        # ----- ICT / SMC concepts (simplified) -----
        # Fair Value Gap (FVG) detection on 3 candles
        if len(candles) >= 3:
            c1, c2, c3 = candles[-3], candles[-2], candles[-1]
            # Bullish FVG: c1 high < c3 low
            if c1["high"] < c3["low"]:
                pattern_desc.append("Bullish FVG (imbalance)")
                pattern_score += 2
            # Bearish FVG: c1 low > c3 high
            if c1["low"] > c3["high"]:
                pattern_desc.append("Bearish FVG (imbalance)")
                pattern_score -= 2

        # Liquidity sweep (stop hunt) – simple detection via wick beyond recent high/low
        if len(candles) >= 5:
            recent_high = max(c["high"] for c in candles[-5:-1])
            recent_low = min(c["low"] for c in candles[-5:-1])
            last_c = candles[-1]
            if last_c["high"] > recent_high and last_c["close"] < recent_high:
                pattern_desc.append("Liquidity sweep above (stop hunt)")
                pattern_score -= 2
            if last_c["low"] < recent_low and last_c["close"] > recent_low:
                pattern_desc.append("Liquidity sweep below (stop hunt)")
                pattern_score += 2

        # ----- Volume Profile / Order Flow insights -----
        vol_profile_note = ""
        poc = tech.get("poc")
        if poc:
            if price > poc:
                vol_profile_note = f"Price above POC {poc:.2f} (bullish context)"
            else:
                vol_profile_note = f"Price below POC {poc:.2f} (bearish context)"

        # Bid/Ask imbalance
        imbalance = order_book.get("bid_ask_imbalance", {})
        bias_note = imbalance.get("bias", "balanced")
        if bias_note == "buyers_dominant":
            pattern_score += 1
        elif bias_note == "sellers_dominant":
            pattern_score -= 1

        # ----- News sentiment -----
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

        # ================= SCORING ENGINE =================
        reasons = []
        score = 0

        # Primary trend
        if trend == "bullish":
            score += 2; reasons.append("Primary trend bullish")
        elif trend == "bearish":
            score -= 2; reasons.append("Primary trend bearish")

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
            score += 1.5; reasons.append("Price below lower BB")
        elif price > bb_upper:
            score -= 1.5; reasons.append("Price above upper BB")

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

        # ================= DECISION =================
        if score >= 4:
            direction, conf = "LONG", min(90, 50 + int(score * 4))
        elif score <= -4:
            direction, conf = "SHORT", min(90, 50 + int(abs(score) * 4))
        else:
            direction, conf = "NO TRADE", 30

        # Extreme Fear/Greed override
        if direction == "NO TRADE":
            if fg_val <= 15 and trend != "bearish":
                direction, conf = "LONG", 45
                reasons.append("Extreme Fear override – small long")
            elif fg_val >= 85 and trend != "bullish":
                direction, conf = "SHORT", 45
                reasons.append("Extreme Greed override – small short")

        # ================= TRADE PARAMETERS =================
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

        # ================= DAILY OUTLOOK =================
        daily_high = round(price + atr, 2)
        daily_low = round(price - atr, 2)
        daily_range = round(2*atr, 2)
        if trend == "bullish":
            bias = "Bullish"
        elif trend == "bearish":
            bias = "Bearish"
        else:
            bias = "Neutral"

        # ================= SETUP QUALITY SCORE =================
        # Count of active bullish/bearish signals
        bullish_signals = sum(1 for r in reasons if any(w in r.lower() for w in ["bullish","oversold","rising","contrarian buy","positive","scarce"]))
        bearish_signals = sum(1 for r in reasons if any(w in r.lower() for w in ["bearish","overbought","falling","contrarian sell","negative","abundant"]))
        total_signals = bullish_signals + bearish_signals
        if total_signals > 0:
            quality = min(100, int((bullish_signals if direction=="LONG" else bearish_signals if direction=="SHORT" else 0) / total_signals * 100))
        else:
            quality = 50

        # ================= OUTPUT =================
        return f"""ASSET: {symbol}
GENERATED: {timestamp}
STATUS: ACTIVE
VALID UNTIL: Next 6 hours or until SL/TP hit

FINAL DECISION: {direction}
CONFIDENCE: {conf}/100
SETUP QUALITY SCORE: {quality}/100

CURRENT PRICE: ${price:.2f}
SUPPORT: ${support:.2f} ({round((price-support)/price*100,1)}% below)
RESISTANCE: ${resistance:.2f} ({round((resistance-price)/price*100,1)}% above)
VWAP: {vwap:.2f}
ATR: {atr:.2f}

--- DAILY OUTLOOK ---
Predicted High: ${daily_high:.2f}
Predicted Low: ${daily_low:.2f}
Expected Range: ${daily_range:.2f}
Bias: {bias}

--- KEY LEVELS ---
Support: ${support:.2f}
Resistance: ${resistance:.2f}
Stop Loss: ${stop:.2f}
Take Profit 1: ${tp1:.2f}
Take Profit 2: ${tp2:.2f}
Take Profit 3: ${tp3:.2f}
Risk/Reward: {rr}

--- REASONING ---
{' | '.join(reasons[:8])}

--- CANDLESTICK / ORDER FLOW ---
{', '.join(pattern_desc) if pattern_desc else 'No strong patterns'}
{vol_profile_note}
Order Book Bias: {bias_note}

--- TRADE MANAGEMENT ---
Entry Trigger: {f'Wait for price in ${entry} zone with bullish confirmation' if direction == 'LONG' else f'Wait for price in ${entry} zone with bearish confirmation' if direction == 'SHORT' else 'No action until clearer signals'}
Invalidation: If closes beyond ${stop:.2f}
Best Session: London + New York overlap (13:00-17:00 UTC)

--- RISK NOTE ---
Risk 1-{pos_size} of capital. Always use a stop loss. Past performance does not guarantee future results.
"""
    except:
        return "Analysis failed. Please refresh."

# =====================================================================
#  MAIN TRADE PLAN GENERATOR (tries AI first, falls back to rule engine)
# =====================================================================
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

    # 3) Fallback to self-contained engine
    return _rule_based(data)