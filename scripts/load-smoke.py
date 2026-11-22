"""Small concurrency check for a dedicated test stack. Not an LLM benchmark."""
import argparse
import asyncio
import json
import time
from pathlib import Path
from uuid import uuid4
import httpx

async def main(args):
    results=[]
    async def user(index):
        async with httpx.AsyncClient(base_url=args.base_url,timeout=120,trust_env=False) as client:
            headers={'X-Requested-With':'PartnerAgent'}
            response=await client.post('/api/v1/auth/register',headers=headers,json={
                'name':'Load Test','email':uuid4().hex+'@example.com','password':'load-test-password'})
            response.raise_for_status()
            headers['X-CSRF-Token']=response.json()['csrf_token']
            chat=await client.post('/api/v1/conversations',headers=headers,json={})
            chat.raise_for_status();chat_id=chat.json()['id']
            try:
                for i in range(args.turns):
                    started=time.perf_counter()
                    response=await client.post('/api/v1/ask/stream',headers=headers,json={
                        'conversation_id':chat_id,'question':'Расскажи про курс Go','request_id':str(uuid4())})
                    results.append({'user':index,'turn':i,'seconds':round(time.perf_counter()-started,4),
                                    'ok':response.status_code==200 and 'event: done' in response.text and 'event: error' not in response.text and (not args.require_sources or any(line.startswith('data: [') and bool(json.loads(line[6:])) for line in response.text.splitlines()))})
            finally:
                await client.delete('/api/v1/conversations/'+chat_id,headers=headers)
                await client.post('/api/v1/auth/logout',headers=headers)
    await asyncio.gather(*(user(i) for i in range(args.users)))
    latencies=sorted(r['seconds'] for r in results)
    payload={'users':args.users,'requests':len(results),'failed':sum(not r['ok'] for r in results),
             'p95_seconds':latencies[max(0,__import__('math').ceil(len(latencies)*.95)-1)],'results':results}
    target=Path(args.output);target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(payload,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in payload.items() if k!='results'}))
    if payload['failed']:raise SystemExit(1)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url',required=True,help='Dedicated test URL; creates test accounts')
    parser.add_argument('--users',type=int,choices=range(1,6),default=2)
    parser.add_argument('--turns',type=int,choices=range(1,11),default=3)
    parser.add_argument('--require-sources',action='store_true',help='Fail if the answer has no retrieved sources')
    parser.add_argument('--output',default='reports/load-smoke.json')
    asyncio.run(main(parser.parse_args()))
