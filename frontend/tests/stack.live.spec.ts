import { expect, test } from "@playwright/test";

test("real registration, RAG answer, reload and logout", async ({ page, request }) => {
  const seed = await request.post("/api/v1/admin/files", {
    headers: { "X-Admin-Token": process.env.TEST_ADMIN_TOKEN || "local-test-admin" },
    multipart: { category: "browser", files: { name: "go.md", mimeType: "text/markdown", buffer: Buffer.from("# Курс Go\nКурс Go длится 12 недель. Обучение онлайн.") } },
  });
  expect(seed.ok()).toBeTruthy();
  await page.goto("/");
  await page.getByRole("button", { name: "Регистрация", exact: true }).click();
  await page.locator("#name").fill("Browser User");
  await page.locator("#email").fill(`browser-${crypto.randomUUID()}@example.com`);
  await page.locator("#password").fill("browser-password-123");
  await page.locator("#confirmation").fill("browser-password-123");
  await page.getByRole("button", { name: "Создать аккаунт", exact: true }).click();
  await page.getByRole("textbox", { name: "Ваш вопрос", exact: true }).fill("Расскажи про Go");
  await page.getByRole("button", { name: "Отправить вопрос" }).click();
  await expect(page.getByLabel("Ответ ассистента")).toContainText("12 недель");
  await page.reload();
  await page.getByRole("navigation", { name: "История диалогов" }).getByRole("button", { name: "Расскажи про Go", exact: true }).click();
  await expect(page.getByLabel("Ответ ассистента")).toContainText("12 недель");
  await page.getByRole("button", { name: "Выйти из аккаунта" }).click();
  await expect(page.getByRole("button", { name: "Войти", exact: true })).toBeVisible();
});
