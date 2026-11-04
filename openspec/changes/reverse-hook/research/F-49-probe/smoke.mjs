// Первый проход: сторож, что уйдёт модели, сервер и запрос CLI. Если сторож сработает, запрос до модели не дойдёт.
import path from "node:path";
import fs from "node:fs";
import { idle, makeProject, mark, newTrace, readTrace, rememberFromTrace, rest, runAttached, say, startServer, stopServer, WORK } from "./lib.mjs";

const traceDir = newTrace("smoke");
const root = makeProject("a");
say("файлы проекта:", fs.readdirSync(root).join(" "));
const server = await startServer(traceDir);
try {
  mark(traceDir, "первый запрос");
  const r = await runAttached(server, root, "Ответь одним словом: ГОТОВО");
  say("код", r.code, "сессия", r.id, "ответ", JSON.stringify(r.text.slice(0, 200)));
  say("stderr", r.err.slice(0, 400));
  if (r.id) await idle(server, r.id);
  const rows = readTrace(traceDir);
  for (const row of rows) if (["setup", "guard.block", "hook.context", "hook.model.request", "command-error"].includes(row.at)) say(JSON.stringify(row).slice(0, 700));
  const ctx = r.id ? await rest(server, "GET", `/api/session/${r.id}/context`) : null;
  say("context", ctx?.status, JSON.stringify(ctx?.json?.data?.map((m) => ({ type: m.type, text: m.text ?? m.content?.[0]?.text }))).slice(0, 500));
} finally {
  rememberFromTrace(traceDir);
  stopServer(server);
}
say("след:", path.relative(WORK, traceDir));
