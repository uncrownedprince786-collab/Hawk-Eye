import asyncio, json, os
from datetime import datetime, timezone
import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from core.crypto_engine import fetch_crypto_price, fetch_crypto_ohlc, fetch_crypto_market, fetch_orderbook
from core.data_engine import fetch_fear_greed, fetch_coins_list, fetch_news
from core.spoof_detector import SpoofDetector
from core.sentiment import analyze_sentiment
from core.agent import generate_trade_plan
from services.streams import BinanceStream
from core.config import NEWS_DATA_KEY

import math

def _safe_float(obj):
    if isinstance(obj, dict):
        return {k: _safe_float(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_safe_float(v) for v in obj]
    elif isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
    return obj


load_dotenv()
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

def classify_asset_type(symbol: str) -> str:
    sym = symbol.upper()
    if sym.endswith(("USDT", "USD", "BTC", "ETH")):
        return "crypto"
    return "crypto"

def normalize_symbol(symbol: str, asset_type: str) -> str:
    sym = symbol.upper()
    if not sym.endswith("USDT"):
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

@app.get("/", response_class=HTMLResponse)
async def root():
    with open("static/index.html","r",encoding="utf-8") as f: return HTMLResponse(content=f.read())

@app.get("/coin", response_class=HTMLResponse)
async def coin_page():
    with open("static/coin.html","r",encoding="utf-8") as f: return HTMLResponse(content=f.read())

@app.get("/exchanges", response_class=HTMLResponse)
async def exchanges_page():
    return HTMLResponse("""<html><head><title>Hawk Eye - Exchanges</title><link rel="stylesheet" href="/static/css/style.css"></head><body class="bg-[#0b0e11] text-white"><header class="bg-[#1e2329] border-b border-[#2b3139] p-4"><a href="/" class="text-[#f0b90b] font-bold text-xl">HAWK EYE</a></header><main class="max-w-4xl mx-auto p-4"><h2 class="text-[#f0b90b] text-xl mb-4">Top Exchanges</h2><div id="exchanges"></div></main><script>fetch('https://api.coingecko.com/api/v3/exchanges?per_page=20').then(r=>r.json()).then(d=>{document.getElementById('exchanges').innerHTML=d.map(e=>'<div class="bg-[#1e2329] p-3 rounded mb-2 flex justify-between"><span>'+e.name+'</span><span class="text-[#848e9c]">Trust: '+e.trust_score+'</span></div>').join('')})</script></body></html>""")

@app.get("/learn", response_class=HTMLResponse)
async def learn_page():
    return HTMLResponse("""<html><head><title>Learn Trading</title><link rel="stylesheet" href="/static/css/style.css"></head><body class="bg-[#0b0e11] text-white"><header class="bg-[#1e2329] border-b border-[#2b3139] p-4"><a href="/" class="text-[#f0b90b] font-bold text-xl">HAWK EYE</a></header><main class="max-w-4xl mx-auto p-4 space-y-4"><h1 class="text-[#f0b90b] text-2xl font-bold">Trading Education</h1><p>Learn about support/resistance, RSI, MACD, candlestick patterns, and risk management.</p></main></body></html>""")

@app.get("/api/news")
async def news_proxy(symbol: str = ""):
    if symbol:
        news = await _fetch_coin_news(symbol)
        return JSONResponse(news)
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"https://finnhub.io/api/v1/news?category=general&token={os.getenv('FINNHUB_API_KEY','')}")
            if resp.status_code == 200:
                return JSONResponse(resp.json())
    except: pass
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"https://newsdata.io/api/1/news?apikey={NEWS_DATA_KEY}&q=crypto&category=business,finance&language=en&size=12")
            if resp.status_code == 200:
                return JSONResponse(resp.json())
    except: pass
    return JSONResponse([], status_code=500)

@app.websocket("/ws/{symbol}")
async def ws_endpoint(ws: WebSocket, symbol: str):
    await manager.connect(ws)
    sym = normalize_symbol(symbol, "crypto")
    try:
        await binance_stream.subscribe(sym, ws)
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

@app.post("/analyze")
async def analyze(request: Request):
    try:
        body = await request.json()
        symbol = body.get("symbol","").strip().upper()
        if not symbol: raise ValueError("Symbol required")
        symbol = normalize_symbol(symbol, "crypto")

        price_data = await fetch_crypto_price(symbol) or {}
        ohlc = await fetch_crypto_ohlc(symbol, 30)
        technicals = compute_multi_timeframe_technicals_from_ohlc(ohlc) if ohlc else {}
        coingecko_data = await fetch_crypto_market(symbol) or {}
        orderbook = await fetch_orderbook(symbol) or {"bids":[],"asks":[]}
        news = await _fetch_coin_news(symbol)
        fear_greed = await fetch_fear_greed()
        sentiment = analyze_sentiment(news)

        if coingecko_data:
            coingecko_data = _enrich_coingecko(coingecko_data, price_data.get("price"))

        sd = SpoofDetector()
        sd.update(symbol, orderbook.get("bids",[]), orderbook.get("asks",[]))
        spoof_info = sd.get_spoof_alert(symbol)
        bids, asks = orderbook.get("bids",[]), orderbook.get("asks",[])
        bid_v = sum(q for _,q in bids[:5])
        ask_v = sum(q for _,q in asks[:5])
        bias = "buyers_dominant" if bid_v>ask_v else "sellers_dominant" if ask_v>bid_v else "balanced"

        full_data = {
            "symbol":symbol, "asset_type":"crypto",
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
        return JSONResponse({"trade_plan":trade_plan, "data_snapshot":_safe_float(full_data)})
    except Exception as e:
        return JSONResponse({"error":str(e)}, status_code=500)

@app.on_event("shutdown")
async def shutdown():
    await binance_stream.close()
