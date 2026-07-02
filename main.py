import json
import os
from datetime import datetime, timezone
import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from core.data_engine import (
    classify_asset_type,
    normalize_symbol,
    fetch_binance_ticker,
    fetch_binance_orderbook,
    fetch_coingecko_data,
    fetch_fear_greed,
    fetch_coins_list,
    fetch_news,
    fetch_stock_data,
    fetch_binance_klines,
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

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)


manager = ConnectionManager()
binance = BinanceStream()
finnhub = FinnhubStream()


def _summarize_timeframe(df) -> dict:
    if df is None or df.empty:
        return {"error": "No timeframe data"}
    closes = [float(v) for v in df["C"]]
    if not closes:
        return {"error": "No timeframe data"}
    first = closes[0]
    last = closes[-1]
    change_pct = round(((last - first) / first) * 100, 2) if first else None
    recent = df.tail(5)
    return {
        "current_price": round(last, 2),
        "change_pct": change_pct,
        "trend": "bullish" if last > first else "bearish" if last < first else "neutral",
        "recent_candles": [
            {
                "open": float(row["O"]),
                "high": float(row["H"]),
                "low": float(row["L"]),
                "close": float(row["C"]),
                "volume": float(row["V"]),
            }
            for _, row in recent.iterrows()
        ],
    }


async def _fetch_news_headlines(symbol: str) -> list:
    news_key = os.getenv("NEWS_DATA_KEY")
    if news_key:
        try:
            async with httpx.AsyncClient(timeout=12) as client:
                r = await client.get(
                    "https://newsdata.io/api/1/news",
                    params={"apikey": news_key, "q": symbol, "language": "en", "size": 5},
                )
                if r.status_code == 200:
                    results = r.json().get("results", [])
                    if results:
                        return [
                            {
                                "headline": item.get("title") or item.get("description") or "",
                                "summary": (item.get("description") or "")[:200],
                            }
                            for item in results[:5]
                        ]
        except Exception:
            pass
    return await fetch_news(symbol)


def _enrich_coingecko_data(coingecko_data: dict, price: float | None = None) -> dict:
    if not coingecko_data:
        return coingecko_data
    if price is not None and coingecko_data.get("ath"):
        coingecko_data["ath_distance_pct"] = round(((price - coingecko_data["ath"]) / coingecko_data["ath"]) * 100, 2)
    circ = coingecko_data.get("circ_supply")
    max_supply = coingecko_data.get("max_supply")
    if circ and max_supply:
        ratio = round(circ / max_supply, 4) if max_supply else None
        coingecko_data["supply_ratio"] = ratio
        coingecko_data["supply_scarcity"] = "scarce" if ratio < 0.8 else "abundant" if ratio > 0.95 else "moderate"
    return coingecko_data


@app.get("/", response_class=HTMLResponse)
async def root():
    with open("static/index.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())


@app.get("/coin", response_class=HTMLResponse)
async def coin_page():
    with open("static/coin.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())


@app.websocket("/ws/{symbol}")
async def websocket_endpoint(websocket: WebSocket, symbol: str):
    await manager.connect(websocket)
    asset_type = classify_asset_type(symbol)
    resolved_symbol = normalize_symbol(symbol, asset_type)
    try:
        if asset_type == "stock":
            await finnhub.subscribe(symbol, websocket)
        else:
            await binance.subscribe(resolved_symbol, websocket)
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        if websocket.client_state.name != "CLOSED":
            try:
                await websocket.send_text(json.dumps({"error": str(e)}))
            except Exception:
                pass
        manager.disconnect(websocket)


@app.get("/api/coins")
async def coins_list():
    data = await fetch_coins_list(50)
    return JSONResponse(data)


@app.post("/analyze")
async def analyze(request: Request):
    try:
        body = await request.json()
        symbol = body.get("symbol", "").strip().upper()
        if not symbol:
            raise ValueError("Symbol required")

        asset_type = body.get("type", "auto")
        if asset_type not in ("stock", "crypto", "commodity", "auto"):
            asset_type = "auto"
        if asset_type == "auto":
            asset_type = classify_asset_type(symbol)

        symbol = normalize_symbol(symbol, asset_type)

        if asset_type == "crypto":
            price_data = await fetch_binance_ticker(symbol)
            if not price_data:
                return JSONResponse({"error": "Invalid crypto symbol"}, status_code=400)
            depth = await fetch_binance_orderbook(symbol)
            coin_id = symbol.lower().replace("usdt", "")
            coingecko_data = await fetch_coingecko_data(coin_id)
            df = fetch_binance_klines(symbol)
            technicals = compute_multi_timeframe_technicals(symbol, asset_type) if not df.empty else {}
        elif asset_type == "commodity":
            price_data = await fetch_binance_ticker(symbol)
            if not price_data:
                return JSONResponse({"error": "Invalid commodity symbol"}, status_code=400)
            depth = await fetch_binance_orderbook(symbol)
            coin_id = symbol.lower().replace("usdt", "")
            coingecko_data = await fetch_coingecko_data(coin_id)
            df = fetch_binance_klines(symbol)
            technicals = compute_multi_timeframe_technicals(symbol, "crypto") if not df.empty else {}
        else:
            price_data = fetch_stock_data(symbol)
            if not price_data:
                return JSONResponse({"error": "Invalid stock symbol"}, status_code=400)
            depth = {"bids": [], "asks": []}
            coingecko_data = {}
            technicals = compute_multi_timeframe_technicals(symbol, "stock")
            df = None

        if isinstance(technicals, dict) and not technicals.get("error") and df is not None and not df.empty:
            technicals["recent_candles"] = [
                {
                    "open": float(row["O"]),
                    "high": float(row["H"]),
                    "low": float(row["L"]),
                    "close": float(row["C"]),
                    "volume": float(row["V"]),
                }
                for _, row in df.tail(5).iterrows()
            ]

        coingecko_data = _enrich_coingecko_data(coingecko_data, price_data.get("price"))
        fear_greed = await fetch_fear_greed()
        news = await _fetch_news_headlines(symbol)
        sentiment = analyze_sentiment(news)

        spoof_detector = SpoofDetector()
        spoof_detector.update(symbol, depth.get("bids", []), depth.get("asks", []))
        spoof_info = spoof_detector.get_spoof_alert(symbol)
        bids = depth.get("bids", [])
        asks = depth.get("asks", [])
        bid_volume = sum(q for _, q in bids[:5])
        ask_volume = sum(q for _, q in asks[:5])
        imbalance_bias = "buyers_dominant" if bid_volume > ask_volume else "sellers_dominant" if ask_volume > bid_volume else "balanced"

        multi_timeframe = {"1D": technicals}
        if asset_type in ("crypto", "commodity") and df is not None and not df.empty:
            for label, interval in (("4H", "4h"), ("1H", "1h"), ("15m", "15m")):
                tf_df = fetch_binance_klines(symbol, interval=interval, limit=100)
                multi_timeframe[label] = _summarize_timeframe(tf_df)

        full_data = {
            "symbol": symbol,
            "asset_type": asset_type,
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "price_data": price_data,
            "technicals_1d": technicals,
            "technicals": technicals,
            "multi_timeframe": multi_timeframe,
            "fear_greed": fear_greed,
            "coingecko": coingecko_data,
            "order_book": {
                "bids_top5": bids[:5],
                "asks_top5": asks[:5],
                "bid_ask_imbalance": {
                    "bid_volume": round(bid_volume, 2),
                    "ask_volume": round(ask_volume, 2),
                    "bias": imbalance_bias,
                },
                "spoof_alert": spoof_info,
            },
            "news": news,
            "sentiment": sentiment,
            "news_sentiment_score": sentiment.get("score") if isinstance(sentiment, dict) else None,
        }

        trade_plan = generate_trade_plan(full_data)
        return JSONResponse({"trade_plan": trade_plan, "data_snapshot": full_data})

    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.on_event("shutdown")
async def shutdown_event():
    await binance.close()
    await finnhub.close()