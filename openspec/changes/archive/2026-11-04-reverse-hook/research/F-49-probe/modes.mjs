// Режимы пробы F-49: когда плагин загружен и когда уходит. serve без запроса, перезапись файла плагина, два сервера, выгрузка места, run --standalone.
import fs from "node:fs";
import path from "node:path";
import { MODEL, TOOLS, emit, makeProject, mark, newTrace, note, readTrace, remember, rememberFromTrace, rest, runStandalone, say, setControl, sleep, startServer, stopServer, waitFor } from "./lib.mjs";

const which = process.argv[2];
const count = (traceDir, at, extra = () => true) => readTrace(traceDir).filter((r) => r.at === at && extra(r)).length;

async function touch(server, directory) {
  const r = await rest(server, "GET", "/api/location", { directory });
  return r.status;
}

async function bootAndReload() {
  const traceDir = newTrace("boot");
  const root = makeProject("c");

  mark(traceDir, "serve из каталога проекта, запросов нет");
  let server = await startServer(traceDir, { cwd: root, label: "serve-cwd-project" });
  await sleep(5000);
  note(traceDir, { serve_cwd_project_no_requests: { setups: count(traceDir, "setup") } });
  emit(root, { op: "list", tag: "serve из каталога, запросов не было" });
  await sleep(2500);
  note(traceDir, { reaction: { commands: count(traceDir, "command") } });

  mark(traceDir, "запрос с каталогом проекта");
  note(traceDir, { touch_status: await touch(server, root) });
  await waitFor(traceDir, (r) => r.at === "setup", "setup после запроса", 30000);
  await sleep(2000);
  const prompt = readTrace(traceDir).filter((r) => r.at === "command").length;
  note(traceDir, { old_line_after_setup: { commands: prompt } });
  emit(root, { op: "list", tag: "строка после setup" });
  await sleep(2500);
  note(traceDir, { reaction_after_touch: { commands: count(traceDir, "command") } });

  mark(traceDir, "перезапись файла плагина при живом сервере");
  const plugin = path.join(root, ".opencode", "plugins", "f49-probe.js");
  const setups = count(traceDir, "setup");
  fs.writeFileSync(plugin, `${fs.readFileSync(plugin, "utf8")}// правка пробы\n`, "utf8");
  await sleep(8000);
  note(traceDir, { plugin_rewrite: { setups_before: setups, setups_after: count(traceDir, "setup"), cleanups: count(traceDir, "cleanup") } });
  emit(root, { op: "list", tag: "после перезаписи плагина" });
  await sleep(2500);
  stopServer(server);
  await sleep(1500);
  note(traceDir, { after_taskkill: { cleanups: count(traceDir, "cleanup") } });

  mark(traceDir, "serve из пустого каталога, GET сессии без заголовка каталога");
  const traceGet = newTrace("boot-get");
  const rootGet = makeProject("d");
  server = await startServer(traceGet, { label: "serve-empty" });
  const made = await rest(server, "POST", "/api/session", { body: { location: { directory: rootGet } } });
  const sid = (made.json?.data ?? made.json)?.id;
  remember(sid);
  note(traceGet, { rest_create: { status: made.status, sessionID: sid, setups: count(traceGet, "setup") } });
  await sleep(2500);
  stopServer(server);
  await sleep(1500);
  server = await startServer(traceGet, { label: "serve-empty-2" });
  const before = count(traceGet, "setup");
  const list = await rest(server, "GET", `/api/session?directory=${encodeURIComponent(rootGet)}&limit=5`);
  await sleep(3000);
  const listed = count(traceGet, "setup");
  const got = await rest(server, "GET", `/api/session/${sid}`);
  await sleep(3000);
  const gotten = count(traceGet, "setup");
  const ctx = await rest(server, "GET", `/api/session/${sid}/context`);
  await sleep(3000);
  note(traceGet, { what_loads_plugin: { before, list_status: list.status, after_list: listed, get_status: got.status, after_get: gotten, context_status: ctx.status, after_context: count(traceGet, "setup") } });
  await touch(server, rootGet);
  await sleep(3000);
  note(traceGet, { after_location_request: { setups: count(traceGet, "setup") } });
  stopServer(server);
  rememberFromTrace(traceDir);
  rememberFromTrace(traceGet);
}

async function twoServers() {
  const traceDir = newTrace("two");
  const root = makeProject("e");
  const one = await startServer(traceDir, { label: "serve-1" });
  const two = await startServer(traceDir, { label: "serve-2" });
  try {
    await touch(one, root);
    await touch(two, root);
    await waitFor(traceDir, (r) => r.at === "setup" && readTrace(traceDir).filter((x) => x.at === "setup").length >= 2, "две загрузки", 30000);
    mark(traceDir, "одна строка, два сервера");
    emit(root, { op: "list", tag: "два сервера" });
    await sleep(3000);
    const rows = readTrace(traceDir).filter((r) => r.at === "command");
    note(traceDir, { two_servers: { reacted: rows.length, pids: [...new Set(rows.map((r) => r.pid))].length } });
  } finally {
    stopServer(one);
    stopServer(two);
    rememberFromTrace(traceDir);
  }
}

/** Короткий срок простоя места из настройки проекта: то же, что 60 минут по умолчанию, но за минуты. */
async function evict(keep) {
  const name = keep ? "evict-keep" : "evict-close";
  const traceDir = newTrace(name);
  const root = makeProject(keep ? "f" : "g", { config: { experimental: { location_idle_timeout: "1 minute" } } });
  setControl(traceDir, keep ? { keepAfterCleanup: true } : {});
  const server = await startServer(traceDir, { label: name });
  try {
    const [providerID, id] = [MODEL.slice(0, MODEL.indexOf("/")), MODEL.slice(MODEL.indexOf("/") + 1)];
    const made = await rest(server, "POST", "/api/session", { body: { location: { directory: root }, model: { providerID, id } } });
    const sid = (made.json?.data ?? made.json)?.id;
    remember(sid);
    note(traceDir, { rest_create: { status: made.status, sessionID: sid, setups: count(traceDir, "setup") } });
    // POST /api/session плагин не загружает (след boot-get): место загружает запрос с каталогом.
    note(traceDir, { touch_status: await touch(server, root) });
    await waitFor(traceDir, (r) => r.at === "setup", "setup", 30000);
    await sleep(1000);
    emit(root, { op: "list", tag: "до выгрузки" });
    await sleep(2000);
    mark(traceDir, `ждём выгрузки места, keep=${keep}`);
    const gone = await waitFor(traceDir, (r) => r.at === "cleanup", "cleanup по простою", 300000);
    note(traceDir, { evicted: !!gone, after_ms: gone ? gone.t - readTrace(traceDir).find((r) => r.at === "setup").t : null });
    await sleep(1500);
    mark(traceDir, "строка в файле после выгрузки");
    emit(root, { op: "list", tag: "после выгрузки" });
    await sleep(3000);
    note(traceDir, { after_evict: { commands: count(traceDir, "command"), setups: count(traceDir, "setup") } });
    if (keep) {
      mark(traceDir, "session.prompt из наблюдателя, пережившего выгрузку");
      const since = Date.now();
      emit(root, { op: "prompt", tag: "после выгрузки, prompt", session: sid, text: "Ответь одним словом: БУК" });
      await waitFor(traceDir, (r) => r.t >= since && r.at === "event" && /session\.execution\.(succeeded|failed|interrupted)/.test(r.type), "ход после выгрузки", 90000);
      await sleep(2000);
      note(traceDir, { after_prompt: { setups: count(traceDir, "setup"), cleanups: count(traceDir, "cleanup") } });
      emit(root, { op: "list", tag: "сколько наблюдателей теперь" });
      await sleep(3000);
      const ctx = await rest(server, "GET", `/api/session/${sid}/context`);
      note(traceDir, { context: (ctx.json?.data ?? []).map((m) => ({ type: m.type, text: m.text ?? m.content?.find?.((c) => c.type === "text")?.text })) });
    } else {
      mark(traceDir, "любой запрос к месту после выгрузки");
      await touch(server, root);
      await sleep(3000);
      note(traceDir, { after_touch: { setups: count(traceDir, "setup") } });
      emit(root, { op: "list", tag: "после нового запроса" });
      await sleep(3000);
      note(traceDir, { reaction: { commands: count(traceDir, "command") } });
    }
  } finally {
    stopServer(server);
    rememberFromTrace(traceDir);
  }
}

async function standalone() {
  const traceDir = newTrace("standalone");
  const root = makeProject("h");
  setControl(traceDir, { delayMs: 10000 });
  mark(traceDir, "run --standalone: строка в файле, пока процесс жив");
  const running = runStandalone(root, "Ответь одним словом: КЕДР", traceDir);
  const started = await waitFor(traceDir, (r) => r.at === "delay.start", "delay.start", 90000);
  if (started) emit(root, { op: "prompt", tag: "run --standalone, пока жив", session: "latest", delivery: "steer", text: "Дополнение: в конец ответа добавь слово ПИНИЯ." });
  const r = await running;
  note(traceDir, { run: "standalone", code: r.code, sessionID: r.id, reply: r.text.slice(0, 200), stderr: r.err.slice(0, 200) });
  await sleep(2000);
  note(traceDir, { after_exit: { setups: count(traceDir, "setup"), cleanups: count(traceDir, "cleanup"), commands: count(traceDir, "command") } });
  mark(traceDir, "строка в файле после выхода run --standalone");
  emit(root, { op: "list", tag: "после выхода" });
  await sleep(3000);
  note(traceDir, { reaction_after_exit: { commands: count(traceDir, "command") } });
  rememberFromTrace(traceDir);
}

/** Файл плагина появился, когда место уже загружено: так бывает, если расширение ставит его при живой службе. */
async function newFile() {
  const traceDir = newTrace("newfile");
  const root = makeProject("i");
  const plugin = path.join(root, ".opencode", "plugins", "f49-probe.js");
  fs.unlinkSync(plugin);
  const server = await startServer(traceDir, { label: "serve-newfile" });
  try {
    note(traceDir, { touch_status: await touch(server, root) });
    await sleep(4000);
    note(traceDir, { before_file: { setups: count(traceDir, "setup") } });
    mark(traceDir, "файл плагина появился при живом сервере");
    fs.copyFileSync(path.join(TOOLS, "plugin", "f49-probe.js"), plugin);
    const found = await waitFor(traceDir, (r) => r.at === "setup", "setup нового файла", 30000);
    note(traceDir, { after_file: { setups: count(traceDir, "setup"), picked_up: !!found } });
    emit(root, { op: "list", tag: "после появления файла" });
    await sleep(2500);
    note(traceDir, { reaction: { commands: count(traceDir, "command") } });
    mark(traceDir, "файл плагина снят при живом сервере");
    fs.unlinkSync(plugin);
    await sleep(5000);
    note(traceDir, { after_unlink: { cleanups: count(traceDir, "cleanup") } });
    emit(root, { op: "list", tag: "после снятия файла" });
    await sleep(2500);
    note(traceDir, { reaction_after_unlink: { commands: count(traceDir, "command") } });
  } finally {
    stopServer(server);
    rememberFromTrace(traceDir);
  }
}

/** Первый запрос TUI при запуске по исходнику: fs.list с каталогом запуска (packages/tui/src/app.tsx). Без TUI, тот же адрес. */
async function tuiFirstRequest() {
  const traceDir = newTrace("fslist");
  const root = makeProject("j");
  const server = await startServer(traceDir, { label: "serve-fslist" });
  try {
    const r = await rest(server, "GET", "/api/fs/list", { directory: root });
    await waitFor(traceDir, (x) => x.at === "setup", "setup после fs.list", 15000);
    note(traceDir, { fs_list: { status: r.status, setups: count(traceDir, "setup") } });
  } finally {
    stopServer(server);
  }
}

/** Без запроса к модели: сколько навыков видит место с флагом и без. Имена в след не идут. */
async function skillCount() {
  const traceDir = newTrace("skills");
  const root = makeProject("k");
  fs.unlinkSync(path.join(root, ".opencode", "plugins", "f49-probe.js"));
  for (const [label, extraEnv] of [["без-флага", { OPENCODE_DISABLE_CLAUDE_CODE: "" }], ["с-флагом", {}]]) {
    const server = await startServer(traceDir, { label, extraEnv });
    try {
      await rest(server, "GET", "/api/location", { directory: root });
      await sleep(4000);
      const r = await rest(server, "GET", "/api/skill", { directory: root });
      const body = r.json;
      const data = Array.isArray(body) ? body : Array.isArray(body?.data) ? body.data : [];
      note(traceDir, { skills: { label, status: r.status, body_keys: body && !Array.isArray(body) ? Object.keys(body) : "массив", count: data.length, from_home_claude: data.filter((s) => JSON.stringify(s).includes(".claude")).length, builtin: data.filter((s) => ["opencode", "report"].includes(s.id)).map((s) => s.id) } });
    } finally {
      stopServer(server);
    }
  }
}

if (which === "skills") await skillCount();
else if (which === "fslist") await tuiFirstRequest();
else if (which === "newfile") await newFile();
else if (which === "boot") await bootAndReload();
else if (which === "two") await twoServers();
else if (which === "evict") {
  await Promise.all([evict(true), evict(false)]);
} else if (which === "standalone") await standalone();
else throw new Error(`нет режима ${which} в ${TOOLS}`);
say("готово", which);
