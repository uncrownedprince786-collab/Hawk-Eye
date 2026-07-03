import httpx, asyncio
TIMEOUT = 8
CG_MAP = {"btc":"bitcoin","eth":"ethereum","sol":"solana","bnb":"binancecoin","xrp":"ripple","ada":"cardano","doge":"dogecoin","dot":"polkadot","matic":"matic-network","avax":"avalanche-2","link":"chainlink","uni":"uniswap","ltc":"litecoin","atom":"cosmos","near":"near","paxg":"pax-gold"}

async def try_first(*tasks, timeout=TIMEOUT):
    for t in tasks:
        try:
            return await asyncio.wait_for(t, timeout=timeout)
        except:
            continue
    return None

async def _cg_price(symbol):
    cid = CG_MAP.get(symbol.lower().replace("usdt",""), symbol.lower().replace("usdt",""))
    async with httpx.AsyncClient(timeout=TIMEOUT) as c:
        r = await c.get(f"https://api.coingecko.com/api/v3/simple/price?ids={cid}&vs_currencies=usd&include_24hr_change=true&include_24hr_vol=true")
        if r.status_code == 200 and cid in r.json():
            d = r.json()[cid]
            return {"price":d["usd"],"change_pct":d.get("usd_24h_change",0),"volume":d.get("usd_24h_vol",0),"high":None,"low":None,"trades":0}
    return None

async def _coincap_price(symbol):
    cid = symbol.lower().replace("usdt","")
    async with httpx.AsyncClient(timeout=TIMEOUT) as c:
        r = await c.get(f"https://api.coincap.io/v2/assets/{cid}")
        if r.status_code == 200 and "data" in r.json():
            d = r.json()["data"]
            return {"price":float(d["priceUsd"]),"change_pct":float(d["changePercent24Hr"]),"volume":float(d["volumeUsd24Hr"]),"high":None,"low":None,"trades":0}
    return None

async def _binance_price(symbol):
    async with httpx.AsyncClient(timeout=TIMEOUT) as c:
        r = await c.get(f"https://api.binance.com/api/v3/ticker/24hr?symbol={symbol.upper()}")
        if r.status_code == 200:
            d = r.json()
            return {"price":float(d["lastPrice"]),"change_pct":float(d["priceChangePercent"]),"volume":float(d["volume"]),"high":float(d["highPrice"]),"low":float(d["lowPrice"]),"trades":int(d["count"])}
    return None

async def fetch_crypto_price(symbol):
    return await try_first(_cg_price(symbol), _coincap_price(symbol), _binance_price(symbol))

async def _cg_ohlc(symbol, days=30):
    cid = CG_MAP.get(symbol.lower().replace("usdt",""), symbol.lower().replace("usdt",""))
    async with httpx.AsyncClient(timeout=TIMEOUT) as c:
        r = await c.get(f"https://api.coingecko.com/api/v3/coins/{cid}/ohlc?vs_currency=usd&days={days}")
        if r.status_code == 200:
            data = r.json()
            return [{"open":d[1],"high":d[2],"low":d[3],"close":d[4],"volume":0} for d in data]
    return None

async def _binance_klines(symbol, interval="1d", limit=200):
    async with httpx.AsyncClient(timeout=TIMEOUT) as c:
        r = await c.get(f"https://api.binance.com/api/v3/klines?symbol={symbol.upper()}&interval={interval}&limit={limit}")
        if r.status_code == 200:
            data = r.json()
            return [{"open":float(d[1]),"high":float(d[2]),"low":float(d[3]),"close":float(d[4]),"volume":float(d[5])} for d in data]
    return None

async def fetch_crypto_ohlc(symbol, days=30):
    return await try_first(_cg_ohlc(symbol, days), _binance_klines(symbol, limit=min(days,200)))

async def _cg_market(symbol):
    cid = CG_MAP.get(symbol.lower().replace("usdt",""), symbol.lower().replace("usdt",""))
    async with httpx.AsyncClient(timeout=TIMEOUT) as c:
        r = await c.get(f"https://api.coingecko.com/api/v3/coins/{cid}?localization=false&tickers=false&community_data=false&developer_data=false")
        if r.status_code == 200:
            d = r.json()["market_data"]
            return {"market_cap":d.get("market_cap",{}).get("usd"),"total_volume":d.get("total_volume",{}).get("usd"),"high_24h":d.get("high_24h",{}).get("usd"),"low_24h":d.get("low_24h",{}).get("usd"),"circulating_supply":d.get("circulating_supply"),"max_supply":d.get("max_supply"),"ath":d.get("ath",{}).get("usd"),"atl":d.get("atl",{}).get("usd"),"price_change_24h":d.get("price_change_percentage_24h"),"price_change_7d":d.get("price_change_percentage_7d"),"price_change_30d":d.get("price_change_percentage_30d")}
    return None

async def fetch_crypto_market(symbol):
    return await try_first(_cg_market(symbol))

async def _binance_orderbook(symbol, limit=20):
    async with httpx.AsyncClient(timeout=TIMEOUT) as c:
        r = await c.get(f"https://api.binance.com/api/v3/depth?symbol={symbol.upper()}&limit={limit}")
        if r.status_code == 200:
            d = r.json()
            return {"bids":[[float(p),float(q)] for p,q in d["bids"]], "asks":[[float(p),float(q)] for p,q in d["asks"]]}
    return None

async def _bybit_orderbook(symbol, limit=20):
    async with httpx.AsyncClient(timeout=TIMEOUT) as c:
        r = await c.get(f"https://api.bybit.com/v5/market/orderbook?category=spot&symbol={symbol.upper()}&limit={limit}")
        if r.status_code == 200:
            d = r.json()["result"]
            return {"bids":[[float(p),float(q)] for p,q in d["b"]], "asks":[[float(p),float(q)] for p,q in d["a"]]}
    return None

async def fetch_orderbook(symbol):
    return await try_first(_binance_orderbook(symbol), _bybit_orderbook(symbol)) or {"bids":[],"asks":[]}
