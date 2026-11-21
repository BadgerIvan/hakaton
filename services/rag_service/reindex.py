"""Run inside the RAG container: python /app/reindex.py."""
import urllib.error
import urllib.request

try:
    request = urllib.request.Request('http://127.0.0.1:8001/api/v1/reindex', method='POST')
    with urllib.request.urlopen(request, timeout=1800) as response:
        print(response.read().decode())
except urllib.error.HTTPError as error:
    raise SystemExit(error.read().decode()) from None
