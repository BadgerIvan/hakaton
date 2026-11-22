import { readFileSync } from 'node:fs';
import { expect, test, type Page } from '@playwright/test';

const adminHtml = readFileSync(new URL('../../services/rag_service/app/static/admin.html', import.meta.url), 'utf8');
const headers = { 'X-Admin-Token': 'admin-test-token' };
const sampleFiles = [
  { source:'shift/go.md', category:'shift', size_bytes:2048, chunks:12, indexed:true, on_disk:true },
  { source:'cft/products.txt', category:'cft', size_bytes:1024, chunks:0, indexed:false, on_disk:true },
];
const sampleLogs = [
  { timestamp:'2026-11-22T10:01:02.000+00:00', service:'backend', level:'ERROR', event:'generation.failed', request_id:'trace-42', status:502, duration_ms:35 },
  { timestamp:'2026-11-22T10:01:00.000+00:00', service:'auth', level:'INFO', event:'http.request', method:'POST', path:'/api/v1/auth/login', status:200, duration_ms:4 },
];

async function prepare(page: Page) {
  let files = [...sampleFiles];
  const requests: { method:string; path:string }[] = [];
  await page.route('**/admin', route => route.fulfill({ contentType:'text/html', body:adminHtml }));
  await page.route('**/api/v1/admin/**', async route => {
    const req = route.request(); const url = new URL(req.url());
    requests.push({method:req.method(), path:url.pathname});
    if (req.headers()['x-admin-token'] !== headers['X-Admin-Token']) return route.fulfill({status:401, json:{detail:'Неверный токен'}});
    if (url.pathname.endsWith('/logs')) {
      let rows = [...sampleLogs];
      if (url.searchParams.get('service')) rows = rows.filter(row => row.service === url.searchParams.get('service'));
      if (url.searchParams.get('level') === 'ERROR') rows = rows.filter(row => row.level === 'ERROR');
      const query = url.searchParams.get('search')?.toLowerCase();
      if (query) rows = rows.filter(row => JSON.stringify(row).toLowerCase().includes(query));
      return route.fulfill({ json:{entries:rows, configured:true, truncated:false, updated_at:new Date().toISOString()} });
    }
    if (url.pathname.endsWith('/reindex')) return route.fulfill({json:{files_indexed:2, total_chunks:15}});
    if (req.method() === 'DELETE') { files = files.filter(file => file.source !== url.searchParams.get('source')); return route.fulfill({json:{deleted:true}}); }
    if (req.method() === 'POST') return route.fulfill({json:{uploaded:[{}],total_chunks_added:3}});
    return route.fulfill({json:files});
  });
  await page.goto('/admin');
  return requests;
}

async function login(page: Page) {
  await page.getByLabel('Токен администратора').fill(headers['X-Admin-Token']);
  await page.getByRole('button', {name:'Войти в панель'}).click();
  await expect(page.locator('#adminContent')).toBeVisible();
}

test('admin sign-in, documents, search and session restore', async ({page}) => {
  await prepare(page);
  await expect(page.locator('#headingActions')).toBeHidden();
  await login(page);
  await expect(page.locator('#statFiles')).toHaveText('2');
  await expect(page.locator('#filesBody tr')).toHaveCount(2);
  await page.getByRole('searchbox', {name:'Поиск документов'}).fill('products');
  await expect(page.locator('#filesBody tr')).toHaveCount(1);
  await expect(page.locator('#filesBody')).toContainText('products.txt');
  await page.reload();
  await expect(page.locator('#adminContent')).toBeVisible();
  await page.getByRole('button', {name:'Выйти',exact:true}).click();
  await expect(page.locator('#authPanel')).toBeVisible();
  expect(await page.evaluate(() => sessionStorage.getItem('rag_admin_token'))).toBeNull();
});

test('invalid token leaves documents hidden', async ({page}) => {
  await prepare(page);
  await page.getByLabel('Токен администратора').fill('invalid');
  await page.getByRole('button', {name:'Войти в панель'}).click();
  await expect(page.locator('#statusBox')).toContainText('Токен не принят');
  await expect(page.locator('#adminContent')).toBeHidden();
});

test('logs filter, expand details and export the visible rows', async ({page}) => {
  await prepare(page); await login(page);
  await page.getByRole('tab', {name:'Логи', exact:true}).click();
  await expect(page.locator('.log-row')).toHaveCount(2);
  await page.getByLabel('Сервис', {exact:true}).selectOption('backend');
  await page.getByLabel('Минимальный уровень').selectOption('ERROR');
  await expect(page.locator('.log-row')).toHaveCount(1);
  await page.locator('.log-row summary').click();
  await expect(page.locator('.log-json')).toContainText('trace-42');
  const downloadPromise = page.waitForEvent('download');
  await page.getByRole('button', {name:'Скачать',exact:true}).click();
  expect((await downloadPromise).suggestedFilename()).toMatch(/partner-agent-logs-.*\.jsonl$/);
  await page.getByRole('searchbox', {name:'Поиск по журналу'}).fill('does-not-exist');
  await expect(page.locator('#logsBody')).toContainText('Событий пока нет');
  await expect(page.locator('#exportLogs')).toBeDisabled();
});

test('delete and reindex require confirmation; upload preserves the admin header', async ({page}) => {
  const requests = await prepare(page); await login(page);
  await page.getByRole('button', {name:'Удалить shift/go.md',exact:true}).click();
  await page.getByRole('button', {name:'Отмена',exact:true}).click();
  expect(requests.filter(req => req.method === 'DELETE')).toHaveLength(0);
  await page.getByRole('button', {name:'Удалить shift/go.md',exact:true}).click();
  await page.getByRole('button', {name:'Удалить',exact:true}).click();
  await expect(page.locator('#statFiles')).toHaveText('1');
  await page.locator('#reindexBtn').click();
  await page.getByRole('dialog').getByRole('button', {name:'Переиндексировать',exact:true}).click();
  await expect(page.locator('#statusBox')).toContainText('Индекс обновлён');
  await page.locator('#fileInput').setInputFiles({name:'new.md', mimeType:'text/markdown', buffer:Buffer.from('# Документ')});
  await expect(page.locator('#statusBox')).toContainText('Загружено документов: 1');
});

test('log rendering treats untrusted text as text', async ({page}) => {
  await prepare(page); await login(page);
  await page.route('**/api/v1/admin/logs?**', route => route.fulfill({json:{configured:true,updated_at:new Date().toISOString(),entries:[{...sampleLogs[0],event:'<img src=x onerror="window.injected=true">'}]}}));
  await page.locator('#tab-logs').click();
  await expect(page.locator('.log-event')).toContainText('<img');
  expect(await page.evaluate(() => (window as any).injected)).toBeUndefined();
  await expect(page.locator('.log-event img')).toHaveCount(0);
});

test('phone layout fits the viewport and both tabs remain usable', async ({page}) => {
  await page.setViewportSize({width:390,height:844});
  await prepare(page); await login(page);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.locator('#tab-logs').click();
  await expect(page.locator('.log-row')).toHaveCount(2);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});
