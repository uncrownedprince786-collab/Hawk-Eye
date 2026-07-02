import asyncio
import json
import httpx
from fastapi import WebSocket
from core.config import FINNHUB_API_KEY

TIMEOUT = 10


class BinanceStream:
    async def subscribe(self, symbol: str, websocket: WebSocket):
        while True:
            try:
                async with httpx.AsyncClient(timeout=TIMEOUT) as client:
                    resp = await client.get(f"https://api.binance.com/api/v3/ticker/24hr?symbol={symbol}")
                    if resp.status_code == 200:
                        await websocket.send_text(json.dumps(resp.json()))
            except Exception:
                pass
            await asyncio.sleep(5)

    async def close(self):
        pass


class FinnhubStream:
    async def subscribe(self, symbol: str, websocket: WebSocket):
        async def poll():
            while True:
                try:
                    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
                        resp = await client.get(f"https://finnhub.io/api/v1/quote?symbol={symbol}&token={FINNHUB_API_KEY}")
                        if resp.status_code == 200:
                            data = resp.json()
                            data["symbol"] = symbol
                            await websocket.send_text(json.dumps(data))
                except Exception:
                    pass
                await asyncio.sleep(5)

        asyncio.create_task(poll())

    async def close(self):
        pass
