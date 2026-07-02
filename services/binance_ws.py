import json
import websockets
from fastapi import WebSocket
import httpx

class BinanceStream:
    def __init__(self):
        self.connections = {}
        self.ws = None

    async def subscribe(self, symbol: str, client_ws: WebSocket):
        symbol = symbol.lower()
        self.connections[symbol] = client_ws
        url = f"wss://stream.binance.com:9443/stream?streams={symbol}@ticker/{symbol}@depth20"
        try:
            async with websockets.connect(url) as ws:
                self.ws = ws
                async for msg in ws:
                    data = json.loads(msg)
                    if "data" in data:
                        payload = data["data"]
                    else:
                        payload = data
                    try:
                        await client_ws.send_text(json.dumps(payload))
                    except Exception:
                        break
        except Exception as e:
            try:
                await client_ws.send_text(json.dumps({"error": str(e)}))
            except Exception:
                pass

    async def get_order_book_snapshot(self, symbol: str) -> dict:
        url = f"https://api.binance.com/api/v3/depth?symbol={symbol}&limit=20"
        async with httpx.AsyncClient() as client:
            resp = await client.get(url)
            if resp.status_code == 200:
                d = resp.json()
                return {"bids": [[float(p), float(q)] for p, q in d["bids"]],
                        "asks": [[float(p), float(q)] for p, q in d["asks"]]}
        return {"bids": [], "asks": []}

    async def close(self):
        if self.ws:
            await self.ws.close()