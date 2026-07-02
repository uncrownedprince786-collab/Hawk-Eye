import httpx
import asyncio
import websockets

print('HTTP status', httpx.get('http://127.0.0.1:8000/').status_code)

async def test_ws():
    uri = 'ws://127.0.0.1:8000/ws/BTCUSDT'
    try:
        async with websockets.connect(uri) as ws:
            print('WS connected')
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=5)
                print('WS received', msg[:200])
            except Exception as e:
                print('WS no message', e)
    except Exception as e:
        print('WS failed', e)

asyncio.run(test_ws())