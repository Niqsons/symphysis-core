import fs from "node:fs";
import path from "node:path";
import { spawn, spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { isFullyAbsolute } from "./paths.js";

const here = path.dirname(fileURLToPath(import.meta.url));
const win = process.platform === "win32";
const CMD_META = /([()\][%!^"`<>&|;, *?])/g;
const NOT_FOUND = { notFound: true, status: null, stdout: "", stderr: "" };

/**
 * Аргумент для строки `cmd`: кавычки по правилам разбора argv, метасимволы через `^`.
 * Метасимволы дважды: шим npm передаёт `%*`, и `.cmd` разбирает строку второй раз.
 */
function cmdArg(arg) {
  const quoted = `"${String(arg).replace(/(\\*)"/g, '$1$1\\"').replace(/(\\*)$/, "$1$1")}"`;
  return quoted.replace(CMD_META, "^$1").replace(CMD_META, "^$1");
}

/** Первый `openspec` из PATH по PATHEXT; null — нет. На Windows `spawn` без оболочки `.cmd` не находит. */
export function* executableCandidates(name, env = process.env) {
  const exts = win ? (env.PATHEXT || ".COM;.EXE;.BAT;.CMD").split(";").filter(Boolean) : [""];
  for (const dir of String(env.PATH ?? env.Path ?? "").split(path.delimiter).filter((d) => isFullyAbsolute(d))) {
    for (const ext of exts) yield path.join(dir, name + ext);
  }
}

export function findExecutable(name, env = process.env) {
  for (const file of executableCandidates(name, env)) {
    try {
      if (!fs.statSync(file, { throwIfNoEntry: false })?.isFile()) continue;
      if (!win) fs.accessSync(file, fs.constants.X_OK);
      return file;
    } catch (error) {
      if (!["EACCES", "EPERM", "ENOENT", "ENOTDIR"].includes(error.code)) throw error;
    }
  }
  return null;
}

/**
 * `spawnSync` без поиска программы в каталоге вызова. На Windows голое имя ищется сначала в `cwd`, то есть в корне чужого проекта:
 * лежащий там `python.exe` или `git.exe` исполнился бы. Поиск отключает `NoDefaultCurrentDirectoryInExePath`; `libuv` читает её
 * из окружения самого процесса, а не из `options.env`, поэтому она ставится здесь, в `process.env`. Для `cmd.exe` она же идёт в окружении вызова.
 */
export function spawnTool(command, args, options = {}) {
  if (win) process.env.NoDefaultCurrentDirectoryInExePath = "1";
  return spawnSync(command, args, options);
}

/** Same cwd executable guard for a child whose lifetime the dispatcher owns. */
export function spawnToolAsync(command, args, options = {}) {
  if (win) process.env.NoDefaultCurrentDirectoryInExePath = "1";
  return spawn(command, args, { windowsHide: true, ...options });
}

export function executableLauncher(file, args) {
  if (win && /\.(cmd|bat)$/i.test(file)) {
    const line = [file.replace(CMD_META, "^$1"), ...args.map(cmdArg)].join(" ");
    return { command: line, args: [], shell: true };
  }
  return { command: file, args, shell: false };
}

/** The same pinned fork launch is used for read-only probes and leased commands. */
export function openspecLauncher(args, env = process.env) {
  if (env.SYMPHYSIS_OPENSPEC && !isFullyAbsolute(env.SYMPHYSIS_OPENSPEC)) throw Object.assign(new Error("SYMPHYSIS_OPENSPEC: нужен полный абсолютный путь"), { code: "fork-path-invalid", exitCode: 2 });
  const chosen = env.SYMPHYSIS_OPENSPEC ? path.resolve(env.SYMPHYSIS_OPENSPEC) : findExecutable("openspec", env);
  if (!chosen || !fs.existsSync(chosen)) return null;
  return chosen.endsWith(".js") ? { command: process.execPath, args: [chosen, ...args], shell: false } : executableLauncher(chosen, args);
}

export function openspecEnvironment(env = process.env) {
  const clean = Object.fromEntries(Object.entries(env).filter(([key]) => key.toLowerCase() !== "nodefaultcurrentdirectoryinexepath"));
  return { ...clean, OPENSPEC_TELEMETRY: "0", NoDefaultCurrentDirectoryInExePath: "1" };
}

/**
 * Запускает форк OpenSpec с аргументами: SYMPHYSIS_OPENSPEC (.js или исполняемый) либо `openspec` из PATH.
 * Инсталлятор телеметрию не порождает: каждый вызов идёт с OPENSPEC_TELEMETRY=0 (F-116.A).
 * Возвращает результат spawnSync; `notFound: true` — форка нет, ненулевой `status` или `error` — форк есть и отказал.
 */
export function runOpenspec(args, { cwd, env: suppliedEnv = process.env, timeout = 15000 } = {}) {
  // Шим npm без `node.exe` рядом зовёт голое `node`, и `cmd.exe` ищет его сначала в `cwd`. Ключ снимается без учёта регистра: дубля в блоке нет.
  let launch;
  try { launch = openspecLauncher(args, suppliedEnv); }
  catch (error) { return { notFound: false, error, status: null, stdout: "", stderr: "" }; }
  if (!launch) return NOT_FOUND;
  const r = spawnTool(launch.command, launch.args, { encoding: "utf8", cwd, timeout, env: openspecEnvironment(suppliedEnv), shell: launch.shell });
  return { ...r, notFound: false };
}

/** Пин и источник форка из `package.json`. */
export function forkPin() {
  return JSON.parse(fs.readFileSync(path.join(here, "..", "package.json"), "utf8")).symphysis;
}

/** Текст отказа: «не найден» и отказ самого форка — разные исходы. */
export function describeFailure(r) {
  if (r.notFound) return "openspec не найден";
  if (r.error) return `openspec не отработал (${r.error.message})`;
  const first = [r.stderr, r.stdout].flatMap((s) => String(s ?? "").split(/\r?\n/)).find((l) => l.trim());
  return `openspec не отработал (код ${r.status}${first ? `: ${first.trim()}` : ""})`;
}
