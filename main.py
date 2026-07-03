import asyncio, json, os
from datetime import datetime, timezone
import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from core.crypto_engine import fetch_crypto_price, fetch_crypto_ohlc, fetch_crypto_market, fetch_orderbook
from core.stock_engine import fetch_stock_quote, fetch_stock_fundamentals, fetch_stock_ohlc
from core.data_engine import fetch_coingecko_data, fetch_fear_greed, fetch_coins_list, fetch_news
from core.technicals import compute_multi_timeframe_technicals
from core.spoof_detector import SpoofDetector
from core.sentiment import analyze_sentiment
from core.agent import generate_trade_plan
from services.streams import BinanceStream, FinnhubStream
from core.config import FINNHUB_API_KEY, NEWS_DATA_KEY

load_dotenv()

def classify_asset_type(symbol: str) -> str:
    sym = symbol.upper()
    if sym in ("XAUUSDT","XAGUSDT","PAXGUSDT","XAUTUSDT","GOLD","SILVER"):
        return "commodity"
    if sym.endswith(("USDT","USD","BTC","ETH")):
        return "crypto"
    return "stock"

def normalize_symbol(symbol: str, asset_type: str) -> str:
    sym = symbol.upper()
    if asset_type == "commodity":
        m = {"GOLD":"PAXGUSDT","SILVER":"XAGUSDT","XAU":"PAXGUSDT","XAG":"XAGUSDT"}
        return m.get(sym, sym if sym.endswith("USDT") else sym+"USDT")
    if asset_type == "crypto" and not sym.endswith("USDT"):
        return sym + "USDT"
    return sym

def compute_multi_timeframe_technicals_from_ohlc(ohlc: list) -> dict:
    import pandas as pd, numpy as np
    df = pd.DataFrame(ohlc)
    df.columns = ["Open","High","Low","Close","Volume"]
    closes = df["Close"]
    result = {}
    result["current_price"] = closes.iloc[-1]
    for p in [9,21,50,200]:
        e = closes.ewm(span=p, adjust=False).mean().iloc[-1]
        result[f"ema_{p}"] = round(e,2) if not pd.isna(e) else None
    for p in [20,50,200]:
        s = closes.rolling(p).mean().iloc[-1] if len(closes)>=p else None
        result[f"sma_{p}"] = round(s,2) if s is not None and not pd.isna(s) else None
    d = closes.diff()
    gain = d.clip(lower=0).rolling(14).mean().iloc[-1]
    loss = -d.clip(upper=0).rolling(14).mean().iloc[-1]
    rs = gain/loss if loss!=0 else float('inf')
    result["rsi_14"] = round(100-(100/(1+rs)),2) if rs!=float('inf') else 100.0
    ema12 = closes.ewm(span=12,adjust=False).mean()
    ema26 = closes.ewm(span=26,adjust=False).mean()
    macd = ema12 - ema26
    sig = macd.ewm(span=9,adjust=False).mean()
    result["macd"] = round(macd.iloc[-1],4)
    result["macd_signal"] = round(sig.iloc[-1],4)
    result["macd_direction"] = "bullish" if macd.iloc[-1]>sig.iloc[-1] else "bearish"
    low14 = df["Low"].rolling(14).min()
    high14 = df["High"].rolling(14).max()
    stoch_k = ((closes - low14)/(high14 - low14))*100
    result["stoch_k"] = round(stoch_k.iloc[-1],2)
    result["stoch_d"] = round(stoch_k.rolling(3).mean().iloc[-1],2)
    sma20 = closes.rolling(20).mean()
    std20 = closes.rolling(20).std()
    result["bb_upper"] = round((sma20+2*std20).iloc[-1],2)
    result["bb_lower"] = round((sma20-2*std20).iloc[-1],2)
    tr = pd.concat([df["High"]-df["Low"], (df["High"]-closes.shift()).abs(), (df["Low"]-closes.shift()).abs()], axis=1).max(axis=1)
    result["atr_14"] = round(tr.rolling(14).mean().iloc[-1],2)
    recent = df.tail(20)
    result["support_20"] = round(recent["Low"].min(),2)
    result["resistance_20"] = round(recent["High"].max(),2)
    tp = (df["High"]+df["Low"]+closes)/3
    vwap = (tp*df["Volume"]).rolling(20).sum()/df["Volume"].rolling(20).sum()
    result["vwap"] = round(vwap.iloc[-1],2)
    obv = (np.sign(closes.diff())*df["Volume"]).fillna(0).cumsum()
    result["obv_trend"] = "rising" if obv.iloc[-1]>obv.iloc[-20] else "falling"
    if result.get("sma_50") and result.get("sma_200"):
        if result["current_price"]>result["sma_50"] and result["sma_50"]>result["sma_200"]:
            result["trend"] = "bullish"
        elif result["current_price"]<result["sma_50"] and result["sma_50"]<result["sma_200"]:
            result["trend"] = "bearish"
        else:
            result["trend"] = "neutral"
    else:
        result["trend"] = "neutral"
    result["recent_candles"] = ohlc[-30:]
    return result

async def _fetch_coin_news(symbol: str) -> list:
    query = symbol.replace("USDT","").replace("USD","")
    if NEWS_DATA_KEY:
        try:
            async with httpx.AsyncClient(timeout=12) as c:
                r = await c.get("https://newsdata.io/api/1/news",
                    params={"apikey":NEWS_DATA_KEY,"q":f"{query} crypto","category":"business,finance","language":"en","size":5})
                if r.status_code == 200 and r.json().get("results"):
                    return [{"headline":i.get("title",""),"summary":(i.get("description") or "")[:200]} for i in r.json()["results"][:5]]
        except: pass
    return await fetch_news(symbol)

def _enrich_coingecko(cg: dict, price: float|None=None) -> dict:
    if not cg: return cg
    if price and cg.get("ath"):
        cg["ath_distance_pct"] = round(((price-cg["ath"])/cg["ath"])*100,2)
    circ, mx = cg.get("circulating_supply"), cg.get("max_supply")
    if circ and mx:
        ratio = round(circ/mx,4) if mx else None
        cg["supply_ratio"] = ratio
        cg["supply_scarcity"] = "scarce" if ratio<0.8 else "abundant" if ratio>0.95 else "moderate"
    return cg

app = FastAPI(title="Hawk Eye Terminal")
app.mount("/static", StaticFiles(directory="static"), name="static")

class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []
    async def connect(self, ws: WebSocket):
        await ws.accept(); self.active_connections.append(ws)
    def disconnect(self, ws: WebSocket):
        if ws in self.active_connections: self.active_connections.remove(ws)

manager = ConnectionManager()
binance_stream = BinanceStream()
finnhub_stream = FinnhubStream()

@app.get("/", response_class=HTMLResponse)
async def root():
    with open("static/index.html","r",encoding="utf-8") as f: return HTMLResponse(content=f.read())

@app.get("/coin", response_class=HTMLResponse)
async def coin_page():
    with open("static/coin.html","r",encoding="utf-8") as f: return HTMLResponse(content=f.read())

@app.get("/exchanges", response_class=HTMLResponse)
async def exchanges_page():
    return HTMLResponse("""<html><head><title>Hawk Eye - Exchanges</title><link rel="stylesheet" href="/static/css/style.css"></head><body><header class="header"><div class="container header-inner"><a href="/" class="logo">HAWK EYE</a><nav class="nav"><a href="/" class="nav-link">Coins</a><a href="/exchanges" class="nav-link active">Exchanges</a><a href="/learn" class="nav-link">Learn</a></nav></div></header><main style="max-width:1400px;margin:40px auto;padding:20px;"><h2 style="color:#f0b90b;">Top Exchanges</h2><table class="coin-table"><thead><tr><th>#</th><th>Exchange</th><th>Trust Score</th><th>24h Volume (BTC)</th><th>Country</th><th>Year</th></tr></thead><tbody id="exBody"><tr><td colspan="6">Loading...</td></tr></tbody></table></main><script>fetch('https://api.coingecko.com/api/v3/exchanges?per_page=20').then(r=>r.json()).then(d=>{document.getElementById('exBody').innerHTML=d.map((e,i)=>`<tr><td>${i+1}</td><td><a href="${e.url}" target="_blank" style="color:#3da5d9;">${e.name}</a></td><td>${e.trust_score}</td><td>${e.trade_volume_24h_btc.toFixed(2)}</td><td>${e.country||'N/A'}</td><td>${e.year_established||'N/A'}</td></tr>`).join('')}).catch(()=>document.getElementById('exBody').innerHTML='<tr><td colspan=6>Failed to load.</td></tr>')</script></body></html>""")

@app.get("/learn", response_class=HTMLResponse)
async def learn_page():
    return HTMLResponse("""<html><head><title>Hawk Eye - Learn Trading</title><link rel="stylesheet" href="/static/css/style.css"></head><body><header class="header"><div class="container header-inner"><a href="/" class="logo">HAWK EYE</a><nav class="nav"><a href="/" class="nav-link">Coins</a><a href="/exchanges" class="nav-link">Exchanges</a><a href="/learn" class="nav-link active">Learn</a></nav></div></header><main style="max-width:900px;margin:40px auto;padding:20px;"><h1 style="color:#f0b90b;">Trading Education Center</h1><div class="panel" style="margin-top:20px;"><h3 style="color:#3da5d9;">1. What is Trading?</h3><p>Buying and selling assets to profit from price movements. Buy low, sell high. Or short sell high, buy back low.</p></div><div class="panel" style="margin-top:16px;"><h3 style="color:#3da5d9;">2. Support & Resistance</h3><p><b>Support:</b> Price floor where buying pressure stops declines.<br><b>Resistance:</b> Price ceiling where selling pressure stops advances.</p></div><div class="panel" style="margin-top:16px;"><h3 style="color:#3da5d9;">3. RSI (Relative Strength Index)</h3><p>Measures momentum on a 0-100 scale.<br><b>Above 70:</b> Overbought - potential reversal down.<br><b>Below 30:</b> Oversold - potential reversal up.</p></div><div class="panel" style="margin-top:16px;"><h3 style="color:#3da5d9;">4. MACD</h3><p>Trend-following momentum indicator.<br><b>MACD above Signal:</b> Bullish momentum.<br><b>MACD below Signal:</b> Bearish momentum.</p></div><div class="panel" style="margin-top:16px;"><h3 style="color:#3da5d9;">5. Risk Management</h3><p><b>1-2% Rule:</b> Never risk more than 1-2% per trade.<br><b>Stop Loss:</b> Always set before entering.<br><b>Risk/Reward:</b> Minimum 1:2. Risk $1 to make $2.</p></div><div class="panel" style="margin-top:16px;"><h3 style="color:#3da5d9;">6. Fear & Greed Index</h3><p><b>Extreme Fear (0-25):</b> Often best time to buy.<br><b>Extreme Greed (75-100):</b> Often time to sell.</p></div><div class="panel" style="margin-top:16px;"><h3 style="color:#3da5d9;">7. Candlestick Patterns</h3><p><b>Doji:</b> Open=Close. Indecision.<br><b>Hammer:</b> Long lower wick. Bullish reversal.<br><b>Shooting Star:</b> Long upper wick. Bearish reversal.</p></div><p style="margin-top:30px;color:#848e9c;text-align:center;">Trade smart. Manage risk. Let data guide you.</p></main></body></html>""")

@app.get("/api/stock/{symbol}")
async def stock_quote(symbol: str):
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"https://finnhub.io/api/v1/quote?symbol={symbol}&token={FINNHUB_API_KEY}")
            if resp.status_code == 200:
                return JSONResponse(resp.json())
    except: pass
    return JSONResponse({"error": "Stock data unavailable"}, status_code=500)

@app.get("/api/news")
async def news_proxy(symbol: str = ""):
    if symbol:
        news = await _fetch_coin_news(symbol)
        return JSONResponse(news)
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"https://finnhub.io/api/v1/news?category=general&token={FINNHUB_API_KEY}")
            if resp.status_code == 200:
                return JSONResponse(resp.json())
    except: pass
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"https://newsdata.io/api/1/news?apikey={NEWS_DATA_KEY}&q=forex crypto stocks&category=business,finance&language=en&size=12")
            if resp.status_code == 200:
                return JSONResponse(resp.json())
    except: pass
    return JSONResponse([], status_code=500)

@app.websocket("/ws/{symbol}")
async def ws_endpoint(ws: WebSocket, symbol: str):
    await manager.connect(ws)
    at = classify_asset_type(symbol)
    sym = normalize_symbol(symbol, at)
    try:
        if at == "stock": await finnhub_stream.subscribe(symbol, ws)
        else: await binance_stream.subscribe(sym, ws)
    except WebSocketDisconnect: manager.disconnect(ws)
    except Exception: manager.disconnect(ws)

@app.get("/api/coins")
async def coins_list(page: int = 1, per_page: int = 50):
    data = await fetch_coins_list(per_page, page)
    return JSONResponse(data)

@app.get("/api/price/{symbol}")
async def price_ticker(symbol: str):
    price_data = await fetch_crypto_price(symbol.upper())
    if price_data:
        return JSONResponse(price_data)
    return JSONResponse({"price": 0}, status_code=500)


def _sanitize_for_json(obj):
    """Replace NaN/Infinity with None for JSON compliance."""
    import math
    if isinstance(obj, dict):
        return {k: _sanitize_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_sanitize_for_json(v) for v in obj]
    elif isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
    return obj

@app.post("/analyze")
async def analyze(request: Request):
    try:
        body = await request.json()
        symbol = body.get("symbol","").strip().upper()
        if not symbol: raise ValueError("Symbol required")
        asset_type = classify_asset_type(symbol)
        symbol = normalize_symbol(symbol, asset_type)

        price_data = {}
        technicals = {}
        coingecko_data = {}
        orderbook = {"bids":[],"asks":[]}
        news = []
        fear_greed = await fetch_fear_greed()

        if asset_type in ("crypto","commodity"):
            price_data = await fetch_crypto_price(symbol) or {}
            ohlc = await fetch_crypto_ohlc(symbol, 30)
            if ohlc:
                technicals = compute_multi_timeframe_technicals_from_ohlc(ohlc)
            else:
                technicals = {}
            coingecko_data = await fetch_crypto_market(symbol) or {}
            orderbook = await fetch_orderbook(symbol) or {"bids":[],"asks":[]}
            news = await _fetch_coin_news(symbol)
        else:
            price_data = await fetch_stock_quote(symbol) or {}
            ohlc = await fetch_stock_ohlc(symbol)
            if ohlc:
                technicals = compute_multi_timeframe_technicals_from_ohlc(ohlc)
            else:
                technicals = {}
            coingecko_data = {}
            news = await _fetch_coin_news(symbol)

        if coingecko_data:
            coingecko_data = _enrich_coingecko(coingecko_data, price_data.get("price"))

        sentiment = analyze_sentiment(news)

        sd = SpoofDetector()
        sd.update(symbol, orderbook.get("bids",[]), orderbook.get("asks",[]))
        spoof_info = sd.get_spoof_alert(symbol)
        bids, asks = orderbook.get("bids",[]), orderbook.get("asks",[])
        bid_v = sum(q for _,q in bids[:5])
        ask_v = sum(q for _,q in asks[:5])
        bias = "buyers_dominant" if bid_v>ask_v else "sellers_dominant" if ask_v>bid_v else "balanced"

        full_data = {
            "symbol":symbol, "asset_type":asset_type,
            "timestamp_utc":datetime.now(timezone.utc).isoformat(),
            "price_data":price_data, "technicals_1d":technicals,
            "technicals":technicals, "multi_timeframe":{},
            "fear_greed":fear_greed, "coingecko":coingecko_data,
            "order_book":{"bids_top5":bids[:5],"asks_top5":asks[:5],
            "bid_ask_imbalance":{"bid_volume":round(bid_v,2),"ask_volume":round(ask_v,2),"bias":bias},
            "spoof_alert":spoof_info}, "news":news, "sentiment":sentiment,
            "news_sentiment_score":sentiment.get("score") if isinstance(sentiment,dict) else None
        }

        trade_plan = generate_trade_plan(full_data)
        return JSONResponse({"trade_plan":trade_plan, "data_snapshot":_sanitize_for_json(full_data)})
    except Exception as e:
        return JSONResponse({"error":str(e)}, status_code=500)

@app.on_event("shutdown")
async def shutdown():
    await binance_stream.close(); await finnhub_stream.close()

