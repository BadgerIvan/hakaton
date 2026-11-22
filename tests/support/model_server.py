"""Deterministic Ollama protocol double; no weights, no claims about answer quality."""
import asyncio
import json
from datetime import datetime, timezone
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
app=FastAPI()

@app.get('/api/tags')
def tags():return {'models':[{'name':'qwen3:4b'},{'name':'bge-m3:latest'}]}

@app.post('/api/embed')
async def embed(request:Request):
    data=await request.json();texts=data.get('input',[])
    if isinstance(texts,str):texts=[texts]
    vectors=[]
    for text in texts:
        row=[0.]*1024;row[0 if 'go' in text.lower() else 1]=1.;vectors.append(row)
    return {'model':data.get('model'),'embeddings':vectors,'total_duration':1,'load_duration':1,'prompt_eval_count':1}

@app.post('/api/chat')
async def chat(request:Request):
    data=await request.json();messages=data.get('messages',[])
    system=' '.join(m.get('content','') for m in messages if m['role']=='system')
    question=next((m.get('content','') for m in reversed(messages) if m['role']=='user'),'')
    rewrite='переписываешь' in system
    if rewrite:answer='Что я выбрал из курсов Go?' if 'что я выбрал' in question.lower() else 'Курс Go ШИФТ'
    elif 'что я выбрал' in question.lower() and 'Хочу изучать Go' in system:answer='Вы выбрали Go. Курс Go длится 12 недель.'
    else:answer='Курс Go длится 12 недель. Обучение проходит онлайн.'
    def packet(text,done=False):
        return {'model':data.get('model','qwen3:4b'),'created_at':datetime.now(timezone.utc).isoformat(),
                'message':{'role':'assistant','content':text},'done':done,'done_reason':'stop' if done else None,
                'total_duration':1,'load_duration':1,'prompt_eval_count':1,'eval_count':1}
    if not data.get('stream'):return packet(answer,True)
    async def stream():
        for token in answer.split(' '):
            await asyncio.sleep(.015)
            yield json.dumps(packet(token+' '),ensure_ascii=False)+'\n'
        yield json.dumps(packet('',True))+'\n'
    return StreamingResponse(stream(),media_type='application/x-ndjson')
