import asyncio
import json
import httpx
from fastapi import WebSocket
from core.config import FINNHUB_API_KEY

class FinnhubStream:
    def __init__(self):
        self.polling_tasks = {}

    async def subscribe(self, symbol: str, client_ws: WebSocket):
        async def poll():
            while True:
                try:
                    async with httpx.AsyncClient() as client:
                        resp = await client.get(
                            f"https://finnhub.io/api/v1/quote?symbol={symbol}&token={FINNHUB_API_KEY}"
                        )
                        if resp.status_code == 200:
                            data = resp.json()
                            data["symbol"] = symbol
                            await client_ws.send_text(json.dumps(data))
                except:
                    pass
                await asyncio.sleep(5)
        task = asyncio.create_task(poll())
        self.polling_tasks[symbol] = task

    async def close(self):
        for task in self.polling_tasks.values():
            task.cancel()