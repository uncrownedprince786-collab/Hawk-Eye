import httpx
import pandas as pd
import yfinance as yf
from .config import FINNHUB_API_KEY
from .technicals import compute_multi_timeframe_technicals

TIMEOUT = 12

CRYPTO_SYMBOLS = {
    "BTC": "BTCUSDT",
    "ETH": "ETHUSDT",
    "SOL": "SOLUSDT",
    "BNB": "BNBUSDT",
    "XRP": "XRPUSDT",
    "ADA": "ADAUSDT",
    "DOGE": "DOGEUSDT",
    "DOT": "DOTUSDT",
    "MATIC": "MATICUSDT",
    "AVAX": "AVAXUSDT",
    "LINK": "LINKUSDT",
    "UNI": "UNIUSDT",
    "LTC": "LTCUSDT",
    "ATOM": "ATOMUSDT",
    "NEAR": "NEARUSDT",
    "ALGO": "ALGOUSDT",
    "VET": "VETUSDT",
    "ICP": "ICPUSDT",
    "FIL": "FILUSDT",
    "APT": "APTUSDT",
    "ARB": "ARBUSDT",
    "OP": "OPUSDT",
    "XAU": "XAUUSDT",
    "XAG": "XAGUSDT",
}

COIN_MAP = {
    "btc": "bitcoin",
    "eth": "ethereum",
    "sol": "solana",
    "bnb": "binancecoin",
    "xrp": "ripple",
    "ada": "cardano",
    "doge": "dogecoin",
    "dot": "polkadot",
    "matic": "matic-network",
    "avax": "avalanche-2",
    "link": "chainlink",
    "uni": "uniswap",
    "ltc": "litecoin",
    "atom": "cosmos",
    "near": "near",
    "algo": "algorand",
    "vet": "vechain",
    "icp": "internet-computer",
    "fil": "filecoin",
    "apt": "aptos",
    "arb": "arbitrum",
    "op": "optimism",
    "xau": "gold",
    "xag": "silver",
}


def classify_asset_type(symbol: str) -> str:
    s = (symbol or "").strip().upper()
    if not s:
        return "unknown"
    if s in {"XAUUSD", "XAGUSD", "XAUUSDT", "XAGUSDT", "XAU", "XAG", "GOLD", "SILVER"}:
        return "commodity"
    if s.endswith(("USDT", "USD", "BTC", "ETH", "BNB", "SOL", "ADA", "XRP", "DOGE", "LTC", "MATIC", "DOT", "LINK", "UNI", "AVAX", "ATOM", "NEAR", "ALGO", "VET", "ICP", "FIL", "APT", "ARB", "OP")) or len(s) > 5:
        return "crypto"
    return "stock"


def normalize_symbol(symbol: str, asset_type: str | None = None) -> str:
    s = (symbol or "").strip().upper()
    if not s:
        return s
    if asset_type == "commodity":
        if s in {"XAUUSD", "XAU", "GOLD"}:
            return "XAUUSDT"
        if s in {"XAGUSD", "XAG", "SILVER"}:
            return "XAGUSDT"
        return s
    if asset_type == "crypto":
        if s in CRYPTO_SYMBOLS:
            return CRYPTO_SYMBOLS[s]
        if s.endswith("USD"):
            return s[:-3] + "USDT"
        if s.endswith("USDT"):
            return s
        return s + "USDT"
    return s


def fetch_binance_klines(symbol: str, interval: str = "1d", limit: int = 200) -> pd.DataFrame:
    try:
        url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}"
        resp = httpx.get(url, timeout=TIMEOUT)
        if resp.status_code != 200:
            return pd.DataFrame()
        data = resp.json()
        df = pd.DataFrame(data, columns=["ot", "O", "H", "L", "C", "V", "ct", "qv", "trades", "tbb", "tbq", "ig"])
        for col in ["O", "H", "L", "C", "V"]:
            df[col] = df[col].astype(float)
        df.index = pd.to_datetime(df["ot"], unit="ms")
        return df
    except Exception:
        return pd.DataFrame()


async def fetch_binance_ticker(symbol: str) -> dict:
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            r = await client.get(f"https://api.binance.com/api/v3/ticker/24hr?symbol={symbol}")
            if r.status_code == 200:
                d = r.json()
                return {
                    "price": float(d["lastPrice"]),
                    "change_pct": float(d["priceChangePercent"]),
                    "volume": float(d["volume"]),
                    "high": float(d["highPrice"]),
                    "low": float(d["lowPrice"]),
                    "trades": int(d["count"]),
                }
    except Exception:
        pass
    return {}


async def fetch_binance_orderbook(symbol: str, limit: int = 20) -> dict:
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            r = await client.get(f"https://api.binance.com/api/v3/depth?symbol={symbol}&limit={limit}")
            if r.status_code == 200:
                d = r.json()
                return {
                    "bids": [[float(p), float(q)] for p, q in d["bids"]],
                    "asks": [[float(p), float(q)] for p, q in d["asks"]],
                }
    except Exception:
        pass
    return {"bids": [], "asks": []}


async def fetch_coingecko_data(coin_id: str) -> dict:
    try:
        cid = COIN_MAP.get((coin_id or "").lower(), coin_id)
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(f"https://api.coingecko.com/api/v3/coins/{cid}?localization=false&tickers=false&community_data=true&developer_data=true")
            if r.status_code == 200:
                d = r.json()
                m = d.get("market_data", {})
                return {
                    "name": d.get("name"),
                    "symbol": d.get("symbol"),
                    "market_cap_rank": m.get("market_cap_rank"),
                    "market_cap": m.get("market_cap", {}).get("usd"),
                    "total_volume": m.get("total_volume", {}).get("usd"),
                    "high_24h": m.get("high_24h", {}).get("usd"),
                    "low_24h": m.get("low_24h", {}).get("usd"),
                    "change_24h": m.get("price_change_percentage_24h"),
                    "change_7d": m.get("price_change_percentage_7d"),
                    "change_30d": m.get("price_change_percentage_30d"),
                    "circ_supply": m.get("circulating_supply"),
                    "total_supply": m.get("total_supply"),
                    "max_supply": m.get("max_supply"),
                    "ath": m.get("ath", {}).get("usd"),
                    "atl": m.get("atl", {}).get("usd"),
                    "dev_score": d.get("developer_data", {}).get("score"),
                    "community_score": d.get("community_data", {}).get("score"),
                    "sentiment_up": d.get("sentiment_votes_up_percentage"),
                    "sentiment_down": d.get("sentiment_votes_down_percentage"),
                }
    except Exception:
        pass
    return {}


async def fetch_fear_greed() -> dict:
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            r = await client.get("https://api.alternative.me/fng/?limit=1")
            if r.status_code == 200:
                d = r.json()["data"][0]
                return {"value": int(d["value"]), "classification": d["value_classification"]}
    except Exception:
        pass
    return {"value": None, "classification": "unavailable"}


async def fetch_coins_list(limit: int = 50) -> list:
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(f"https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&order=market_cap_desc&per_page={limit}&page=1&sparkline=true&price_change_percentage=1h,24h,7d")
            if r.status_code == 200:
                return r.json()
    except Exception:
        pass
    return []


async def fetch_news(symbol: str) -> list:
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            r = await client.get(f"https://finnhub.io/api/v1/news?category=general&token={FINNHUB_API_KEY}")
            if r.status_code == 200:
                return [{"headline": a["headline"], "summary": (a.get("summary", "") or "")[:200]} for a in r.json()[:5]]
    except Exception:
        pass
    return []


def fetch_stock_data(symbol: str) -> dict:
    try:
        ticker = yf.Ticker(symbol)
        info = ticker.info
        hist = ticker.history(period="1d")
        if hist.empty:
            return {}
        return {
            "symbol": symbol,
            "price": round(hist["Close"].iloc[-1], 2),
            "change_pct": round(((hist["Close"].iloc[-1] - hist["Open"].iloc[-1]) / hist["Open"].iloc[-1]) * 100, 2),
            "volume": int(hist["Volume"].iloc[-1]),
            "name": info.get("longName", symbol),
            "sector": info.get("sector", "N/A"),
            "market_cap": info.get("marketCap"),
            "pe_ratio": info.get("trailingPE"),
            "eps": info.get("trailingEps"),
            "beta": info.get("beta"),
            "52w_high": info.get("fiftyTwoWeekHigh"),
            "52w_low": info.get("fiftyTwoWeekLow"),
        }
    except Exception:
        return {}


def fetch_stock_technicals(symbol: str) -> dict:
    try:
        df = yf.Ticker(symbol).history(period="6mo")
        if df.empty:
            return {}
        return compute_multi_timeframe_technicals(symbol, "stock")
    except Exception:
        return {}
