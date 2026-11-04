// Чистит следы пробы F-49: убирает шум, сокращает контекст, заменяет временные пути метками. Вход и выход — аргументы.
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const WORK = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const [, , traceRoot, outDir] = process.argv;

const forms = (value) => [value, value.replaceAll("\\", "/"), encodeURI(value.replaceAll("\\", "/"))];
const marks = [
  [path.join(WORK, "проекты с пробелом"), "<проект>"],
  [WORK, "<tmp>"],
  [os.tmpdir(), "<tmp>"],
  [os.homedir(), "<home>"],
];
export function clean(text) {
  let out = String(text);
  for (const [value, mark] of marks) for (const form of forms(value)) out = out.replaceAll(form, mark);
  return out;
}
const deep = (v) => {
  if (typeof v === "string") return clean(v);
  if (Array.isArray(v)) return v.map(deep);
  if (v && typeof v === "object") return Object.fromEntries(Object.entries(v).map(([k, x]) => [k, deep(x)]));
  return v;
};

const NOISE = /^(session\.(text|reasoning|tool\.input)\.|session\.step\.streamed|session\.renamed|project\.updated|worktree\.resolved|(integration|provider|model|vcs\.branch|agent|command|skill|websearch|reference|plugin)\.updated)/;
const short = (s, n = 200) => (s.length > n ? `${s.slice(0, n)}…` : s);

for (const name of fs.readdirSync(traceRoot)) {
  const file = path.join(traceRoot, name, "trace.jsonl");
  if (!fs.existsSync(file) || name === "smoke") continue;
  const rows = fs.readFileSync(file, "utf8").split("\n").filter(Boolean).map((l) => JSON.parse(l));
  const t0 = rows[0]?.t ?? 0;
  let firstSetup = true;
  const out = [];
  for (const raw of rows) {
    const r = { t_ms: raw.t - t0, ...raw };
    delete r.t;
    if (r.at === "watch-fired" || r.at === "file-new-bytes") continue;
    if (r.at === "event" && NOISE.test(r.type)) continue;
    if (r.at === "event" && r.event_location === undefined) delete r.event_location;
    if (r.at === "setup") {
      if (!firstSetup) delete r.ctx_keys;
      firstSetup = false;
    }
    if (r.at === "hook.context") {
      r.count = r.messages.length;
      r.messages = r.messages.slice(-3).map((m) => ({ role: m.role, text: short(m.text) }));
      delete r.tools;
    }
    if (r.snapshot) {
      r.count = r.messages.length;
      r.messages = r.messages.slice(-7).map((m) => ({ ...m, text: m.text === undefined ? undefined : short(m.text), content: m.content?.map((c) => (c.text ? { ...c, text: short(c.text, 120) } : c)) }));
    }
    if (r.at === "admitted" && r.res?.payload?.text) r.res = { id: r.res.id, type: r.res.type, delivery: r.res.delivery, payload_keys: Object.keys(r.res.payload) };
    out.push(JSON.stringify(deep(r)));
  }
  const target = path.join(outDir, `trace-${name}.jsonl`);
  fs.writeFileSync(target, `${out.join("\n")}\n`, "utf8");
  console.log(path.basename(target), out.length);
}
