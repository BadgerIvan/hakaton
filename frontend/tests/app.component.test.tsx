import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, test, vi } from "vitest";
import { App } from "../src/App";
import { AuthProvider } from "../src/auth";
import type { Conversation } from "../src/types";

let signedIn: boolean;
let chats: Map<string, Conversation>;
const session = { user: { id: "test-user", name: "Вова", email: "vova@example.com" }, csrf_token: "csrf-test", expires_at: "2099-01-01" };
const calls: string[] = [];
let activeStream: { reject: (reason: unknown) => void; chat: Conversation; requestId: string } | undefined;
beforeEach(() => {
  signedIn=false; chats=new Map(); calls.length=0; activeStream=undefined;
  vi.stubGlobal("fetch", vi.fn(async (input: string, options?: RequestInit) => {
    const path = new URL(String(input), "http://localhost").pathname;
    const method = options?.method || "GET";
    const body = options?.body ? JSON.parse(String(options.body)) : {};
    calls.push(method+" "+path);
    const json = (value: unknown, status=200) => Response.json(value, { status });
    if (path.endsWith("/auth/me")) return json(signedIn ? session : { detail: "Войдите" }, signedIn ? 200 : 401);
    if (path.endsWith("/auth/login") || path.endsWith("/auth/register")) {
      if (body.password === "wrong-pass") return json({ detail: "Неверная почта или пароль" }, 401);
      signedIn=true; return json(session);
    }
    if (path.endsWith("/auth/logout")) { signedIn=false; return new Response(null, { status:204 }); }
    if (!signedIn) return json({ detail: "Войдите" },401);
    if (method !== "GET") expect(new Headers(options?.headers).get("X-CSRF-Token")).toBe("csrf-test");
    if (path === "/api/v1/conversations") {
      if (method === "GET") return json([...chats.values()].map(({ messages, ...chat })=>chat));
      const chat: Conversation = { id: crypto.randomUUID(), title: body.title, updatedAt: Date.now(), messages: [] };
      chats.set(chat.id,chat); return json(chat,201);
    }
    if (path === "/api/v1/ask/stream") {
      const chat=chats.get(body.conversation_id)!;
      chat.title=body.question;
      const failed=body.question.includes("ошибка");
      const text=failed ? "Частичный ответ" : "Курс Go длится **12 недель**.";
      const sources=[{ doc_id:"doc1", source:"Курс Go", url:"https://education.cft.ru/go", score:.9 }];
      chat.messages.push({ id:crypto.randomUUID(),role:"user",content:body.question,sources:[],status:"complete",request_id:body.request_id });
      chat.messages.push({ id:crypto.randomUUID(),role:"assistant",content:text,sources,status:failed ? "error" : "complete",request_id:body.request_id });
      if (body.question === "Долгий ответ") {
        return await new Promise<Response>((_resolve,reject)=>{
          activeStream={reject,chat,requestId:body.request_id};
          options?.signal?.addEventListener("abort",()=>reject(new DOMException("Aborted","AbortError")),{once:true});
        });
      }
      return new Response(`event: token\ndata: ${JSON.stringify({text})}\n\nevent: sources\ndata: ${JSON.stringify(sources)}\n\n`+(failed ? 'event: error\ndata: {}\n\n' : 'event: done\ndata: {}\n\n'),{headers:{"Content-Type":"text/event-stream"}});
    }
    if (path.endsWith("/cancel")) {
      if (activeStream) activeStream.chat.messages.at(-1)!.status="cancelled";
      return new Response(null,{status:204});
    }
    const id=path.split("/").at(-1)!;
    if (chats.has(id)) {
      if (method === "DELETE") { chats.delete(id); return new Response(null,{status:204}); }
      return json(chats.get(id));
    }
    return json({detail:"Missing"},404);
  }));
});

function mount() { return render(<AuthProvider><App /></AuthProvider>); }
async function login() {
  const user=userEvent.setup();
  await user.type(await screen.findByLabelText("Электронная почта"),"vova@example.com");
  await user.type(screen.getByLabelText("Пароль",{exact:true}),"test-password");
  await user.click(screen.getByRole("button",{name:"Войти"}));
  await screen.findByRole("button",{name:"Новый диалог"});
  return user;
}
async function ask(user: ReturnType<typeof userEvent.setup>, question="Расскажи про Go") {
  await user.type(screen.getByRole("textbox",{name:"Ваш вопрос"}),question);
  await user.click(screen.getByRole("button",{name:"Отправить вопрос"}));
  await waitFor(()=>expect(screen.getByLabelText("Ответ ассистента")).toHaveTextContent("12 недель"));
}

test("registration rejects mismatched confirmation before API call",async()=>{
  mount(); const user=userEvent.setup();
  await user.click(await screen.findByRole("button",{name:"Регистрация"}));
  await user.type(screen.getByLabelText("Ваше имя"),"Вова");
  await user.type(screen.getByLabelText("Электронная почта"),"vova@example.com");
  await user.type(screen.getByLabelText("Пароль",{exact:true}),"test-password");
  await user.type(screen.getByLabelText("Повторите пароль"),"different-password");
  await user.click(screen.getByRole("button",{name:"Создать аккаунт"}));
  expect(screen.getByRole("alert")).toHaveTextContent("Пароли не совпадают");
  expect(calls).not.toContain("POST /api/v1/auth/register");
});

test("login failure is displayed",async()=>{
  mount();const user=userEvent.setup();
  await user.type(await screen.findByLabelText("Электронная почта"),"vova@example.com");
  await user.type(screen.getByLabelText("Пароль",{exact:true}),"wrong-pass");
  await user.click(screen.getByRole("button",{name:"Войти"}));
  expect(await screen.findByRole("alert")).toHaveTextContent("Неверная почта или пароль");
});

test("chat renders Markdown/source URL and restores server history on reopening",async()=>{
  const view=mount();const user=await login();await ask(user);
  const answer=screen.getByLabelText("Ответ ассистента");
  expect(answer.querySelector("strong")).toHaveTextContent("12 недель");
  expect(within(answer).getByRole("link",{name:"Курс Go"})).toHaveAttribute("href","https://education.cft.ru/go");
  view.unmount();mount();
  await user.click(await screen.findByRole("button",{name:"Расскажи про Go"}));
  await waitFor(()=>expect(screen.getByLabelText("Ответ ассистента")).toHaveTextContent("12 недель"));
});

test("new dialog isolates old messages and history can be reopened",async()=>{
  mount();const user=await login();await ask(user);
  await user.click(screen.getByRole("button",{name:"Новый диалог"}));
  expect(screen.queryByLabelText("Ответ ассистента")).not.toBeInTheDocument();
  await user.click(screen.getByRole("button",{name:"Расскажи про Go"}));
  await waitFor(()=>expect(screen.getByLabelText("Ответ ассистента")).toHaveTextContent("12 недель"));
});

test("confirmed deletion removes chat on the server",async()=>{
  mount();const user=await login();await ask(user);vi.spyOn(window,"confirm").mockReturnValue(true);
  await user.click(screen.getByRole("button",{name:"Удалить диалог Расскажи про Go"}));
  await waitFor(()=>expect(chats.size).toBe(0));
  expect(screen.queryByLabelText("Ответ ассистента")).not.toBeInTheDocument();
});

test("logout clears the session while retaining server-side history",async()=>{
  mount();const user=await login();await ask(user);
  await user.click(screen.getByRole("button",{name:"Выйти из аккаунта"}));
  expect(await screen.findByRole("button",{name:"Войти"})).toBeVisible();
  expect(chats.size).toBe(1);expect(signedIn).toBe(false);
});

test("partial stream failures stay failed and offer retry",async()=>{
  mount();const user=await login();
  await user.type(screen.getByRole("textbox",{name:"Ваш вопрос"}),"ошибка");
  await user.click(screen.getByRole("button",{name:"Отправить вопрос"}));
  await screen.findByRole("button",{name:"Повторить запрос"});
  expect(screen.getByLabelText("Ответ ассистента")).toHaveTextContent("Частичный ответ");
});

test("stop aborts the pending stream and sends the server cancellation",async()=>{
  mount();const user=await login();
  await user.type(screen.getByRole("textbox",{name:"Ваш вопрос"}),"Долгий ответ");
  await user.click(screen.getByRole("button",{name:"Отправить вопрос"}));
  await waitFor(()=>expect(activeStream).toBeDefined());
  await user.click(await screen.findByRole("button",{name:"Остановить ответ"}));
  await waitFor(()=>expect(calls.some(c=>c.endsWith("/cancel"))).toBe(true));
  expect(screen.queryByRole("button",{name:"Остановить ответ"})).not.toBeInTheDocument();
});
