// Общая часть пробы F-49: проект, сервер, запрос CLI, REST, след, учёт сессий.
// Запускается только копия во временном каталоге: <tmp>/tools/*.mjs, plugin/ рядом. Рабочий каталог проб — родитель этого файла, из дерева запуск отказан ниже.
import crypto from "node:crypto";
import { spawn, spawnSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

export const MODEL = "ollama-cloud/deepseek-v4.1-flash";
export const TOOLS = path.dirname(fileURLToPath(import.meta.url));
export const WORK = path.dirname(TOOLS);
if (/openspec[\\/]/.test(WORK)) throw new Error("проба запускается только из копии во временном каталоге");
export const ANSWER = "openspec/changes/demo/answers/2026-11-04.md";
export const MARKER = "МАРКЕР-ОТВЕТА: ОЛЬХА-7141";
const SESSIONS = path.join(WORK, "sessions.txt");
const PASSWORD = crypto.randomBytes(24).toString("base64url");

function which(names) {
  for (const dir of (process.env.PATH ?? "").split(path.delimiter).filter(Boolean)) {
    for (const name of names) {
      const file = path.join(dir, name);
      if (fs.existsSync(file)) return file;
    }
  }
  return null;
}

function findOpencode() {
  const shim = which(["opencode.cmd"]);
  const exe = shim && /"%dp0%\\([^"]+\.exe)"/i.exec(fs.readFileSync(shim, "utf8"));
  const file = exe && path.join(path.dirname(shim), exe[1]);
  if (!file || !fs.existsSync(file)) throw new Error("opencode.exe не найден");
  return file;
}
export const OPENCODE = findOpencode();

// Как hook-clients.mjs, и ещё: навыки из ~/.claude модели не уходят (server-process.ts:127-131).
export const baseEnv = () => ({
  ...Object.fromEntries(Object.entries(process.env).filter(([k]) => !/^(CLAUDE|ELECTRON_|VSCODE_)/i.test(k) && !["NoDefaultCurrentDirectoryInExePath", "PYTHONIOENCODING", "PWD", "OLDPWD", "INIT_CWD"].includes(k))),
  OPENCODE_DISABLE_CLAUDE_CODE: "1",
  OPENCODE_PASSWORD: PASSWORD,
});

export const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
export const say = (...args) => console.log(new Date().toISOString().slice(11, 19), ...args);

export function makeProject(name, { config } = {}) {
  const root = path.join(WORK, "проекты с пробелом", name);
  fs.mkdirSync(path.join(root, ".opencode", "plugins"), { recursive: true });
  fs.mkdirSync(path.join(root, ".symphysis", "viewer"), { recursive: true });
  fs.mkdirSync(path.join(root, "openspec", "changes", "demo", "answers"), { recursive: true });
  fs.mkdirSync(path.join(root, "sub"), { recursive: true });
  fs.copyFileSync(path.join(TOOLS, "plugin", "f49-probe.js"), path.join(root, ".opencode", "plugins", "f49-probe.js"));
  fs.writeFileSync(path.join(root, ANSWER), `# Ответы\n\n${MARKER}\n`, "utf8");
  if (config) fs.writeFileSync(path.join(root, "opencode.json"), JSON.stringify(config, null, 2), "utf8");
  spawnSync("git", ["init", "-q"], { cwd: root });
  return root;
}

export function newTrace(name) {
  const dir = path.join(WORK, "trace", name);
  fs.mkdirSync(dir, { recursive: true });
  return dir;
}

export function setControl(traceDir, value) {
  fs.writeFileSync(path.join(traceDir, "control.json"), JSON.stringify(value), "utf8");
}

export function readTrace(traceDir) {
  const file = path.join(traceDir, "trace.jsonl");
  if (!fs.existsSync(file)) return [];
  return fs.readFileSync(file, "utf8").split("\n").filter(Boolean).map((l) => JSON.parse(l));
}

export function note(traceDir, row) {
  fs.appendFileSync(path.join(traceDir, "trace.jsonl"), `${JSON.stringify({ t: Date.now(), at: "probe", ...row })}\n`, "utf8");
}

export async function waitFor(traceDir, test, what, ms = 180000) {
  const from = Date.now();
  while (Date.now() - from < ms) {
    const found = readTrace(traceDir).find(test);
    if (found) return found;
    await sleep(250);
  }
  note(traceDir, { timeout: what, ms });
  say(`ТАЙМАУТ: ${what}`);
  return null;
}

export function remember(id) {
  if (!id) return;
  const known = fs.existsSync(SESSIONS) ? fs.readFileSync(SESSIONS, "utf8").split("\n").filter(Boolean) : [];
  if (!known.includes(id)) fs.appendFileSync(SESSIONS, `${id}\n`, "utf8");
}

export function rememberFromTrace(traceDir) {
  for (const row of readTrace(traceDir)) if (row.at === "event" && row.type === "session.created") remember(row.sessionID);
}

export async function startServer(traceDir, { cwd = path.join(WORK, "empty"), label = "serve", extraEnv = {} } = {}) {
  fs.mkdirSync(path.join(WORK, "empty"), { recursive: true });
  const child = spawn(OPENCODE, ["serve", "--hostname", "127.0.0.1", "--print-logs", "--log-level", "info"], { cwd, env: { ...baseEnv(), F49_TRACE_DIR: traceDir, ...extraEnv }, stdio: ["ignore", "pipe", "pipe"], windowsHide: true });
  const logFile = path.join(traceDir, `${label}-${child.pid}.log`);
  const log = fs.createWriteStream(logFile, { flags: "a" });
  child.stderr.pipe(log);
  let url = null;
  child.stdout.on("data", (b) => {
    const text = b.toString();
    log.write(text);
    const m = /server listening on (\S+)/.exec(text);
    if (m) url = m[1];
  });
  const from = Date.now();
  while (!url && Date.now() - from < 60000) await sleep(100);
  if (!url) throw new Error("сервер не поднялся");
  say(`${label}: pid ${child.pid}`);
  fs.appendFileSync(path.join(WORK, "pids.txt"), `${child.pid}\n`, "utf8");
  return { child, url, label, logFile };
}

export function stopServer(server) {
  if (!server?.child?.pid) return;
  spawnSync("taskkill", ["/PID", String(server.child.pid), "/T", "/F"], { windowsHide: true });
  say(`${server.label}: остановлен`);
}

export async function rest(server, method, route, { body, directory } = {}) {
  const headers = { authorization: `Basic ${Buffer.from(`opencode:${PASSWORD}`).toString("base64")}` };
  if (body !== undefined) headers["content-type"] = "application/json";
  if (directory) headers["x-opencode-directory"] = encodeURIComponent(directory);
  const res = await fetch(`${server.url}${route}`, { method, headers, body: body === undefined ? undefined : JSON.stringify(body) });
  const text = await res.text();
  let json = null;
  try {
    json = JSON.parse(text);
  } catch {
    /* не JSON */
  }
  return { status: res.status, json, text };
}

export async function idle(server, sessionID, ms = 180000) {
  const from = Date.now();
  while (Date.now() - from < ms) {
    const active = await rest(server, "GET", "/api/session/active");
    const data = active.json?.data;
    const busy = Array.isArray(data) ? data.includes(sessionID) || data.some((x) => x?.id === sessionID) : JSON.stringify(data ?? "").includes(sessionID);
    if (!busy) return true;
    await sleep(500);
  }
  say(`сессия ${sessionID} всё ещё занята`);
  return false;
}

export function cli(args, cwd, { timeout = 240000, traceDir } = {}) {
  return new Promise((resolve) => {
    const env = { ...baseEnv(), ...(traceDir ? { F49_TRACE_DIR: traceDir } : {}) };
    const child = spawn(OPENCODE, args, { cwd, env, stdio: ["ignore", "pipe", "pipe"], windowsHide: true });
    let out = "";
    let err = "";
    child.stdout.on("data", (b) => (out += b));
    child.stderr.on("data", (b) => (err += b));
    const timer = setTimeout(() => spawnSync("taskkill", ["/PID", String(child.pid), "/T", "/F"], { windowsHide: true }), timeout);
    child.on("close", (code) => {
      clearTimeout(timer);
      let id = null;
      const texts = [];
      for (const line of out.split(/\r?\n/)) {
        let row;
        try {
          row = JSON.parse(line);
        } catch {
          continue;
        }
        if (!row || typeof row !== "object") continue;
        id ??= row.sessionID ?? row.session_id ?? row.session?.id ?? null;
        if (typeof row.text === "string") texts.push(row.text);
        else if (typeof row.part?.text === "string") texts.push(row.part.text);
      }
      remember(id);
      resolve({ code, id, text: texts.join(""), out, err });
    });
  });
}

export const runAttached = (server, cwd, message, extra = []) => cli(["run", "--server", server.url, "--format", "json", "-m", MODEL, ...extra, message], cwd);
export const runStandalone = (cwd, message, traceDir, extra = []) => cli(["run", "--standalone", "--format", "json", "-m", MODEL, ...extra, message], cwd, { traceDir });

export function emit(root, probe) {
  const hash = "ab".repeat(32);
  fs.appendFileSync(path.join(root, ".symphysis", "viewer", "events.jsonl"), `${JSON.stringify({ change: "demo", answers: ANSWER, sha256_before: hash, sha256_after: "cd".repeat(32), probe })}\n`, "utf8");
}

export const mark = (traceDir, tag) => {
  note(traceDir, { mark: tag });
  say(tag);
};

export const homedir = os.homedir();
