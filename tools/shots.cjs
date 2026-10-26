// Снимки для странички и проверка экрана «Папки с проектами» пакета для других.
// Настоящие HTML/CSS/JS окна (../aihub-terminal/ui), подменён только транспорт
// Tauri; проекты вымышленные — личных папок на снимках нет.
//
//   $env:NODE_PATH = Join-Path $env:TEMP 'aihub-ui-test\node_modules'
//   node tools/shots.cjs
const { chromium } = require('playwright');
const path = require('node:path');
const assert = require('node:assert/strict');
const { pathToFileURL } = require('node:url');

const UI = path.resolve(__dirname, '../../aihub-terminal/ui/index.html');
const OUT = path.resolve(__dirname, '../docs');

(async () => {
  const browser = await chromium.launch({ channel: 'msedge', headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 860 }, deviceScaleFactor: 1 });
  const errors = []; page.on('pageerror', (e) => errors.push(e.message));
  try {
    await page.addInitScript(() => {
      localStorage.clear();
      window.sent = []; window.channels = {};
      window.emit = (id, event) => window.channels[id].onmessage({ kind: 'line', line: JSON.stringify(event) });
      // Состояние «скина»: корни и проекты в них
      const DEMO = {
        'D:\\Projects': ['landing-page', 'telegram-bot', 'game-jam-2026', 'notes-app'],
        'D:\\Work': ['crm-export', 'report-builder'],
      };
      window.state = { roots: [], extra: [] };
      const label = (p) => p.split('\\').pop().toLowerCase();
      const items = () => {
        const out = [];
        for (const r of state.roots) for (const n of DEMO[r] || []) out.push({ name: n, path: r + '\\' + n, tag: label(r), temp: false, fixed: false, oneoff: false });
        if (state.roots.length) out.push({ name: 'idea-sketch', path: 'C:\\Users\\me\\AIHUB\\временные проекты\\idea-sketch', tag: 'врем.', temp: true, fixed: true, oneoff: false, born: 1 });
        out.push({ name: 'разовая сессия', path: 'C:\\Users\\me', tag: 'разово', temp: true, fixed: true, oneoff: true });
        return out;
      };
      const now = Date.now() / 1000;
      window.__TAURI__ = { webview: { getCurrentWebview: () => ({ onDragDropEvent: async () => () => {} }) }, core: { Channel: class {}, invoke: async (method, p = {}) => {
        if (method === 'aihub_found') return true;
        if (method === 'read_status') return [];
        if (method === 'sys_status') return { proxy: null, battery: 82, charging: false, live_rain: false };
        if (method === 'pick_folder') return window.nextFolder;
        if (method === 'agent_start') { window.channels[p.id] = p.onEvent; p.onEvent.onmessage({ kind: 'ready' }); return; }
        if (method === 'agent_send') { window.sent.push(JSON.parse(p.line)); return; }
        if (method === 'aihub') {
          const [cmd, arg] = p.args;
          if (cmd === 'projects') return {
            items: items(), running: 0, plans: false, roots_editable: true,
            kinds: state.roots.map((r) => ({ tag: label(r), label: label(r).toUpperCase(), root: r })),
            roots: state.roots.map((r) => ({ path: r, label: label(r), kind: 'root' })),
            temp_root: 'C:\\Users\\me\\AIHUB\\временные проекты', temp_name: '2026-10-26',
          };
          if (cmd === 'add_root') { if (state.roots.includes(arg)) throw 'Эта папка уже в списке'; state.roots.push(arg); return { ok: true }; }
          if (cmd === 'remove_root') { state.roots = state.roots.filter((r) => r !== arg); return { ok: true }; }
          if (cmd === 'card') return {
            desc: 'Лендинг для студии: одна страница, форма заявки, тёмная тема. Сборка — Vite, деплой на GitHub Pages.',
            source: 'README.md',
            sessions: [
              { provider: 'claude', id: 's1', when: now - 3600 * 3, said: 'добавь форму заявки и проверь мобильную вёрстку', human: 'сегодня в 14:12' },
              { provider: 'codex', id: 's2', when: now - 86400, said: 'почини сборку после обновления Vite', human: 'вчера в 19:40' },
            ],
            weight: 41000,
            preview: [
              { role: 'user', text: 'добавь форму заявки и проверь мобильную вёрстку' },
              { role: 'assistant', text: 'Форма добавлена в секцию «Контакты»: имя, телефон, сообщение, отправка через fetch. На 375 px кнопка переносилась — поправил отступы.' },
            ],
            can_delete: true, temp: false, fixed: false, oneoff: false,
          };
          return {};
        }
        return null;
      } } };
    });
    await page.goto(pathToFileURL(UI).href);

    // ── первый запуск: папок нет → сразу «Папки с проектами» ──
    await page.locator('#btn-new-empty').click();
    await page.waitForSelector('#pcard h3');
    assert.equal(await page.locator('#pcard h3').textContent(), 'Папки с проектами', 'first run opens roots form');
    await page.screenshot({ path: path.join(OUT, 'shot-first-run.png') });

    // ── добавить две папки ──
    await page.evaluate(() => { window.nextFolder = 'D:\\Projects'; });
    await page.getByRole('button', { name: '＋ Папка, где лежат проекты…' }).click();
    await page.waitForFunction(() => document.querySelector('#plist').textContent.includes('landing-page'));
    await page.evaluate(() => { window.nextFolder = 'D:\\Work'; });
    await page.getByRole('button', { name: '＋ Папка, где лежат проекты…' }).click();
    await page.waitForFunction(() => document.querySelector('#plist').textContent.includes('crm-export'));
    assert.equal(await page.locator('#pcard .pc-sess').count(), 2, 'two roots listed');
    // повтор той же папки — ошибка, а не дубль
    await page.getByRole('button', { name: '＋ Папка, где лежат проекты…' }).click();
    await page.waitForSelector('.pc-notice.err');
    // убрать и вернуть
    await page.getByRole('button', { name: 'Убрать из списка' }).nth(1).click();
    await page.waitForFunction(() => !document.querySelector('#plist').textContent.includes('crm-export'));
    await page.evaluate(() => { window.nextFolder = 'D:\\Work'; });
    await page.getByRole('button', { name: '＋ Папка, где лежат проекты…' }).click();
    await page.waitForFunction(() => document.querySelector('#plist').textContent.includes('crm-export'));

    // ── карточка проекта ──
    await page.locator('.prow', { hasText: 'landing-page' }).click();
    await page.waitForSelector('.pc-term');
    await page.screenshot({ path: path.join(OUT, 'shot-projects.png') });

    // ── окно-чат с перепиской ──
    await page.locator('#projects-close').click();
    await page.evaluate(async () => {
      const t = createTab({ id: 'demo', name: 'landing-page', cwd: 'D:\\Projects\\landing-page', kind: 'chat' }, false);
      hideCover(t); setView('single'); await t.chat.start(null);
      emit('demo', { type: 'system', subtype: 'init', session_id: 'demo', model: 'claude-sonnet-5', cwd: 'D:\\Projects\\landing-page' });
    });
    await page.locator('.tile.active .chat-input textarea').fill('Добавь форму заявки в «Контакты» и проверь мобильную вёрстку');
    await page.locator('.tile.active .chat-input textarea').press('Enter');
    await page.evaluate(async () => {
      const e = (x) => emit('demo', x);
      e({ type: 'assistant', message: { id: 'm1', role: 'assistant', content: [{ type: 'text', text: 'Посмотрю, как устроена секция контактов.' }, { type: 'tool_use', id: 'tu1', name: 'Read', input: { file_path: 'D:\\Projects\\landing-page\\src\\Contacts.jsx' } }] } });
      e({ type: 'user', message: { role: 'user', content: [{ type: 'tool_result', tool_use_id: 'tu1', content: 'export default function Contacts() {\n  return <section id="contacts">…</section>\n}' }] } });
      e({ type: 'assistant', message: { id: 'm2', role: 'assistant', content: [{ type: 'tool_use', id: 'tu2', name: 'Edit', input: { file_path: 'D:\\Projects\\landing-page\\src\\Contacts.jsx', old_string: '  return <section id="contacts">…</section>', new_string: '  return (\n    <section id="contacts">\n      <LeadForm onSubmit={sendLead} />\n    </section>\n  )' } }] } });
      e({ type: 'user', message: { role: 'user', content: [{ type: 'tool_result', tool_use_id: 'tu2', content: 'The file has been updated.' }] } });
      e({ type: 'assistant', message: { id: 'm3', role: 'assistant', content: [{ type: 'tool_use', id: 'tu3', name: 'Bash', input: { command: 'npm run build', description: 'Собрать сайт' } }] } });
      e({ type: 'user', message: { role: 'user', content: [{ type: 'tool_result', tool_use_id: 'tu3', content: 'vite v6.2.0 building for production...\n✓ 42 modules transformed.\n✓ built in 1.84s' }] } });
      e({ type: 'assistant', message: { id: 'm4', role: 'assistant', content: [{ type: 'text', text: 'Готово:\n\n- форма **имя / телефон / сообщение** в секции «Контакты», отправка через `fetch`;\n- на 375 px кнопка переносилась — поправил отступы;\n- сборка проходит.\n\nПроверить можно командой `npm run dev`.' }] } });
      e({ type: 'result', subtype: 'success', is_error: false, duration_ms: 48000, num_turns: 4, total_cost_usd: 0.08, usage: { input_tokens: 1200, output_tokens: 900 } });
      setLiveLimits({ five_hour: { used_percentage: 23, resets_at: Date.now() / 1000 + 8000 }, seven_day: { used_percentage: 41, resets_at: Date.now() / 1000 + 300000 } });
    });
    await page.waitForTimeout(600);
    await page.screenshot({ path: path.join(OUT, 'shot-chat.png') });

    assert.deepEqual(errors, [], 'page errors');
    console.log('OK: снимки в docs/, экран папок работает');
  } finally {
    await browser.close();
  }
})().catch((e) => { console.error(e); process.exit(1); });
