// Прогон страницы просмотрщика в настоящем Chrome: чистый профиль, страница из file://, флагов, ослабляющих проверки, нет.
// Использование: node viewer-browser.mjs <chrome> <страница.html> <ширина> <высота> <действие>...
// Действия: panel — включить панель и дождаться рисунка или текста; mode:<режим> — кнопка режима; drag:<dx> — тянуть границу панели;
// reload — открыть страницу снова; choose:<запись>:<буква> — выбрать вариант; word:<запись>:<текст> — написать слово; buttons — экспорт, импорт, копирование;
// tab:<scheme|help> — переключатель панели; step:<шаг> — пункт списка справки; helpnext, helpprev — листание; howto — кнопка «Как готовить intent.md?»;
// clicklink — ссылка на файл внутри варианта; editor:<значение>[:<маска>] — выбор редактора; open:<страница> — другая страница в том же профиле.
// Итог на stdout: JSON с замером страницы, запросами наружу (`http`), запросами, которые заблокировала CSP (`blocked`), нарушениями и ошибками.
import { spawn } from "node:child_process";
import { existsSync, mkdirSync, mkdtempSync, readdirSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { pathToFileURL } from "node:url";
import { removeTree } from "../../installer/scripts/sync-payload.js";

const [chrome, page, width, height, ...actions] = process.argv.slice(2);
const [w, h] = [Number(width), Number(height)];
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const profile = mkdtempSync(join(tmpdir(), "symphysis-viewer-"));
const proc = spawn(chrome, ["--headless=new", "--disable-gpu", "--no-first-run", "--no-default-browser-check",
  "--remote-debugging-port=0", `--user-data-dir=${profile}`, `--window-size=${w},${h}`, "about:blank"], { stdio: "ignore" });

const MEASURE = `(() => {
  const panel = document.getElementById('schemePanel');
  const shown = panel && !panel.classList.contains('hidden');
  const rect = shown ? panel.getBoundingClientRect() : null;
  const main = document.querySelector('.layout main');
  const mainRect = main && main.offsetParent ? main.getBoundingClientRect() : null;
  const view = document.querySelector('main.view:not(.hidden)');
  const svg = shown ? panel.querySelector('svg') : null;
  const scroller = document.getElementById('schemeBody');
  let topVisible = null, labelPx = null, total = 0;
  if (svg) {
    const nodes = [...svg.querySelectorAll('g.node')], box = (n) => n.getBoundingClientRect(), port = scroller.getBoundingClientRect();
    total = nodes.length;
    if (total) {
      const top = nodes.reduce((a, b) => box(b).top < box(a).top ? b : a), t = box(top);
      topVisible = t.left >= port.left && t.right <= port.right && t.top >= port.top && t.bottom <= port.bottom;
    }
    const label = svg.querySelector('.nodeLabel');
    if (label) labelPx = parseFloat(getComputedStyle(label).fontSize) * (svg.getBoundingClientRect().width / svg.viewBox.baseVal.width);
  }
  const pre = shown ? scroller.querySelector('pre') : null;
  const body = document.getElementById('helpBody');
  const field = (sel, name) => { const n = body && body.querySelector(sel); return n ? n[name] : null; };
  const help = body && { shown: !!shown && !body.classList.contains('hidden'), schemeShown: !!shown && !scroller.classList.contains('hidden'),
    opened: field('[data-page]', 'dataset') ? field('[data-page]', 'dataset').page : null,
    current: [...body.querySelectorAll('.helpstep.current')].map((n) => n.dataset.step),
    steps: [...body.querySelectorAll('.helpstep')].map((n) => n.dataset.step),
    prevDisabled: field('#helpPrev', 'disabled'), nextDisabled: field('#helpNext', 'disabled'),
    time: field('#helpTime', 'textContent'), rebuild: field('#helpRebuild', 'textContent'), versions: field('#helpVersions', 'textContent'),
    error: field('#helpError', 'textContent'), text: body.textContent, foreign: body.querySelectorAll('img, script, iframe, svg').length };
  return { help, stats: document.getElementById('stats').textContent, panelLabel: document.getElementById('btnScheme').textContent, modeButtons: document.querySelectorAll('#modes button').length,
    tabs: [...document.querySelectorAll('#panelTabs button')].map((n) => n.textContent), activeTab: (document.querySelector('#panelTabs button.active') || {}).textContent || null,
    viewport: innerWidth, headerBottom: document.querySelector('header').getBoundingClientRect().bottom, shown, state: panel ? panel.dataset.state || null : null,
    panel: rect && { left: rect.left, top: rect.top, width: rect.width, height: rect.height, bottom: rect.bottom },
    cards: mainRect && { left: mainRect.left, right: mainRect.right, top: mainRect.top, width: mainRect.width },
    view: view ? view.getBoundingClientRect().width : null,
    hasSvg: !!svg, total, topVisible, labelPx,
    messages: shown ? [...scroller.querySelectorAll('.note')].map((n) => n.textContent) : [],
    text: pre ? pre.textContent : null,
    out: document.getElementById('out').value,
    warnings: [...document.querySelectorAll('[data-antipode-warning]')].map((n) => n.dataset.antipodeWarning),
    wordNeeded: [...document.querySelectorAll('[data-word-needed]:not(.hidden)')].map((n) => n.dataset.wordNeeded),
    recommendations: [...document.querySelectorAll('div.rec')].map((n) => n.textContent),
    chosen: [...document.querySelectorAll('input[type=radio]:checked')].map((r) => r.name + '.' + r.value),
    editor: (document.getElementById('editorPick') || {}).value || null, editorMask: (document.getElementById('editorMask') || {}).value ?? null,
    links: [...document.querySelectorAll('a.filelink')].map((a) => ({ href: a.href, text: a.textContent })),
    codes: [...document.querySelectorAll('.card code')].map((c) => c.textContent),
    attack: { groups: [...document.querySelectorAll('#viewAttack .attack-rows h2 code')].map((n) => n.textContent),
      active: (document.querySelector('#lensFilter button.active') || {}).dataset?.lens || null },
    mode: (document.querySelector('#modes button.active') || {}).textContent || null };
})()`;

// Chrome создаёт файл порта раньше, чем отпускает его: под нагрузкой чтение падает с EBUSY, поэтому читается, пока порт не прочитается.
async function devToolsPort() {
  let failure;
  for (let i = 0; i < 400; i++) {
    try {
      const port = readFileSync(join(profile, "DevToolsActivePort"), "utf8").split("\n")[0].trim();
      if (port) return port;
    } catch (e) { failure = e; }
    await sleep(25);
  }
  throw new Error(`Chrome не отдал порт отладки за 10 с: ${failure}`);
}

async function main() {
  const port = await devToolsPort();
  const targets = await (await fetch(`http://127.0.0.1:${port}/json`)).json();
  const ws = new WebSocket(targets.find((t) => t.type === "page").webSocketDebuggerUrl);
  await new Promise((r) => (ws.onopen = r));
  let id = 0;
  const pending = new Map();
  const sent = new Map(), blocked = [], files = [], errors = [];
  ws.onmessage = (ev) => {
    const m = JSON.parse(ev.data);
    if (m.id && pending.has(m.id)) { pending.get(m.id)(m.result ?? { error: m.error }); pending.delete(m.id); return; }
    if (m.method === "Network.requestWillBeSent") {
      const url = m.params.request.url;
      if (/^https?:/.test(url)) sent.set(m.params.requestId, url);
      else if (/^file:/.test(url)) files.push(url);
    }
    if (m.method === "Network.loadingFailed" && m.params.blockedReason === "csp" && sent.has(m.params.requestId)) {
      blocked.push(sent.get(m.params.requestId));
      sent.delete(m.params.requestId);
    }
    if (m.method === "Runtime.exceptionThrown") errors.push(m.params.exceptionDetails.exception?.description?.split("\n")[0] ?? m.params.exceptionDetails.text);
  };
  const send = (method, params = {}) => new Promise((r) => { const i = ++id; pending.set(i, r); ws.send(JSON.stringify({ id: i, method, params })); });
  const evaluate = async (expression) => (await send("Runtime.evaluate", { expression, returnByValue: true, awaitPromise: true })).result?.value;
  for (const domain of ["Page", "Runtime", "Network", "DOM"]) await send(`${domain}.enable`);
  await send("Emulation.setDeviceMetricsOverride", { width: w, height: h, deviceScaleFactor: 1, mobile: false });
  await send("Page.addScriptToEvaluateOnNewDocument", { source: "window.__csp = []; document.addEventListener('securitypolicyviolation', (e) => window.__csp.push(e.violatedDirective + ' ' + e.blockedURI));" });
  const url = pathToFileURL(page).href;
  const loaded = async () => { for (let i = 0; i < 400; i++) { if (await evaluate("document.readyState === 'complete' && !!document.getElementById('out')")) return; await sleep(25); } throw new Error("страница не загрузилась"); };
  const settled = async () => { for (let i = 0; i < 1200; i++) { if (await evaluate("(() => { const p = document.getElementById('schemePanel'); return !p || p.classList.contains('hidden') || !!p.dataset.state || p.dataset.view === 'help'; })()")) return; await sleep(25); } throw new Error("панель не дорисовала"); };
  const mouse = async (type, x, y) => send("Input.dispatchMouseEvent", { type, x, y, button: "left", clickCount: 1 });
  const center = (sel) => evaluate(`(() => { const b = document.querySelector(${JSON.stringify(sel)}).getBoundingClientRect(); return [b.left + b.width / 2, b.top + b.height / 2]; })()`);
  const click = async (sel) => { const [x, y] = await center(sel); await mouse("mousePressed", x, y); await mouse("mouseReleased", x, y); };

  await send("Page.navigate", { url });
  await loaded();
  await settled();
  const buttons = {};
  for (const action of actions) {
    const [name, ...args] = action.split(":");
    if (name === "panel") { await click("#btnScheme"); await settled(); }
    if (name === "tab") { await click(`#panelTabs button[data-panel="${args[0]}"]`); await settled(); }
    const inHelp = { helpnext: "#helpNext", helpprev: "#helpPrev", howto: "#helpHowTo", step: `#helpBody .helpstep[data-step="${args[0]}"]` }[name];
    if (inHelp) {
      await evaluate(`document.querySelector(${JSON.stringify(inHelp)}).scrollIntoView({ block: 'center' })`);
      await click(inHelp);
      await sleep(50);
    }
    if (name === "mode") { await click(`#modes button[data-mode="${args[0]}"]`); await settled(); }
    if (name === "lens") { await click(`#lensFilter button[data-lens="${args[0]}"]`); await sleep(50); }
    if (name === "reload") { await send("Page.navigate", { url }); await loaded(); await settled(); }
    if (name === "choose") {
      await evaluate(`document.querySelector('input[name="${args[0]}"][value="${args[1]}"]').scrollIntoView({ block: 'center' })`);
      await click(`input[name="${args[0]}"][value="${args[1]}"]`);
      await sleep(50);
    }
    if (name === "open") { await send("Page.navigate", { url: pathToFileURL(args.join(":")).href }); await loaded(); await settled(); }
    if (name === "editor") {
      await evaluate(`(() => { const s = document.getElementById('editorPick'); s.value = ${JSON.stringify(args[0])}; s.dispatchEvent(new Event('change', { bubbles: true })); const m = ${JSON.stringify(args.slice(1).join(":"))}; if (m) { const i = document.getElementById('editorMask'); i.value = m; i.dispatchEvent(new Event('change', { bubbles: true })); } })()`);
      await sleep(50);
    }
    if (name === "clicklink") {
      await evaluate(`document.querySelector('label.opt a.filelink').scrollIntoView({ block: 'center' })`);
      await click("label.opt a.filelink");
      await sleep(100);
    }
    if (name === "word") {
      await evaluate(`(() => { const t = document.querySelector('textarea[data-word="${args[0]}"]'); t.value = ${JSON.stringify(args[1])}; t.dispatchEvent(new Event('input', { bubbles: true })); })()`);
      await sleep(50);
    }
    if (name === "drag") {
      const [x, y] = await center("#schemehandle");
      await mouse("mousePressed", x, y);
      await send("Input.dispatchMouseEvent", { type: "mouseMoved", x: x + Number(args[0]), y, button: "left" });
      await mouse("mouseReleased", x + Number(args[0]), y);
      await sleep(50);
    }
    if (name === "buttons") {
      const dl = join(profile, "dl");
      mkdirSync(dl, { recursive: true });
      await send("Browser.setDownloadBehavior", { behavior: "allow", downloadPath: dl });
      await click("#btnExport");
      let exported = null;
      for (let i = 0; i < 200 && !exported; i++) { await sleep(25); exported = readdirSync(dl).find((f) => f.endsWith(".json")); }
      buttons.exported = !!exported;
      if (exported) {
        const state = JSON.parse(readFileSync(join(dl, exported), "utf8"));
        state.notes = "проба импорта";
        const file = join(dl, "import.json");
        writeFileSync(file, JSON.stringify(state));
        const doc = await send("DOM.getDocument");
        const node = await send("DOM.querySelector", { nodeId: doc.root.nodeId, selector: "#fileImport" });
        await send("DOM.setFileInputFiles", { files: [file], nodeId: node.nodeId });
        await sleep(300);
        buttons.imported = await evaluate("document.getElementById('notes').value");
      }
      await click("#btnCopy");
      await sleep(150);
      buttons.copied = await evaluate("document.getElementById('copied').textContent");
    }
  }
  const measure = await evaluate(MEASURE);
  const csp = await evaluate("window.__csp");
  await sleep(100);
  ws.close();
  return { ...measure, http: [...sent.values()], blocked, files, errors, csp, buttons };
}

// Процессы Chrome переживают kill главного и держат файлы профиля, поэтому снятие повторяется, пока они не выйдут.
async function removeProfile() {
  const end = Date.now() + 20000;
  let failure;
  while (existsSync(profile) && Date.now() < end) {
    try { removeTree(profile); } catch (e) { failure = e; await sleep(100); }
  }
  if (!existsSync(profile)) return true;
  process.stderr.write(`профиль не снят за 20 с: ${profile}: ${failure}\n`);
  return false;
}

let code = 0;
try {
  process.stdout.write(JSON.stringify(await main()));
} catch (e) {
  process.stderr.write(String(e && e.stack || e));
  code = 1;
} finally {
  proc.kill();
  if (!(await removeProfile())) code = 1;
}
process.exit(code);
