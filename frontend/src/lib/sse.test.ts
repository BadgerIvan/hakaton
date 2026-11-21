import assert from "node:assert/strict";
import test from "node:test";
import { SSEDecoder, streamAnswer } from "./sse";
import { chatApi, safeSourceUrl } from "./api";
import type { Source } from "../types";

test("SSE preserves CRLF across chunks, ignores comments and combines multiline data", () => {
  const parser = new SSEDecoder();
  assert.deepEqual(parser.feed(": ping\r"), []);
  assert.deepEqual(parser.feed("\nevent: token\r\ndata: first\r"), []);
  assert.deepEqual(parser.feed("\ndata: second\r\n\r\n"), [
    { event: "token", data: "first\nsecond" },
  ]);
});

test("stream consumes the supplied contract even with byte-by-byte UTF-8 delivery", async (context) => {
  const previousFetch = globalThis.fetch;
  context.after(() => {
    globalThis.fetch = previousFetch;
  });
  const events =
    'event: meta\ndata: {"conversation_id":"chat-1"}\n\n' +
    'event: sources\ndata: [{"doc_id":"abc123","source":"reglament.pdf","page":4,"score":0.78}]\n\n' +
    'event: token\ndata: {"text":"Заявление "}\n\n' +
    'event: token\ndata: {"text":"подаётся за 14 дней."}\n\n' +
    "event: done\ndata: {}\n\n";
  const bytes = new TextEncoder().encode(events);
  let body: Record<string, unknown> = {};
  globalThis.fetch = async (_url, options) => {
    body = JSON.parse(String(options?.body));
    assert.equal(options?.credentials, "include");
    return new Response(
      new ReadableStream({
        start(controller) {
          for (const byte of bytes) controller.enqueue(Uint8Array.of(byte));
          controller.close();
        },
      }),
      { headers: { "Content-Type": "text/event-stream; charset=utf-8" } },
    );
  };
  let answer = "";
  let sources: Source[] = [];
  const conversationId = "chat-1";
  const requestId = "request-1";
  await streamAnswer({
    question: "За сколько дней?",
    conversationId,
    requestId,
    csrf: "test-csrf",
    signal: new AbortController().signal,
    onSources: (value) => {
      sources = value;
    },
    onToken: (value) => {
      answer += value;
    },
  });
  assert.deepEqual(body, { question: "За сколько дней?", conversation_id: conversationId, request_id: requestId });
  assert.equal(answer, "Заявление подаётся за 14 дней.");
  assert.equal(sources[0].page, 4);
});

test("an interrupted stream remains an error instead of a completed answer", async (context) => {
  const previousFetch = globalThis.fetch;
  context.after(() => {
    globalThis.fetch = previousFetch;
  });
  globalThis.fetch = async () =>
    new Response('event: token\ndata: {"text":"Частичный ответ"}\n\n', {
      headers: { "Content-Type": "text/event-stream" },
    });
  await assert.rejects(
    streamAnswer({
      question: "Вопрос",
      conversationId: "chat-1",
      requestId: "request-1",
      csrf: "",
      signal: new AbortController().signal,
      onSources: () => {},
      onToken: () => {},
    }),
    /прервалось/,
  );
});

test("conversation API loads server history and sends cookies and CSRF on deletion", async (context) => {
  const previousFetch = globalThis.fetch;
  context.after(() => { globalThis.fetch = previousFetch; });
  const calls: { url: string; options: RequestInit | undefined }[] = [];
  globalThis.fetch = async (url, options) => {
    calls.push({ url: String(url), options });
    if (options?.method === "DELETE") return new Response(null, { status: 204 });
    if (String(url).includes("?limit="))
      return Response.json([{ id: "chat-1", title: "Сохранённый", updatedAt: 123 }]);
    return Response.json({ id: "chat-1", title: "Сохранённый", updatedAt: 123,
      messages: [{ id: "answer-1", role: "assistant", content: "Ответ из БД", sources: [], status: "complete" }] });
  };
  assert.equal((await chatApi.list())[0].title, "Сохранённый");
  assert.equal((await chatApi.get("chat-1")).messages[0].content, "Ответ из БД");
  await chatApi.remove("chat-1", "csrf-token");
  assert.equal(calls.at(-1)?.options?.method, "DELETE");
  assert.equal(calls.at(-1)?.options?.credentials, "include");
  assert.equal(new Headers(calls.at(-1)?.options?.headers).get("X-CSRF-Token"), "csrf-token");
});

test("source links reject executable and relative URLs", () => {
  assert.equal(safeSourceUrl("javascript:alert(1)"), undefined);
  assert.equal(safeSourceUrl("data:text/html,test"), undefined);
  assert.equal(safeSourceUrl("reglament.pdf"), undefined);
  assert.equal(safeSourceUrl("https://www.cft.ru/"), "https://www.cft.ru/");
});
