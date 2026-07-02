import json, os, asyncio
from datetime import datetime, timezone
import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from core.data_engine import (
    classify_asset_type, normalize_symbol,
    fetch_binance_ticker, fetch_binance_orderbook,
    fetch_coingecko_data, fetch_fear_greed, fetch_coins_list,
    fetch_news, fetch_stock_data, fetch_binance_klines,
)
from core.technicals import compute_multi_timeframe_technicals
from core.spoof_detector import SpoofDetector
from core.sentiment import analyze_sentiment
from core.agent import generate_trade_plan
from services.streams import BinanceStream, FinnhubStream

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
finnhub_stream = FinnhubStream()

def _summarize_timeframe(df) -> dict:
    if df is None or df.empty: return {"error":"No timeframe data"}
    closes = [float(v) for v in df["C"]]
    if not closes: return {"error":"No timeframe data"}
    first, last = closes[0], closes[-1]
    change_pct = round(((last-first)/first)*100,2) if first else None
    recent = df.tail(5)
    return {
        "current_price":round(last,2), "change_pct":change_pct,
        "trend":"bullish" if last>first else "bearish" if last<first else "neutral",
        "recent_candles":[{"open":float(r["O"]),"high":float(r["H"]),"low":float(r["L"]),"close":float(r["C"]),"volume":float(r["V"])} for _,r in recent.iterrows()]
    }

async def _fetch_news_headlines(symbol: str) -> list:
    key = os.getenv("NEWS_DATA_KEY")
    if key:
        try:
            async with httpx.AsyncClient(timeout=12) as c:
                r = await c.get("https://newsdata.io/api/1/news", params={"apikey":key,"q":symbol,"language":"en","size":5})
                if r.status_code == 200:
                    results = r.json().get("results",[])
                    if results: return [{"headline":i.get("title") or i.get("description") or "","summary":(i.get("description") or "")[:200]} for i in results[:5]]
        except: pass
    return await fetch_news(symbol)

def _enrich_coingecko(cg: dict, price: float|None=None) -> dict:
    if not cg: return cg
    if price and cg.get("ath"):
        cg["ath_distance_pct"] = round(((price-cg["ath"])/cg["ath"])*100,2)
    circ, mx = cg.get("circ_supply"), cg.get("max_supply")
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
    return HTMLResponse("""<html><head><title>Hawk Eye - Exchanges</title><link rel="stylesheet" href="/static/css/style.css"></head><body><header class="header"><div class="header-inner"><a href="/" class="logo">HAWK EYE</a><nav class="nav"><a href="/" class="nav-link">Coins</a><a href="/exchanges" class="nav-link active">Exchanges</a><a href="/learn" class="nav-link">Learn</a></nav></div></header><main style="max-width:1400px;margin:40px auto;padding:20px;"><h2 style="color:#f0b90b;">Top Exchanges</h2><table class="coin-table"><thead><tr><th>#</th><th>Exchange</th><th>Trust Score</th><th>24h Volume (BTC)</th><th>Country</th><th>Year</th></tr></thead><tbody id="exBody"><tr><td colspan="6">Loading...</td></tr></tbody></table></main><script>fetch('https://api.coingecko.com/api/v3/exchanges?per_page=20').then(r=>r.json()).then(d=>{document.getElementById('exBody').innerHTML=d.map((e,i)=>`<tr><td>${i+1}</td><td><a href="${e.url}" target="_blank" style="color:#3da5d9;">${e.name}</a></td><td>${e.trust_score}</td><td>${e.trade_volume_24h_btc.toFixed(2)}</td><td>${e.country||'N/A'}</td><td>${e.year_established||'N/A'}</td></tr>`).join('')}).catch(()=>document.getElementById('exBody').innerHTML='<tr><td colspan=6>Failed to load.</td></tr>')</script></body></html>""")

@app.get("/learn", response_class=HTMLResponse)
async def learn_page():
    return HTMLResponse("""<html><head><title>Hawk Eye - Learn Trading</title><link rel="stylesheet" href="/static/css/style.css"></head><body><header class="header"><div class="header-inner"><a href="/" class="logo">HAWK EYE</a><nav class="nav"><a href="/" class="nav-link">Coins</a><a href="/exchanges" class="nav-link">Exchanges</a><a href="/learn" class="nav-link active">Learn</a></nav></div></header><main style="max-width:900px;margin:40px auto;padding:20px;"><h1 style="color:#f0b90b;">Trading Education Center</h1><div class="panel" style="margin-top:20px;"><h3 style="color:#3da5d9;">1. What is Trading?</h3><p>Buying and selling assets to profit from price movements. Buy low, sell high. Or short sell high, buy back low.</p></div><div class="panel" style="margin-top:16px;"><h3 style="color:#3da5d9;">2. Support & Resistance</h3><p><b>Support:</b> Price floor where buying pressure stops declines.<br><b>Resistance:</b> Price ceiling where selling pressure stops advances.<br>These levels come from previous highs/lows and volume clusters.</p></div><div class="panel" style="margin-top:16px;"><h3 style="color:#3da5d9;">3. RSI (Relative Strength Index)</h3><p>Measures momentum on a 0-100 scale.<br><b>Above 70:</b> Overbought - potential reversal down.<br><b>Below 30:</b> Oversold - potential reversal up.<br><b>50:</b> Neutral zone.</p></div><div class="panel" style="margin-top:16px;"><h3 style="color:#3da5d9;">4. MACD</h3><p>Trend-following momentum indicator.<br><b>MACD above Signal:</b> Bullish momentum.<br><b>MACD below Signal:</b> Bearish momentum.<br><b>Histogram:</b> Shows momentum strength.</p></div><div class="panel" style="margin-top:16px;"><h3 style="color:#3da5d9;">5. Risk Management</h3><p><b>1-2% Rule:</b> Never risk more than 1-2% per trade.<br><b>Stop Loss:</b> Always set before entering.<br><b>Risk/Reward:</b> Minimum 1:2. Risk $1 to make $2.<br><b>Position Size:</b> (Account x Risk%) / (Entry - Stop Loss) = Units.</p></div><div class="panel" style="margin-top:16px;"><h3 style="color:#3da5d9;">6. Fear & Greed Index</h3><p><b>Extreme Fear (0-25):</b> Often best time to buy.<br><b>Extreme Greed (75-100):</b> Often time to sell.<br>Contrarian investing: Buy when blood is in the streets.</p></div><div class="panel" style="margin-top:16px;"><h3 style="color:#3da5d9;">7. Candlestick Patterns</h3><p><b>Doji:</b> Open=Close. Indecision.<br><b>Hammer:</b> Long lower wick. Bullish reversal.<br><b>Shooting Star:</b> Long upper wick. Bearish reversal.<br><b>Engulfing:</b> Big candle swallows previous. Strong reversal signal.</p></div><p style="margin-top:30px;color:#848e9c;text-align:center;">Trade smart. Manage risk. Let data guide you.</p></main></body></html>""")

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
async def coins_list():
    data = await fetch_coins_list(50)
    return JSONResponse(data)

@app.post("/analyze")
async def analyze(request: Request):
    try:
        body = await request.json()
        symbol = body.get("symbol","").strip().upper()
        if not symbol: raise ValueError("Symbol required")
        asset_type = body.get("type","auto")
        if asset_type not in ("stock","crypto","commodity","auto"): asset_type="auto"
        if asset_type=="auto": asset_type=classify_asset_type(symbol)
        symbol = normalize_symbol(symbol, asset_type)

        price_data = {}
        depth = {"bids":[],"asks":[]}
        coingecko_data = {}
        technicals = {}
        df = None

        if asset_type in ("crypto","commodity"):
            price_data = await fetch_binance_ticker(symbol)
            if not price_data: return JSONResponse({"error":f"Invalid {asset_type} symbol"}, status_code=400)
            depth = await fetch_binance_orderbook(symbol)
            coin_id = symbol.lower().replace("usdt","")
            coingecko_data = await fetch_coingecko_data(coin_id)
            df = fetch_binance_klines(symbol)
            technicals = compute_multi_timeframe_technicals(symbol, asset_type) if not df.empty else {}
        else:
            price_data = fetch_stock_data(symbol)
            if not price_data: return JSONResponse({"error":"Invalid stock symbol"}, status_code=400)
            technicals = compute_multi_timeframe_technicals(symbol, "stock")

        if isinstance(technicals, dict) and not technicals.get("error") and df is not None and not df.empty:
            technicals["recent_candles"] = [{"open":float(r["O"]),"high":float(r["H"]),"low":float(r["L"]),"close":float(r["C"]),"volume":float(r["V"])} for _,r in df.tail(5).iterrows()]

        coingecko_data = _enrich_coingecko(coingecko_data, price_data.get("price"))
        fear_greed = await fetch_fear_greed()
        news = await _fetch_news_headlines(symbol)
        sentiment = analyze_sentiment(news)

        sd = SpoofDetector()
        sd.update(symbol, depth.get("bids",[]), depth.get("asks",[]))
        spoof_info = sd.get_spoof_alert(symbol)
        bids, asks = depth.get("bids",[]), depth.get("asks",[])
        bid_v = sum(q for _,q in bids[:5])
        ask_v = sum(q for _,q in asks[:5])
        bias = "buyers_dominant" if bid_v>ask_v else "sellers_dominant" if ask_v>bid_v else "balanced"

        multi_tf = {"1D": technicals}
        if asset_type in ("crypto","commodity") and df is not None and not df.empty:
            for label, interval in (("4H","4h"),("1H","1h"),("15m","15m")):
                tf_df = fetch_binance_klines(symbol, interval=interval, limit=100)
                multi_tf[label] = _summarize_timeframe(tf_df)

        full_data = {
            "symbol":symbol, "asset_type":asset_type,
            "timestamp_utc":datetime.now(timezone.utc).isoformat(),
            "price_data":price_data, "technicals_1d":technicals,
            "technicals":technicals, "multi_timeframe":multi_tf,
            "fear_greed":fear_greed, "coingecko":coingecko_data,
            "order_book":{"bids_top5":bids[:5],"asks_top5":asks[:5],
            "bid_ask_imbalance":{"bid_volume":round(bid_v,2),"ask_volume":round(ask_v,2),"bias":bias},
            "spoof_alert":spoof_info}, "news":news, "sentiment":sentiment,
            "news_sentiment_score":sentiment.get("score") if isinstance(sentiment,dict) else None
        }

        trade_plan = generate_trade_plan(full_data)
        return JSONResponse({"trade_plan":trade_plan, "data_snapshot":full_data})
    except Exception as e:
        return JSONResponse({"error":str(e)}, status_code=500)

@app.on_event("shutdown")
async def shutdown():
    await binance_stream.close(); await finnhub_stream.close()