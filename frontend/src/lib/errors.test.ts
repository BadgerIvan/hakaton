import assert from "node:assert/strict";
import test from "node:test";
import { ApiError, authApi, chatApi, errorMessage, responseError } from "./api";
import { streamAnswer, SSEDecoder } from "./sse";

test("API errors hide 5xx internals and handle HTML proxy replies", async () => {
  const error=await responseError(Response.json({detail:"postgres://private-password"},{status:502}));
  assert.equal(error.status,502);assert.ok(!error.message.includes("private-password"));
  assert.equal((await responseError(new Response("<h1>502</h1>",{status:502}))).status,502);
  assert.match((await responseError(Response.json({detail:[{input:"secret"}]},{status:422}))).message,/Проверьте/);
  assert.match(errorMessage(new DOMException("slow","TimeoutError")),/долго/);
  assert.equal(errorMessage(new ApiError("known",401)),"known");
});

test("pagination fetches all history pages instead of losing older dialogs", async context => {
  const old=globalThis.fetch;context.after(()=>{globalThis.fetch=old;});
  const offsets:number[]=[];
  globalThis.fetch=async (url)=>{
    const offset=Number(new URL(String(url),"http://test").searchParams.get("offset"));offsets.push(offset);
    return Response.json(Array.from({length:offset===0?100:2},(_,i)=>({id:String(offset+i),title:"Chat",updatedAt:1})));
  };
  const chats=await chatApi.list();assert.equal(chats.length,102);assert.deepEqual(offsets,[0,100]);
});

test("auth login uses cookies and does not send CSRF before authentication", async context => {
  const old=globalThis.fetch;context.after(()=>{globalThis.fetch=old;});
  globalThis.fetch=async (_url,options)=>{
    assert.equal(options?.credentials,"include");
    assert.equal(new Headers(options?.headers).get("X-Requested-With"),"PartnerAgent");
    assert.deepEqual(JSON.parse(String(options?.body)),{email:"test@example.com",password:"secret"});
    return Response.json({user:{id:"1"},csrf_token:"csrf"});
  };
  await authApi.login("test@example.com","secret");
});

for (const [name,body,contentType] of [
  ["malformed JSON",'event: token\ndata: {bad}\n\n',"text/event-stream"],
  ["invalid token",'event: token\ndata: {"text":42}\n\n',"text/event-stream"],
  ["invalid sources",'event: sources\ndata: {}\n\n',"text/event-stream"],
  ["upstream error",'event: error\ndata: {"detail":"secret"}\n\n',"text/event-stream"],
  ["wrong content type","<html/>","text/html"],
] as const) {
  test(`stream rejects ${name}`,async context=>{
    const old=globalThis.fetch;context.after(()=>{globalThis.fetch=old;});
    globalThis.fetch=async ()=>new Response(body,{headers:{"Content-Type":contentType}});
    await assert.rejects(streamAnswer({question:"Go",conversationId:"chat",requestId:"turn",csrf:"csrf",signal:new AbortController().signal,onToken:()=>{},onSources:()=>{}}));
  });
}

test("pre-aborted requests preserve cancellation",async context=>{
  const old=globalThis.fetch;context.after(()=>{globalThis.fetch=old;});
  globalThis.fetch=async (_url,options)=>{
    assert.equal(options?.signal?.aborted,true);
    throw new DOMException("aborted","AbortError");
  };
  const controller=new AbortController();controller.abort();
  await assert.rejects(streamAnswer({question:"Go",conversationId:"chat",requestId:"turn",csrf:"csrf",signal:controller.signal,onToken:()=>{},onSources:()=>{}}),{name:"AbortError"});
});

test("SSE unknown fields are ignored and default event is message",()=>{
  const decoder=new SSEDecoder();
  assert.deepEqual(decoder.feed('id: 12\nretry: 1\ndata: hello\n\n'),[{event:"message",data:"hello"}]);
});
