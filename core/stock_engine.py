import httpx, asyncio, yfinance as yf, os
TIMEOUT = 8
from core.config import FINNHUB_API_KEY
ALPHA_KEY = os.getenv("ALPHA_VANTAGE_KEY", "demo")

async def try_first(*tasks, timeout=TIMEOUT):
    for t in tasks:
        try:
            return await asyncio.wait_for(t, timeout=timeout)
        except:
            continue
    return None

async def _finnhub_quote(symbol):
    async with httpx.AsyncClient(timeout=TIMEOUT) as c:
        r = await c.get(f"https://finnhub.io/api/v1/quote?symbol={symbol}&token={FINNHUB_API_KEY}")
        if r.status_code == 200:
            d = r.json()
            if d.get("c"):
                return {"price":d["c"],"change_pct":d.get("dp",0),"volume":d.get("v",0),"high":d["h"],"low":d["l"],"trades":0}
    return None

async def _alpha_quote(symbol):
    async with httpx.AsyncClient(timeout=TIMEOUT) as c:
        r = await c.get(f"https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol={symbol}&apikey={ALPHA_KEY}")
        if r.status_code == 200:
            d = r.json().get("Global Quote",{})
            if d and d.get("05. price"):
                return {"price":float(d["05. price"]),"change_pct":float(d.get("10. change percent","0").replace("%","")),"volume":int(d.get("06. volume",0)),"high":float(d.get("03. high",0)),"low":float(d.get("04. low",0)),"trades":0}
    return None

async def _yf_quote(symbol):
    try:
        t = yf.Ticker(symbol)
        hist = t.history(period="1d")
        if not hist.empty:
            price = hist["Close"].iloc[-1]
            prev = t.info.get("previousClose", price)
            change = ((price-prev)/prev)*100 if prev else 0
            return {"price":price,"change_pct":change,"volume":hist["Volume"].iloc[-1] if "Volume" in hist else 0,"high":hist["High"].iloc[-1],"low":hist["Low"].iloc[-1],"trades":0}
    except:
        pass
    return None

async def fetch_stock_quote(symbol):
    return await try_first(_finnhub_quote(symbol), _alpha_quote(symbol), _yf_quote(symbol))

async def _finnhub_profile(symbol):
    async with httpx.AsyncClient(timeout=TIMEOUT) as c:
        r = await c.get(f"https://finnhub.io/api/v1/stock/profile2?symbol={symbol}&token={FINNHUB_API_KEY}")
        if r.status_code == 200:
            d = r.json()
            if d:
                return {"name":d.get("name",symbol),"sector":d.get("finnhubIndustry",""),"market_cap":d.get("marketCapitalization",0)*1e6}
    return None

async def fetch_stock_fundamentals(symbol):
    return await try_first(_finnhub_profile(symbol))

async def _alpha_daily(symbol):
    async with httpx.AsyncClient(timeout=TIMEOUT) as c:
        r = await c.get(f"https://www.alphavantage.co/query?function=TIME_SERIES_DAILY&symbol={symbol}&outputsize=compact&apikey={ALPHA_KEY}")
        if r.status_code == 200:
            data = r.json().get("Time Series (Daily)",{})
            candles = []
            for date, vals in sorted(data.items())[-90:]:
                candles.append({"open":float(vals["1. open"]),"high":float(vals["2. high"]),"low":float(vals["3. low"]),"close":float(vals["4. close"]),"volume":int(vals["5. volume"])})
            return candles
    return None

async def _yf_daily(symbol):
    try:
        t = yf.Ticker(symbol)
        hist = t.history(period="3mo")
        if not hist.empty:
            return [{"open":r["Open"],"high":r["High"],"low":r["Low"],"close":r["Close"],"volume":r["Volume"]} for _,r in hist.iterrows()]
    except:
        pass
    return None

async def fetch_stock_ohlc(symbol):
    return await try_first(_alpha_daily(symbol), _yf_daily(symbol))
