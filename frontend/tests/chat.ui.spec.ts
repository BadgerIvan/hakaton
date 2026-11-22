import { expect, test, type Page } from "@playwright/test";

type Chat = { id: string; title: string; updatedAt: number; messages: any[] };
async function fakeApi(page: Page) {
  let signedIn = false;
  const chats = new Map<string, Chat>();
  const session = { user: { id: "test-user", name: "Вова", email: "vova@example.com" }, csrf_token: "test-csrf", expires_at: "2099-01-01" };
  await page.route("**/api/v1/**", async route => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    const method = request.method();
    const body = request.postDataJSON();
    const json = (data: unknown, status = 200) => route.fulfill({ status, json: data });
    if (path.endsWith("/auth/me")) return json(signedIn ? session : { detail: "Войдите" }, signedIn ? 200 : 401);
    if (path.endsWith("/auth/login") || path.endsWith("/auth/register")) {
      if (body.password === "wrong-pass") return json({ detail: "Неверная почта или пароль" }, 401);
      signedIn = true; return json(session, path.endsWith("register") ? 201 : 200);
    }
    if (path.endsWith("/auth/logout")) { signedIn = false; return route.fulfill({ status: 204 }); }
    if (!signedIn) return json({ detail: "Войдите" }, 401);
    if (method !== "GET") {
      expect(request.headers()["x-csrf-token"]).toBe("test-csrf");
      expect(request.headers()["x-requested-with"]).toBe("PartnerAgent");
    }
    if (path === "/api/v1/conversations") {
      if (method === "GET") return json([...chats.values()].map(({ messages, ...chat }) => chat));
      const chat = { id: crypto.randomUUID(), title: body.title, updatedAt: Date.now(), messages: [] };
      chats.set(chat.id, chat); return json(chat, 201);
    }
    if (path === "/api/v1/ask/stream") {
      const chat = chats.get(body.conversation_id)!;
      chat.title = body.question;
      const sources = [{ doc_id: "doc1", source: "Курс Go", url: "https://education.cft.ru/go", score: .9 }];
      const failed = body.question.includes("ошибка");
      const text = failed ? "Часть ответа" : "Курс Go длится **12 недель**.";
      chat.messages.push({ id: crypto.randomUUID(), role: "user", content: body.question, sources: [], status: "complete", request_id: body.request_id });
      chat.messages.push({ id: crypto.randomUUID(), role: "assistant", content: text, sources, status: failed ? "error" : "complete", error: failed ? "Не удалось завершить ответ" : undefined, request_id: body.request_id });
      return route.fulfill({ contentType: "text/event-stream", body:
        `event: token\ndata: ${JSON.stringify({ text })}\n\nevent: sources\ndata: ${JSON.stringify(sources)}\n\n` +
        (failed ? 'event: error\ndata: {"detail":"Не удалось завершить ответ"}\n\n' : 'event: done\ndata: {}\n\n') });
    }
    const id = path.split("/").at(-1)!;
    if (chats.has(id)) {
      if (method === "DELETE") { chats.delete(id); return route.fulfill({ status: 204 }); }
      return json(chats.get(id));
    }
    return json({ detail: "Not found" }, 404);
  });
  return chats;
}

async function login(page: Page) {
  await page.goto("/");
  await page.getByLabel("Электронная почта").fill("vova@example.com");
  await page.locator("#password").fill("test-password");
  await page.getByRole("button", { name: "Войти", exact: true }).click();
  await expect(page.getByRole("button", { name: "Новый диалог" })).toBeVisible();
}
async function ask(page: Page, question = "Расскажи про Go") {
  await page.getByRole("textbox", { name: "Ваш вопрос", exact: true }).fill(question);
  await page.getByRole("button", { name: "Отправить вопрос" }).click();
  await expect(page.getByLabel("Ответ ассистента").last()).toContainText("12 недель");
}

test.beforeEach(async ({ page }) => { await fakeApi(page); });

test("registration checks confirmation before making a request", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Регистрация", exact: true }).click();
  await page.locator("#name").fill("Вова");
  await page.locator("#email").fill("vova@example.com");
  await page.locator("#password").fill("test-password");
  await page.locator("#confirmation").fill("different-pass");
  await page.getByRole("button", { name: "Создать аккаунт", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("Пароли не совпадают");
});

test("invalid login displays the API error", async ({ page }) => {
  await page.goto("/");
  await page.locator("#email").fill("vova@example.com");
  await page.locator("#password").fill("wrong-pass");
  await page.getByRole("button", { name: "Войти", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("Неверная почта или пароль");
});

test("chat renders Markdown, source links and restores server history after reload", async ({ page }) => {
  await login(page); await ask(page);
  const answer = page.getByLabel("Ответ ассистента");
  await expect(answer.locator("strong")).toHaveText("12 недель");
  await expect(answer.getByRole("link", { name: "Курс Go" })).toHaveAttribute("href", "https://education.cft.ru/go");
  await page.reload();
  await page.getByRole("navigation", { name: "История диалогов" }).getByRole("button", { name: "Расскажи про Go", exact: true }).click();
  await expect(page.getByLabel("Ответ ассистента")).toContainText("12 недель");
});

test("new dialog has no old messages; opening history restores them", async ({ page }) => {
  await login(page); await ask(page);
  await page.getByRole("button", { name: "Новый диалог" }).click();
  await expect(page.getByLabel("Ответ ассистента")).toHaveCount(0);
  await page.getByRole("navigation", { name: "История диалогов" }).getByRole("button", { name: "Расскажи про Go", exact: true }).click();
  await expect(page.getByLabel("Ответ ассистента")).toContainText("12 недель");
});

test("deleting a dialog removes it from the server list", async ({ page }) => {
  await login(page); await ask(page);
  page.once("dialog", dialog => dialog.accept());
  await page.getByRole("button", { name: "Удалить диалог Расскажи про Go", exact: true }).click();
  await expect(page.getByLabel("Ответ ассистента")).toHaveCount(0);
  await page.reload();
  await expect(page.getByRole("navigation", { name: "История диалогов" }).getByRole("button")).toHaveCount(0);
});

test("logout revokes the visible session but login restores saved chats", async ({ page }) => {
  await login(page); await ask(page);
  await page.getByRole("button", { name: "Выйти из аккаунта" }).click();
  await expect(page.getByRole("button", { name: "Войти", exact: true })).toBeVisible();
  await login(page);
  await page.getByRole("navigation", { name: "История диалогов" }).getByRole("button", { name: "Расскажи про Go", exact: true }).click();
  await expect(page.getByLabel("Ответ ассистента")).toContainText("12 недель");
});

test("an interrupted answer stays visibly failed and offers retry", async ({ page }) => {
  await login(page);
  await page.getByRole("textbox", { name: "Ваш вопрос", exact: true }).fill("ошибка");
  await page.getByRole("button", { name: "Отправить вопрос" }).click();
  await expect(page.getByLabel("Ответ ассистента")).toContainText("Часть ответа");
  await expect(page.getByRole("button", { name: "Повторить запрос" })).toBeVisible();
});
