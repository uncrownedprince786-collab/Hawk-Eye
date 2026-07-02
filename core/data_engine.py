# ========== FALLBACK APIs ==========

async def fetch_coincap_coins(limit=50) -> list:
    """Fallback: CoinCap API for coin list."""
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as c:
            r = await c.get(f"https://api.coincap.io/v2/assets?limit={limit}")
            if r.status_code == 200:
                data = r.json().get("data", [])
                return [{
                    "id": d["id"], "symbol": d["symbol"].upper(), "name": d["name"],
                    "current_price": float(d.get("priceUsd", 0)),
                    "price_change_percentage_24h": float(d.get("changePercent24Hr", 0)),
                    "market_cap": float(d.get("marketCapUsd", 0)),
                    "total_volume": float(d.get("volumeUsd24Hr", 0)),
                    "sparkline_in_7d": {"price": []}
                } for d in data]
    except:
        pass
    return []

async def fetch_coincap_price(coin_id: str) -> dict:
    """Fallback: CoinCap price for single coin."""
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as c:
            r = await c.get(f"https://api.coincap.io/v2/assets/{coin_id}")
            if r.status_code == 200:
                d = r.json().get("data", {})
                return {
                    "price": float(d.get("priceUsd", 0)),
                    "change_pct": float(d.get("changePercent24Hr", 0)),
                    "volume": float(d.get("volumeUsd24Hr", 0)),
                    "high": None, "low": None, "trades": 0
                }
    except:
        pass
    return {}

async def fetch_alpha_vantage_stock(symbol: str) -> dict:
    """Fallback: Alpha Vantage for stocks."""
    AV_KEY = os.getenv("ALPHA_VANTAGE_KEY", "demo")
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as c:
            r = await c.get(f"https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol={symbol}&apikey={AV_KEY}")
            if r.status_code == 200:
                d = r.json().get("Global Quote", {})
                if d:
                    return {
                        "symbol": symbol, "price": float(d.get("05. price", 0)),
                        "change_pct": float(d.get("10. change percent", "0%").replace("%", "")),
                        "volume": int(d.get("06. volume", 0)),
                        "name": symbol, "sector": "N/A"
                    }
    except:
        pass
    return {}