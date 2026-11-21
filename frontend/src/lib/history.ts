import type { Conversation, HistoryMessage, Message } from "../types";

export const storageKey = (userId: string) => `partner-agent:chats:${userId}`;

export function loadConversations(userId: string): Conversation[] {
  try {
    const value: unknown = JSON.parse(
      sessionStorage.getItem(storageKey(userId)) || "[]",
    );
    if (!Array.isArray(value)) return [];
    return value
      .filter(
        (chat): chat is Conversation =>
          chat &&
          typeof chat.id === "string" &&
          typeof chat.title === "string" &&
          typeof chat.updatedAt === "number" &&
          Array.isArray(chat.messages),
      )
      .map((chat) => ({
        ...chat,
        messages: chat.messages
          .filter(isMessage)
          .map((message) =>
            message.status === "streaming"
              ? { ...message, status: "cancelled" as const }
              : message,
          ),
      }));
  } catch {
    return [];
  }
}

function isMessage(value: unknown): value is Message {
  if (!value || typeof value !== "object") return false;
  const candidate = value as Partial<Message>;
  return (
    typeof candidate.id === "string" &&
    ["user", "assistant"].includes(candidate.role || "") &&
    typeof candidate.content === "string" &&
    Array.isArray(candidate.sources) &&
    ["complete", "streaming", "error", "cancelled"].includes(
      candidate.status || "",
    )
  );
}

// Failed and interrupted answers must not enter the next model request as facts.
export function buildHistory(messages: Message[]): HistoryMessage[] {
  const result: HistoryMessage[] = [];
  for (let index = 0; index < messages.length - 1; index += 1) {
    const question = messages[index];
    const answer = messages[index + 1];
    if (
      question.role === "user" &&
      answer.role === "assistant" &&
      answer.status === "complete"
    ) {
      result.push(
        { role: "user", content: question.content },
        { role: "assistant", content: answer.content },
      );
      index += 1;
    }
  }
  return result;
}
