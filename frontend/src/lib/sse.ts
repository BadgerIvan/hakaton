import type { HistoryMessage, Source } from "../types";
import { agentBase, ApiError, responseError } from "./api";

export interface ServerEvent {
  event: string;
  data: string;
}

// Handles UTF-8 after decoding, multiline data and CRLF split between network chunks.
export class SSEDecoder {
  private buffer = "";
  private eventName = "";
  private data: string[] = [];

  feed(chunk: string): ServerEvent[] {
    this.buffer += chunk;
    const events: ServerEvent[] = [];
    let separator: RegExpExecArray | null;
    while ((separator = /\r\n|\r|\n/.exec(this.buffer))) {
      if (separator[0] === "\r" && separator.index === this.buffer.length - 1)
        break;
      const line = this.buffer.slice(0, separator.index);
      this.buffer = this.buffer.slice(separator.index + separator[0].length);
      if (line === "") {
        if (this.data.length > 0)
          events.push({
            event: this.eventName || "message",
            data: this.data.join("\n"),
          });
        this.eventName = "";
        this.data = [];
        continue;
      }
      if (line.startsWith(":")) continue;
      const colon = line.indexOf(":");
      const field = colon === -1 ? line : line.slice(0, colon);
      const value = colon === -1 ? "" : line.slice(colon + 1).replace(/^ /, "");
      if (field === "event") this.eventName = value;
      if (field === "data") this.data.push(value);
    }
    return events;
  }
}

function readSources(value: unknown): Source[] {
  if (!Array.isArray(value)) throw new Error("Invalid sources event");
  return value.filter(
    (source): source is Source =>
      source !== null &&
      typeof source === "object" &&
      typeof source.doc_id === "string" &&
      typeof source.source === "string",
  );
}

export async function streamAnswer(options: {
  question: string;
  history: HistoryMessage[];
  csrf: string;
  signal: AbortSignal;
  onSources: (sources: Source[]) => void;
  onToken: (text: string) => void;
}): Promise<void> {
  const controller = new AbortController();
  const cancel = () => controller.abort();
  let timedOut = false;
  const timeout = setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, 120000);
  options.signal.addEventListener("abort", cancel, { once: true });
  if (options.signal.aborted) controller.abort();
  let reader: ReadableStreamDefaultReader<Uint8Array> | undefined;
  try {
    const response = await fetch(`${agentBase}/api/v1/ask/stream`, {
      method: "POST",
      credentials: "include",
      headers: {
        "Content-Type": "application/json",
        Accept: "text/event-stream",
        "X-Requested-With": "PartnerAgent",
        "X-CSRF-Token": options.csrf,
      },
      body: JSON.stringify({
        question: options.question,
        history: options.history,
      }),
      signal: controller.signal,
    });
    if (!response.ok) throw await responseError(response);
    if (
      !response.body ||
      !response.headers.get("content-type")?.includes("text/event-stream")
    ) {
      throw new ApiError("Сервис вернул неподдерживаемый формат ответа.", 502);
    }
    reader = response.body.getReader();
    const utf8 = new TextDecoder();
    const parser = new SSEDecoder();
    while (true) {
      const { value, done } = await reader.read();
      const events = parser.feed(utf8.decode(value, { stream: !done }));
      for (const event of events) {
        if (event.event === "done") return;
        if (!["sources", "token", "error"].includes(event.event)) continue;
        const data: unknown = JSON.parse(event.data);
        if (event.event === "sources") options.onSources(readSources(data));
        if (event.event === "token") {
          if (
            !data ||
            typeof data !== "object" ||
            !("text" in data) ||
            typeof data.text !== "string"
          )
            throw new Error("Invalid token event");
          options.onToken(data.text);
        }
        if (event.event === "error")
          throw new ApiError(
            "Не удалось завершить ответ. Повторите запрос.",
            502,
          );
      }
      if (done)
        throw new ApiError(
          "Соединение прервалось до завершения ответа. Повторите запрос.",
          502,
        );
    }
  } catch (error) {
    if (timedOut)
      throw new ApiError(
        "Ответ занял слишком много времени. Попробуйте ещё раз.",
        504,
      );
    throw error;
  } finally {
    clearTimeout(timeout);
    options.signal.removeEventListener("abort", cancel);
    await reader?.cancel().catch(() => undefined);
  }
}
