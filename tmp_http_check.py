import urllib.request
req = urllib.request.Request('http://127.0.0.1:8000/', method='GET')
with urllib.request.urlopen(req, timeout=20) as resp:
    print(resp.status)
    print(resp.read(200).decode('utf-8', 'ignore'))
