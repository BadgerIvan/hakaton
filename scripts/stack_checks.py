"""Wait for the test stack and run the DB suites and real HTTP workflow."""
import os
from pathlib import Path
import subprocess
import sys
import time
import httpx

root=Path(__file__).resolve().parents[1]
with httpx.Client(trust_env=False,timeout=3) as client:
    for attempt in range(120):
        try:
            a=client.get('http://auth:8002/health')
            b=client.get('http://backend:8000/health')
            c=client.get('http://rag-service:8001/health')
            if a.status_code==b.status_code==c.status_code==200:break
        except httpx.HTTPError:pass
        time.sleep(1)
    else:raise SystemExit('Test stack did not become ready within 120 seconds')
subprocess.run([sys.executable,'scripts/test.py','--integration','--no-frontend','--coverage'],cwd=root,check=True)
subprocess.run([sys.executable,'-m','pytest','tests/system','-q','--junitxml=reports/system.xml'],cwd=root,check=True)
