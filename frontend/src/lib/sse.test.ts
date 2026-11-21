import assert from "node:assert/strict";
import test from "node:test";
import { SSEDecoder, streamAnswer } from "./sse";
import { safeSourceUrl } from "./api";
import { buildHistory } from "./history";
import type { Message, Source } from "../types";

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
  const history = [{ role: "user" as const, content: "Предыдущий вопрос" }];
  await streamAnswer({
    question: "За сколько дней?",
    history,
    csrf: "test-csrf",
    signal: new AbortController().signal,
    onSources: (value) => {
      sources = value;
    },
    onToken: (value) => {
      answer += value;
    },
  });
  assert.deepEqual(body, { question: "За сколько дней?", history });
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
      history: [],
      csrf: "",
      signal: new AbortController().signal,
      onSources: () => {},
      onToken: () => {},
    }),
    /прервалось/,
  );
});

test("failed answer pairs do not leak into subsequent model history", () => {
  const message = (
    role: Message["role"],
    content: string,
    status: Message["status"] = "complete",
  ): Message => ({ id: content, role, content, status, sources: [] });
  assert.deepEqual(
    buildHistory([
      message("user", "Первый"),
      message("assistant", "Верный ответ"),
      message("user", "Второй"),
      message("assistant", "Оборванный текст", "error"),
    ]),
    [
      { role: "user", content: "Первый" },
      { role: "assistant", content: "Верный ответ" },
    ],
  );
});

test("source links reject executable and relative URLs", () => {
  assert.equal(safeSourceUrl("javascript:alert(1)"), undefined);
  assert.equal(safeSourceUrl("data:text/html,test"), undefined);
  assert.equal(safeSourceUrl("reglament.pdf"), undefined);
  assert.equal(safeSourceUrl("https://www.cft.ru/"), "https://www.cft.ru/");
});
