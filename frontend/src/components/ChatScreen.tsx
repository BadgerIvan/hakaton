import { useCallback, useEffect, useRef, useState } from "react";
import type { FormEvent, KeyboardEvent } from "react";
import {
  Building2,
  Check,
  Code2,
  Compass,
  Copy,
  FileText,
  GraduationCap,
  Link,
  LoaderCircle,
  LogOut,
  Menu,
  MessageSquare,
  Plus,
  RefreshCw,
  Send,
  Square,
  Trash2,
  X,
} from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { useAuth } from "../auth";
import type { AuthSession, Conversation, Message, Source } from "../types";
import { ApiError, errorMessage, safeSourceUrl } from "../lib/api";
import { buildHistory, loadConversations, storageKey } from "../lib/history";
import { streamAnswer } from "../lib/sse";

const suggestions = [
  {
    icon: Building2,
    title: "О компании",
    question: "Чем занимается ЦФТ и какие продукты разрабатывает?",
  },
  {
    icon: Code2,
    title: "Технологии",
    question: "Какие языки и технологии используют в ЦФТ?",
  },
  {
    icon: GraduationCap,
    title: "Обучение в ШИФТ",
    question: "Что такое ШИФТ и кому подойдёт обучение?",
  },
  {
    icon: Compass,
    title: "Мой следующий шаг",
    question:
      "Хочу развиваться в IT. Помоги выбрать подходящее направление в ШИФТ.",
  },
];

function SourceList({ sources }: { sources: Source[] }) {
  if (!sources.length) return null;
  return (
    <div className="message-sources">
      <span className="sources-label">Источники</span>
      <div className="source-list">
        {sources.map((source, index) => {
          const url = safeSourceUrl(source.url) || safeSourceUrl(source.source);
          const label = `${source.source}${source.page ? ` · стр. ${source.page}` : ""}`;
          return url ? (
            <a
              className="source-chip"
              key={`${source.doc_id}:${index}`}
              href={url}
              target="_blank"
              rel="noopener noreferrer"
              title={label}
            >
              <Link size={14} />
              <span>{label}</span>
            </a>
          ) : (
            <span
              className="source-chip"
              key={`${source.doc_id}:${index}`}
              title={label}
            >
              <FileText size={14} />
              <span>{label}</span>
            </span>
          );
        })}
      </div>
    </div>
  );
}

function Answer({
  message,
  retry,
  last,
}: {
  message: Message;
  retry: () => void;
  last: boolean;
}) {
  const [copied, setCopied] = useState(false);
  const timeout = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  useEffect(() => () => clearTimeout(timeout.current), []);
  async function copy() {
    try {
      await navigator.clipboard.writeText(message.content);
      setCopied(true);
      clearTimeout(timeout.current);
      timeout.current = setTimeout(() => setCopied(false), 1800);
    } catch {
      setCopied(false);
    }
  }
  return (
    <article className="assistant-message" aria-label="Ответ ассистента">
      <div className="assistant-avatar" aria-hidden="true">
        <MessageSquare size={19} />
      </div>
      <div className="assistant-body">
        <span className="assistant-name">Partner Agent</span>
        {!message.content && message.status === "streaming" ? (
          <div className="thinking" role="status">
            <span />
            <span />
            <span />
            <span className="sr-only">Готовим ответ</span>
          </div>
        ) : (
          <div className="markdown">
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={{
                a: ({ href, children }) => {
                  const safe = safeSourceUrl(href);
                  return safe ? (
                    <a href={safe} target="_blank" rel="noopener noreferrer">
                      {children}
                    </a>
                  ) : (
                    <span>{children}</span>
                  );
                },
                img: ({ alt }) => <span>{alt}</span>,
              }}
            >
              {message.content}
            </ReactMarkdown>
          </div>
        )}
        <SourceList sources={message.sources} />
        {message.status === "error" && (
          <p className="message-error" role="alert">
            {message.error}
          </p>
        )}
        {message.status === "cancelled" && (
          <p className="message-note">Ответ остановлен</p>
        )}
        {message.status !== "streaming" && (
          <div className="answer-actions">
            {message.content && (
              <button
                className="text-action"
                type="button"
                onClick={() => void copy()}
                aria-label={copied ? "Ответ скопирован" : "Скопировать ответ"}
              >
                {copied ? <Check size={15} /> : <Copy size={15} />}
                {copied ? "Скопировано" : "Копировать"}
              </button>
            )}
            {last && ["error", "cancelled"].includes(message.status) && (
              <button className="text-action" type="button" onClick={retry}>
                <RefreshCw size={15} />
                Повторить запрос
              </button>
            )}
          </div>
        )}
      </div>
    </article>
  );
}

export function ChatScreen({ session }: { session: AuthSession }) {
  const auth = useAuth();
  const [chats, setChats] = useState<Conversation[]>(() =>
    loadConversations(session.user.id),
  );
  const [currentId, setCurrentId] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const [mobileOpen, setMobileOpen] = useState(false);
  const [streaming, setStreaming] = useState(false);
  const [loggingOut, setLoggingOut] = useState(false);
  const [notice, setNotice] = useState("");
  const active = useRef<{
    controller: AbortController;
    messageId: string;
    chatId: string;
  } | null>(null);
  const textarea = useRef<HTMLTextAreaElement>(null);
  const scrollArea = useRef<HTMLDivElement>(null);
  const autoScroll = useRef(true);
  const current = chats.find((chat) => chat.id === currentId);
  const messages = current?.messages || [];

  useEffect(() => {
    try {
      sessionStorage.setItem(
        storageKey(session.user.id),
        JSON.stringify(chats),
      );
    } catch {
      setNotice(
        "Память браузера заполнена. История этого разговора может не сохраниться после обновления страницы.",
      );
    }
  }, [chats, session.user.id]);

  useEffect(() => () => active.current?.controller.abort(), []);
  useEffect(() => {
    if (autoScroll.current && scrollArea.current)
      scrollArea.current.scrollTop = scrollArea.current.scrollHeight;
  }, [messages]);
  useEffect(() => {
    if (textarea.current) {
      textarea.current.style.height = "auto";
      textarea.current.style.height = `${Math.min(textarea.current.scrollHeight, 150)}px`;
    }
  }, [draft]);
  useEffect(() => {
    const close = (event: globalThis.KeyboardEvent) => {
      if (event.key === "Escape") setMobileOpen(false);
    };
    window.addEventListener("keydown", close);
    return () => window.removeEventListener("keydown", close);
  }, []);

  const updateMessage = useCallback(
    (
      chatId: string,
      messageId: string,
      update: (message: Message) => Message,
    ) => {
      setChats((previous) =>
        previous.map((chat) =>
          chat.id === chatId
            ? {
                ...chat,
                messages: chat.messages.map((message) =>
                  message.id === messageId ? update(message) : message,
                ),
              }
            : chat,
        ),
      );
    },
    [],
  );

  function stop() {
    active.current?.controller.abort();
    active.current = null;
    setStreaming(false);
  }

  function newChat() {
    stop();
    setCurrentId(null);
    setDraft("");
    setMobileOpen(false);
    autoScroll.current = true;
    textarea.current?.focus();
  }

  function openChat(id: string) {
    stop();
    setCurrentId(id);
    setDraft("");
    setMobileOpen(false);
    autoScroll.current = true;
  }

  function deleteChat(chat: Conversation) {
    if (!window.confirm(`Удалить диалог «${chat.title}»?`)) return;
    if (active.current?.chatId === chat.id) stop();
    setChats((previous) => previous.filter((item) => item.id !== chat.id));
    if (currentId === chat.id) setCurrentId(null);
  }

  async function send(question: string, retry = false) {
    question = question.trim();
    if (!question || active.current) return;
    const chatId = currentId || crypto.randomUUID();
    const previousMessages = retry ? messages.slice(0, -2) : messages;
    const userMessage: Message = {
      id: crypto.randomUUID(),
      role: "user",
      content: question,
      sources: [],
      status: "complete",
    };
    const assistantMessage: Message = {
      id: crypto.randomUUID(),
      role: "assistant",
      content: "",
      sources: [],
      status: "streaming",
    };
    const next: Conversation = {
      id: chatId,
      title: current?.title || question.slice(0, 62),
      updatedAt: Date.now(),
      messages: [...previousMessages, userMessage, assistantMessage],
    };
    setChats((previous) => [
      next,
      ...previous.filter((chat) => chat.id !== chatId),
    ]);
    setCurrentId(chatId);
    setDraft("");
    setNotice("");
    autoScroll.current = true;
    const request = {
      controller: new AbortController(),
      messageId: assistantMessage.id,
      chatId,
    };
    active.current = request;
    setStreaming(true);
    let content = "";
    try {
      await streamAnswer({
        question,
        history: buildHistory(previousMessages),
        csrf: session.csrf_token,
        signal: request.controller.signal,
        onSources: (sources) =>
          updateMessage(chatId, assistantMessage.id, (message) => ({
            ...message,
            sources,
          })),
        onToken: (text) => {
          content += text;
          updateMessage(chatId, assistantMessage.id, (message) => ({
            ...message,
            content: message.content + text,
          }));
        },
      });
      if (!content.trim())
        throw new ApiError(
          "Агент завершил запрос без текста ответа. Попробуйте ещё раз.",
          502,
        );
      updateMessage(chatId, assistantMessage.id, (message) => ({
        ...message,
        status: "complete",
      }));
    } catch (error) {
      updateMessage(chatId, assistantMessage.id, (message) => ({
        ...message,
        status: request.controller.signal.aborted ? "cancelled" : "error",
        error: errorMessage(error),
      }));
      if (error instanceof ApiError && error.status === 401)
        void auth.restore();
    } finally {
      if (active.current === request) {
        active.current = null;
        setStreaming(false);
        textarea.current?.focus();
      }
    }
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    void send(draft);
  }
  function keyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (
      event.key === "Enter" &&
      !event.shiftKey &&
      !event.nativeEvent.isComposing
    ) {
      event.preventDefault();
      void send(draft);
    }
  }

  async function logout() {
    stop();
    setLoggingOut(true);
    try {
      await auth.logout();
      sessionStorage.removeItem(storageKey(session.user.id));
    } catch (error) {
      setNotice(errorMessage(error));
    } finally {
      setLoggingOut(false);
    }
  }

  return (
    <div className="chat-layout">
      {mobileOpen && (
        <button
          className="sidebar-backdrop"
          type="button"
          aria-label="Закрыть меню"
          onClick={() => setMobileOpen(false)}
        />
      )}
      <aside
        className={`sidebar ${mobileOpen ? "is-open" : ""}`}
        aria-label="Диалоги"
      >
        <div className="sidebar-brand">
          <img src="/cft.svg" alt="ЦФТ" />
          <img src="/shift.svg" alt="ШИФТ" />
          <button
            className="icon-button mobile-close"
            type="button"
            onClick={() => setMobileOpen(false)}
            aria-label="Закрыть меню"
          >
            <X size={20} />
          </button>
        </div>
        <div className="sidebar-product">
          Partner Agent<span>Информация о ЦФТ и ШИФТ</span>
        </div>
        <button className="new-chat-button" type="button" onClick={newChat}>
          <Plus size={20} />
          Новый диалог
        </button>
        <div className="history-heading">Ваши диалоги</div>
        <nav className="chat-history" aria-label="История диалогов">
          {chats.length === 0 && (
            <p className="history-empty">Здесь появятся ваши разговоры</p>
          )}
          {chats.map((chat) => (
            <div
              className={`history-item ${chat.id === currentId ? "active" : ""}`}
              key={chat.id}
            >
              <button
                className="history-link"
                type="button"
                onClick={() => openChat(chat.id)}
                title={chat.title}
                aria-current={chat.id === currentId ? "page" : undefined}
              >
                <MessageSquare size={16} />
                <span>{chat.title}</span>
              </button>
              <button
                className="history-delete"
                type="button"
                onClick={() => deleteChat(chat)}
                aria-label={`Удалить диалог ${chat.title}`}
              >
                <Trash2 size={15} />
              </button>
            </div>
          ))}
        </nav>
        <div className="user-panel">
          <div className="user-avatar">
            {session.user.name.slice(0, 1).toUpperCase()}
          </div>
          <div className="user-info">
            <strong>{session.user.name}</strong>
            <span title={session.user.email}>{session.user.email}</span>
          </div>
          <button
            className="icon-button logout-button"
            type="button"
            disabled={loggingOut}
            onClick={() => void logout()}
            aria-label="Выйти из аккаунта"
            title="Выйти"
          >
            {loggingOut ? (
              <LoaderCircle size={19} className="spin" />
            ) : (
              <LogOut size={19} />
            )}
          </button>
        </div>
      </aside>

      <main className="chat-main">
        <header className="chat-header">
          <div className="chat-header-title">
            <button
              className="icon-button menu-button"
              type="button"
              onClick={() => setMobileOpen(true)}
              aria-label="Открыть меню"
              aria-expanded={mobileOpen}
            >
              <Menu size={23} />
            </button>
            <span>Ассистент ЦФТ и ШИФТ</span>
          </div>
          <span className="header-caption">Ответы с источниками</span>
        </header>
        {notice && (
          <div className="notice" role="alert">
            <span>{notice}</span>
            <button
              className="icon-button"
              type="button"
              onClick={() => setNotice("")}
              aria-label="Закрыть сообщение"
            >
              <X size={17} />
            </button>
          </div>
        )}
        <div
          className="conversation-scroll"
          ref={scrollArea}
          onScroll={() => {
            const element = scrollArea.current;
            if (element)
              autoScroll.current =
                element.scrollHeight -
                  element.scrollTop -
                  element.clientHeight <
                160;
          }}
        >
          {messages.length === 0 ? (
            <section className="welcome">
              <div className="welcome-symbol" aria-hidden="true">
                <MessageSquare size={34} strokeWidth={1.6} />
              </div>
              <h1>Что хотите узнать?</h1>
              <p className="welcome-description">
                О продуктах ЦФТ, технологиях или вашем
                <br className="desktop-break" /> следующем шаге вместе с ШИФТ.
              </p>
              <div className="suggestions">
                {suggestions.map(({ icon: Icon, title, question }) => (
                  <button
                    className="suggestion"
                    type="button"
                    key={title}
                    onClick={() => {
                      setDraft(question);
                      textarea.current?.focus();
                    }}
                  >
                    <Icon size={22} strokeWidth={1.7} />
                    <strong>{title}</strong>
                    <span>{question}</span>
                  </button>
                ))}
              </div>
            </section>
          ) : (
            <div className="messages">
              {messages.map((message, index) =>
                message.role === "user" ? (
                  <article
                    className="user-message"
                    key={message.id}
                    aria-label="Ваш вопрос"
                  >
                    <div>{message.content}</div>
                  </article>
                ) : (
                  <Answer
                    message={message}
                    key={message.id}
                    last={index === messages.length - 1}
                    retry={() => {
                      const question = messages[index - 1];
                      if (question) void send(question.content, true);
                    }}
                  />
                ),
              )}
            </div>
          )}
        </div>
        <div className="composer-area">
          <form className="composer" onSubmit={submit}>
            <textarea
              ref={textarea}
              aria-label="Ваш вопрос"
              placeholder="Спросите о ЦФТ или ШИФТ…"
              value={draft}
              rows={1}
              maxLength={4000}
              onChange={(event) => setDraft(event.target.value)}
              onKeyDown={keyDown}
            />
            <div className="composer-controls">
              <span className="composer-hint">
                Shift + Enter для новой строки
              </span>
              {streaming ? (
                <button
                  className="send-button is-stop"
                  type="button"
                  onClick={stop}
                  aria-label="Остановить ответ"
                >
                  <Square size={16} fill="currentColor" />
                </button>
              ) : (
                <button
                  className="send-button"
                  type="submit"
                  disabled={!draft.trim()}
                  aria-label="Отправить вопрос"
                >
                  <Send size={19} />
                </button>
              )}
            </div>
          </form>
          <p className="composer-disclaimer">
            Проверяйте важные факты и условия по источникам в ответе.
          </p>
        </div>
      </main>
    </div>
  );
}
