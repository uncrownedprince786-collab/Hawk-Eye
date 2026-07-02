import os
import httpx
import pandas as pd
import numpy as np
import yfinance as yf

TIMEOUT = 12

CG_MAP = {
    "btc":"bitcoin","eth":"ethereum","sol":"solana","bnb":"binancecoin",
    "xrp":"ripple","ada":"cardano","doge":"dogecoin","dot":"polkadot",
    "matic":"matic-network","avax":"avalanche-2","link":"chainlink",
    "uni":"uniswap","ltc":"litecoin","atom":"cosmos","near":"near",
    "algo":"algorand","vet":"vechain","icp":"internet-computer",
    "fil":"filecoin","apt":"aptos","arb":"arbitrum","op":"optimism",
    "trx":"tron","shib":"shiba-inu","etc":"ethereum-classic",
    "xlm":"stellar","ftm":"fantom","aave":"aave","eos":"eos",
    "paxg":"pax-gold"
}

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

async def fetch_crypto_ticker(symbol: str) -> dict:
    coin_id = symbol.lower().replace("usdt","")
    cid = CG_MAP.get(coin_id, coin_id)
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as c:
            url = f"https://api.coingecko.com/api/v3/simple/price?ids={cid}&vs_currencies=usd&include_24hr_change=true&include_24hr_vol=true"
            r = await c.get(url)
            if r.status_code == 200 and r.json().get(cid):
                d = r.json()[cid]
                return {
                    "price": d.get("usd",0),
                    "change_pct": d.get("usd_24h_change",0),
                    "volume": d.get("usd_24h_vol",0),
                    "high": None, "low": None, "trades": 0
                }
    except:
        pass
    return {}

async def fetch_binance_ticker(symbol: str) -> dict:
    return await fetch_crypto_ticker(symbol)

async def fetch_crypto_orderbook(symbol: str, limit=20) -> dict:
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as c:
            r = await c.get(f"https://api.binance.com/api/v3/depth?symbol={symbol}&limit={limit}")
            if r.status_code == 200:
                d = r.json()
                return {"bids":[[float(p),float(q)] for p,q in d["bids"]],
                        "asks":[[float(p),float(q)] for p,q in d["asks"]]}
    except:
        pass
    return {"bids":[],"asks":[]}

async def fetch_binance_orderbook(symbol: str, limit=20) -> dict:
    return await fetch_crypto_orderbook(symbol, limit)

def fetch_binance_klines(symbol: str, interval="1d", limit=200) -> pd.DataFrame:
    try:
        url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}"
        resp = httpx.get(url, timeout=TIMEOUT)
        if resp.status_code != 200:
            return pd.DataFrame()
        data = resp.json()
        df = pd.DataFrame(data, columns=["ot","O","H","L","C","V","ct","qv","trades","tbb","tbq","ig"])
        for col in ["O","H","L","C","V"]:
            df[col] = df[col].astype(float)
        df.index = pd.to_datetime(df["ot"], unit="ms")
        return df
    except:
        return pd.DataFrame()

async def fetch_coingecko_data(coin_id: str) -> dict:
    try:
        cid = CG_MAP.get(coin_id, coin_id)
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.get(f"https://api.coingecko.com/api/v3/coins/{cid}?localization=false&tickers=false&community_data=true&developer_data=true")
            if r.status_code == 200:
                d = r.json()
                m = d.get("market_data",{})
                return {
                    "name":d.get("name"),"symbol":d.get("symbol"),
                    "market_cap_rank":m.get("market_cap_rank"),
                    "market_cap":m.get("market_cap",{}).get("usd"),
                    "total_volume":m.get("total_volume",{}).get("usd"),
                    "high_24h":m.get("high_24h",{}).get("usd"),
                    "low_24h":m.get("low_24h",{}).get("usd"),
                    "change_24h":m.get("price_change_percentage_24h"),
                    "change_7d":m.get("price_change_percentage_7d"),
                    "change_30d":m.get("price_change_percentage_30d"),
                    "circ_supply":m.get("circulating_supply"),
                    "total_supply":m.get("total_supply"),
                    "max_supply":m.get("max_supply"),
                    "ath":m.get("ath",{}).get("usd"),
                    "atl":m.get("atl",{}).get("usd"),
                    "dev_score":d.get("developer_data",{}).get("score"),
                    "community_score":d.get("community_data",{}).get("score"),
                    "sentiment_up":d.get("sentiment_votes_up_percentage"),
                    "sentiment_down":d.get("sentiment_votes_down_percentage")
                }
    except:
        pass
    return {}

async def fetch_fear_greed() -> dict:
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as c:
            r = await c.get("https://api.alternative.me/fng/?limit=1")
            if r.status_code == 200:
                d = r.json()["data"][0]
                return {"value":int(d["value"]),"classification":d["value_classification"]}
    except:
        pass
    return {"value":None,"classification":"unavailable"}

async def fetch_coins_list(limit=50) -> list:
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.get(f"https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&order=market_cap_desc&per_page={limit}&page=1&sparkline=true&price_change_percentage=1h,24h,7d")
            if r.status_code == 200:
                return r.json()
    except:
        pass
    return await fetch_coincap_coins(limit)

async def fetch_news(symbol: str) -> list:
    from .config import FINNHUB_API_KEY, NEWS_DATA_KEY
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as c:
            query = symbol.replace("USDT","").replace("USD","")
            url = f"https://newsdata.io/api/1/latest?apikey={NEWS_DATA_KEY}&q={query}&language=en&size=5"
            r = await c.get(url)
            if r.status_code == 200:
                data = r.json()
                if data.get("status") == "success" and data.get("results"):
                    return [{"headline":a.get("title",""),"summary":(a.get("description") or "")[:200]} for a in data["results"][:5]]
    except:
        pass
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as c:
            r = await c.get(f"https://finnhub.io/api/v1/news?category=general&token={FINNHUB_API_KEY}")
            if r.status_code == 200:
                return [{"headline":a["headline"],"summary":(a.get("summary","") or "")[:200]} for a in r.json()[:5]]
    except:
        pass
    return [{"headline":"News unavailable","summary":""}]

def fetch_stock_data(symbol: str) -> dict:
    try:
        t = yf.Ticker(symbol)
        info = t.info
        hist = t.history(period="1d")
        if hist.empty:
            return {}
        return {
            "symbol":symbol,
            "price":round(hist["Close"].iloc[-1],2),
            "change_pct":round(((hist["Close"].iloc[-1]-hist["Open"].iloc[-1])/hist["Open"].iloc[-1])*100,2),
            "volume":int(hist["Volume"].iloc[-1]),
            "name":info.get("longName",symbol),
            "sector":info.get("sector","N/A"),
            "market_cap":info.get("marketCap"),
            "pe_ratio":info.get("trailingPE"),
            "eps":info.get("trailingEps"),
            "beta":info.get("beta"),
            "52w_high":info.get("fiftyTwoWeekHigh"),
            "52w_low":info.get("fiftyTwoWeekLow")
        }
    except:
        return {}

async def fetch_coincap_coins(limit=50) -> list:
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
                    "sparkline_in_7d": {"price": []},
                    "price_change_percentage_1h_in_currency": None,
                    "price_change_percentage_7d_in_currency": None
                } for d in data]
    except:
        pass
    return []