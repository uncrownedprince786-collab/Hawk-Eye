import yfinance as yf
import pandas as pd
import numpy as np
import httpx


def compute_multi_timeframe_technicals(symbol: str, asset_type: str) -> dict:
    try:
        if asset_type == "crypto":
            df = _fetch_binance_klines(symbol)
        else:
            ticker = yf.Ticker(symbol)
            df = ticker.history(period="6mo")
        if df.empty:
            return {"error": "No price data available"}
        return _calculate_indicators(df)
    except Exception as e:
        return {"error": f"Technical analysis failed: {str(e)}"}


def _fetch_binance_klines(symbol: str, interval="1d", limit=200):
    """Fetch OHLCV data from Binance public API. No API key needed."""
    try:
        url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}"
        resp = httpx.get(url, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            df = pd.DataFrame(data, columns=[
                "open_time", "Open", "High", "Low", "Close", "Volume",
                "close_time", "quote_volume", "trades", "taker_buy_base",
                "taker_buy_quote", "ignore"
            ])
            df["Open"] = df["Open"].astype(float)
            df["High"] = df["High"].astype(float)
            df["Low"] = df["Low"].astype(float)
            df["Close"] = df["Close"].astype(float)
            df["Volume"] = df["Volume"].astype(float)
            df.index = pd.to_datetime(df["open_time"], unit="ms")
            return df
    except Exception:
        pass
    return pd.DataFrame()


def _calculate_indicators(df):
    close = df["Close"]
    high = df["High"]
    low = df["Low"]
    volume = df["Volume"]
    result = {}

    result["current_price"] = round(close.iloc[-1], 2)

    for period in [9, 21, 50, 200]:
        ema = close.ewm(span=period, adjust=False).mean().iloc[-1]
        result[f"ema_{period}"] = round(ema, 2) if not pd.isna(ema) else None

    for period in [20, 50, 200]:
        sma = close.rolling(period).mean().iloc[-1] if len(close) >= period else None
        result[f"sma_{period}"] = round(sma, 2) if sma is not None and not pd.isna(sma) else None

    delta = close.diff()
    gain = delta.clip(lower=0).rolling(14).mean().iloc[-1]
    loss = -delta.clip(upper=0).rolling(14).mean().iloc[-1]
    rs = gain / loss if loss != 0 else float("inf")
    rsi = 100 - (100 / (1 + rs)) if rs != float("inf") else 100.0
    result["rsi_14"] = round(rsi, 2)

    ema_12 = close.ewm(span=12, adjust=False).mean()
    ema_26 = close.ewm(span=26, adjust=False).mean()
    macd_line = ema_12 - ema_26
    signal_line = macd_line.ewm(span=9, adjust=False).mean()
    result["macd"] = round(macd_line.iloc[-1], 4)
    result["macd_signal"] = round(signal_line.iloc[-1], 4)
    result["macd_histogram"] = round((macd_line - signal_line).iloc[-1], 4)
    result["macd_cross"] = "bullish" if macd_line.iloc[-1] > signal_line.iloc[-1] else "bearish"

    low_14 = low.rolling(14).min()
    high_14 = high.rolling(14).max()
    stoch_k = ((close - low_14) / (high_14 - low_14)) * 100
    result["stochastic_k"] = round(stoch_k.iloc[-1], 2)
    result["stochastic_d"] = round(stoch_k.rolling(3).mean().iloc[-1], 2)

    sma_20 = close.rolling(20).mean()
    std_20 = close.rolling(20).std()
    result["bollinger_upper"] = round((sma_20 + 2 * std_20).iloc[-1], 2)
    result["bollinger_lower"] = round((sma_20 - 2 * std_20).iloc[-1], 2)
    result["bollinger_mid"] = round(sma_20.iloc[-1], 2)
    result["bollinger_bandwidth"] = round(((result["bollinger_upper"] - result["bollinger_lower"]) / result["bollinger_mid"]) * 100, 2)

    tr = pd.concat([high - low, (high - close.shift()).abs(), (low - close.shift()).abs()], axis=1).max(axis=1)
    result["atr_14"] = round(tr.rolling(14).mean().iloc[-1], 2)

    recent = df.tail(20)
    result["support_20"] = round(recent["Low"].min(), 2)
    result["resistance_20"] = round(recent["High"].max(), 2)

    recent_50 = df.tail(50)
    if len(recent_50) >= 10:
        try:
            bins = pd.cut(close.tail(50), bins=15)
            vol_profile = recent_50.groupby(bins, observed=False)["Volume"].sum()
            poc_bin = vol_profile.idxmax()
            result["poc"] = round(poc_bin.mid, 2) if not pd.isna(poc_bin) else None
            result["vah"] = round(poc_bin.right, 2) if not pd.isna(poc_bin) else None
            result["val"] = round(poc_bin.left, 2) if not pd.isna(poc_bin) else None
        except Exception:
            result["poc"] = None
            result["vah"] = None
            result["val"] = None
    else:
        result["poc"] = None

    obv = (np.sign(close.diff()) * volume).fillna(0).cumsum()
    result["obv_trend"] = "rising" if obv.iloc[-1] > obv.iloc[-20] else "falling"

    typical_price = (high + low + close) / 3
    vwap_20 = (typical_price * volume).rolling(20).sum() / volume.rolling(20).sum()
    result["vwap"] = round(vwap_20.iloc[-1], 2)
    result["price_vs_vwap"] = "above" if result["current_price"] > result["vwap"] else "below"

    if result["current_price"] > result.get("sma_50", 0) and result.get("sma_50", 0) > result.get("sma_200", 0):
        result["primary_trend"] = "bullish"
    elif result["current_price"] < result.get("sma_50", float("inf")) and result.get("sma_50", float("inf")) < result.get("sma_200", float("inf")):
        result["primary_trend"] = "bearish"
    else:
        result["primary_trend"] = "neutral"

    if result.get("ema_9") and result.get("ema_21") and result.get("ema_50"):
        if result["ema_9"] > result["ema_21"] > result["ema_50"]:
            result["ema_alignment"] = "bullish"
        elif result["ema_9"] < result["ema_21"] < result["ema_50"]:
            result["ema_alignment"] = "bearish"
        else:
            result["ema_alignment"] = "mixed"
    else:
        result["ema_alignment"] = "unknown"

    return result


def get_fear_greed_index() -> dict:
    try:
        resp = httpx.get("https://api.alternative.me/fng/?limit=1", timeout=10)
        if resp.status_code == 200:
            data = resp.json()["data"][0]
            return {
                "value": int(data["value"]),
                "classification": data["value_classification"]
            }
    except Exception:
        pass
    return {"value": None, "classification": "unavailable"}


def get_coingecko_market_data(coin_id: str) -> dict:
    try:
        url = f"https://api.coingecko.com/api/v3/coins/{coin_id}?localization=false&tickers=false&community_data=true&developer_data=true"
        resp = httpx.get(url, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            market = data.get("market_data", {})
            return {
                "name": data.get("name"),
                "symbol": data.get("symbol"),
                "market_cap_rank": market.get("market_cap_rank"),
                "market_cap": market.get("market_cap", {}).get("usd"),
                "total_volume": market.get("total_volume", {}).get("usd"),
                "high_24h": market.get("high_24h", {}).get("usd"),
                "low_24h": market.get("low_24h", {}).get("usd"),
                "price_change_24h": market.get("price_change_percentage_24h"),
                "price_change_7d": market.get("price_change_percentage_7d"),
                "price_change_30d": market.get("price_change_percentage_30d"),
                "circulating_supply": market.get("circulating_supply"),
                "total_supply": market.get("total_supply"),
                "max_supply": market.get("max_supply"),
                "ath": market.get("ath", {}).get("usd"),
                "ath_date": market.get("ath_date", {}).get("usd"),
                "atl": market.get("atl", {}).get("usd"),
                "atl_date": market.get("atl_date", {}).get("usd"),
                "developer_score": data.get("developer_data", {}).get("score"),
                "community_score": data.get("community_data", {}).get("score"),
                "sentiment_votes_up": data.get("sentiment_votes_up_percentage"),
                "sentiment_votes_down": data.get("sentiment_votes_down_percentage"),
            }
    except Exception:
        pass
    return {}