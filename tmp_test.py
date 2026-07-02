import httpx
try:
    print('GET / root')
    r = httpx.get('http://127.0.0.1:8000/', timeout=10.0)
    print(r.status_code)
    print(r.text[:100])
except Exception as e:
    print('GET error', repr(e))
try:
    print('POST /analyze BTCUSDT')
    r = httpx.post('http://127.0.0.1:8000/analyze', json={'symbol':'BTCUSDT','type':'crypto'}, timeout=30.0)
    print(r.status_code)
    print(r.text[:600])
except Exception as e:
    print('POST error', repr(e))
try:
    print('POST /analyze AAPL')
    r = httpx.post('http://127.0.0.1:8000/analyze', json={'symbol':'AAPL','type':'stock'}, timeout=30.0)
    print(r.status_code)
    print(r.text[:600])
except Exception as e:
    print('POST error', repr(e))
