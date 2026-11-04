// Основной проход пробы F-49: ход в простаивающей сессии, steer/queue/служебное, занятая сессия, ошибки, откуда брать номер сессии.
import path from "node:path";
import { ANSWER, makeProject, mark, newTrace, note, readTrace, rememberFromTrace, remember, rest, runAttached, say, setControl, sleep, startServer, stopServer, waitFor, emit } from "./lib.mjs";

const traceDir = newTrace("main");
const A = makeProject("a");
const B = makeProject("b");
const server = await startServer(traceDir);

async function quiet(sid, ms = 180000) {
  const from = Date.now();
  let calm = 0;
  while (Date.now() - from < ms) {
    const active = await rest(server, "GET", "/api/session/active");
    const inbox = await rest(server, "GET", `/api/session/${sid}/inbox`);
    const busy = JSON.stringify(active.json?.data ?? "").includes(sid);
    const pending = inbox.json?.data?.length ?? 0;
    calm = !busy && pending === 0 ? calm + 1 : 0;
    if (calm >= 4) return true;
    await sleep(500);
  }
  note(traceDir, { timeout: `quiet ${sid}` });
  say(`ТАЙМАУТ тишины ${sid}`);
  return false;
}

function compact(m) {
  const row = { id: m.id, type: m.type };
  for (const key of ["text", "description", "metadata", "agent"]) if (m[key] !== undefined) row[key] = typeof m[key] === "string" ? m[key].slice(0, 300) : m[key];
  if (m.content) row.content = m.content.map((c) => (c.type === "text" ? { type: "text", text: c.text.slice(0, 300) } : c.type === "tool" ? { type: "tool", name: c.name, status: c.state?.status, input: c.state?.input } : { type: c.type }));
  return row;
}

async function snapshot(tag, sid) {
  const ctx = await rest(server, "GET", `/api/session/${sid}/context`);
  note(traceDir, { snapshot: tag, sessionID: sid, status: ctx.status, messages: (ctx.json?.data ?? []).map(compact) });
}

async function wake(tag, cmd, sid, { wait = true } = {}) {
  mark(traceDir, tag);
  emit(A, { tag, ...cmd });
  if (!wait) return;
  await sleep(1500);
  await quiet(sid);
  await snapshot(tag, sid);
}

/** Занятая сессия: задержка в хуке context держит первый шаг хода, пока приходит вторая просьба. */
async function busy(tag, base, second, sid) {
  mark(traceDir, tag);
  setControl(traceDir, { delayMs: 12000 });
  const since = Date.now();
  emit(A, { tag: `${tag}-base`, ...base });
  const started = await waitFor(traceDir, (r) => r.at === "delay.start" && r.t >= since, `${tag}: delay.start`, 60000);
  if (started) {
    const active = await rest(server, "GET", "/api/session/active");
    note(traceDir, { busy_while_delay: tag, active_has_session: JSON.stringify(active.json?.data ?? "").includes(sid) });
    emit(A, { tag: `${tag}-second`, ...second });
  }
  await sleep(3000);
  await quiet(sid);
  await snapshot(tag, sid);
  setControl(traceDir, {});
}

try {
  // До первого запроса плагин не загружен.
  await sleep(3000);
  emit(A, { op: "list", tag: "до первого запроса" });
  await sleep(2500);
  note(traceDir, { before_first_request: { setups: readTrace(traceDir).filter((r) => r.at === "setup").length, commands: readTrace(traceDir).filter((r) => r.at === "command").length } });

  mark(traceDir, "первая сессия: opencode run --server, ответ, run вышел");
  const first = await runAttached(server, A, "Ответь одним словом: ГОТОВО");
  note(traceDir, { run: "первая", code: first.code, known: !!first.id, reply: first.text.slice(0, 200) });
  const S1 = first.id;
  if (!S1) throw new Error(`нет сессии: ${first.err.slice(0, 300)}`);
  await quiet(S1);
  await sleep(1500);
  const raw = await rest(server, "GET", "/api/session/active");
  note(traceDir, { active_shape: raw.json, sessionID: S1 });
  const got = await rest(server, "GET", `/api/session/${S1}`);
  note(traceDir, { session_get: { status: got.status, time: got.json?.time ?? got.json?.data?.time, model: got.json?.model ?? got.json?.data?.model } });

  // Ход без реплики человека: простаивает, run вышел, в сервере никто не подключён.
  await wake("ход по строке в файле, файл ответа", { op: "prompt", session: "latest", metadata: { source: "f49-wake" }, text: `Человек нажал «Внести» в журнале решений. Открой файл ${ANSWER} и ответь одной строкой, которая начинается со слова МАРКЕР. Больше ничего.` }, S1);

  await wake("простаивает, queue", { op: "prompt", session: S1, delivery: "queue", metadata: { source: "f49-wake", instr: "Служебная метка: КАЛИНА-6161" }, text: "Ответь одним словом: ЧЕРЁМУХА" }, S1);
  await wake("простаивает, steer", { op: "prompt", session: S1, delivery: "steer", metadata: { source: "f49-wake" }, text: "Ответь одним словом: ЯБЛОНЯ" }, S1);
  await wake("простаивает, служебное synthetic", { op: "synthetic", session: S1, description: "проба: служебное сообщение", metadata: { source: "f49-wake" }, text: "Служебное сообщение: ответь одним словом: ВЯЗ" }, S1);

  mark(traceDir, "простаивает, resume:false");
  emit(A, { op: "prompt", tag: "resume-false", session: S1, resume: false, text: "Ответь одним словом: ИВА" });
  await sleep(5000);
  const inbox = await rest(server, "GET", `/api/session/${S1}/inbox`);
  const act = await rest(server, "GET", "/api/session/active");
  note(traceDir, { resume_false: { inbox: (inbox.json?.data ?? []).map((i) => ({ type: i.type, delivery: i.delivery, text: i.payload?.text })), active_has_session: JSON.stringify(act.json?.data ?? "").includes(S1) } });
  await wake("после resume:false следующий запрос", { op: "prompt", session: S1, text: "Ответь одним словом: ДУБ" }, S1);

  const read = `Открой файл ${ANSWER} инструментом read и ответь одной строкой, которая начинается со слова МАРКЕР.`;
  await busy("занята, steer", { op: "prompt", session: S1, text: read }, { op: "prompt", session: S1, delivery: "steer", text: "Дополнение: в конец ответа добавь слово КЛЁН." }, S1);
  await busy("занята, queue", { op: "prompt", session: S1, text: read }, { op: "prompt", session: S1, delivery: "queue", text: "Следующая просьба: ответь одним словом: ЯСЕНЬ." }, S1);
  await busy("занята, служебное", { op: "prompt", session: S1, text: read }, { op: "synthetic", session: S1, description: "проба: служебное", text: "Служебное дополнение: в конец ответа добавь слово ТОПОЛЬ." }, S1);

  // Ошибки вызова: до модели не доходят.
  mark(traceDir, "ошибки вызова");
  emit(A, { op: "prompt", tag: "нет такой сессии", session: "ses_00000000000000000000000000", text: "x" });
  emit(A, { op: "prompt", tag: "не номер", session: "не-номер", text: "x" });
  emit(A, { op: "prompt", tag: "не тот delivery", session: S1, delivery: "now", resume: false, text: "x" });
  await sleep(3000);

  // Откуда брать номер сессии.
  emit(A, { op: "list", tag: "L0 одна сессия" });
  await sleep(1500);
  mark(traceDir, "L1 новая сессия");
  const second = await runAttached(server, A, "Ответь одним словом: ПИХТА");
  const S2 = second.id;
  note(traceDir, { run: "L1", code: second.code, sessionID: S2, reply: second.text.slice(0, 100) });
  await quiet(S2);
  emit(A, { op: "list", tag: "L1 после новой" });
  await sleep(1500);

  mark(traceDir, "L2 возобновление старой: run --session");
  const resumed = await runAttached(server, A, "Ответь одним словом: ГРАБ", ["--session", S1]);
  note(traceDir, { run: "L2", code: resumed.code, same_session: resumed.id === S1, reply: resumed.text.slice(0, 100) });
  await quiet(S1);
  emit(A, { op: "list", tag: "L2 после возобновления" });
  await sleep(1500);

  mark(traceDir, "L3 просмотр старой без реплики");
  const seen = await rest(server, "GET", `/api/session/${S2}`);
  const idleAt = (seen.json?.data ?? seen.json)?.time?.idle;
  const view = await rest(server, "POST", `/api/session/${S2}/view`, { body: { idle: idleAt } });
  note(traceDir, { view: { idle_known: idleAt !== undefined, status: view.status } });
  await sleep(1500);
  emit(A, { op: "list", tag: "L3 после просмотра" });
  await sleep(1500);

  mark(traceDir, "L4 пустая новая сессия без реплики (REST)");
  const created = await rest(server, "POST", "/api/session", { body: { location: { directory: A } } });
  const S3 = (created.json?.data ?? created.json)?.id;
  remember(S3);
  note(traceDir, { rest_create: { status: created.status, sessionID: S3 } });
  await sleep(1500);
  emit(A, { op: "list", tag: "L4 после пустой" });
  await sleep(1500);

  mark(traceDir, "L5 сессия другого проекта на том же сервере");
  const other = await runAttached(server, B, "Ответь одним словом: БУК");
  note(traceDir, { run: "L5", code: other.code, sessionID: other.id, reply: other.text.slice(0, 100) });
  await quiet(other.id);
  emit(A, { op: "list", tag: "L5 из A" });
  await sleep(1500);

  mark(traceDir, "L6 сессия из подкаталога проекта");
  const sub = await runAttached(server, path.join(A, "sub"), "Ответь одним словом: ЛИПА");
  note(traceDir, { run: "L6", code: sub.code, sessionID: sub.id, reply: sub.text.slice(0, 100) });
  await quiet(sub.id);
  emit(A, { op: "list", tag: "L6 строка в файле A после сессии из sub" });
  await sleep(2500);

  const direct = await rest(server, "GET", `/api/session?directory=${encodeURIComponent(A)}&parentID=null&limit=10&order=desc`);
  note(traceDir, { rest_list: { status: direct.status, ids: (direct.json?.data ?? []).map((s) => s.id) } });
} catch (e) {
  note(traceDir, { failed: String(e.stack ?? e) });
  say("СБОЙ", e);
} finally {
  rememberFromTrace(traceDir);
  stopServer(server);
}
say("готово");
