import fs from "node:fs";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

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
function findOnPath(name) {
  const exts = (process.env.PATHEXT || ".COM;.EXE;.BAT;.CMD").split(";").filter(Boolean);
  for (const dir of String(process.env.PATH ?? "").split(path.delimiter).filter(Boolean)) {
    for (const ext of exts) {
      const file = path.join(dir, name + ext);
      if (fs.statSync(file, { throwIfNoEntry: false })?.isFile()) return file;
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

function spawnFile(file, args, options) {
  if (win && /\.(cmd|bat)$/i.test(file)) {
    const line = [file.replace(CMD_META, "^$1"), ...args.map(cmdArg)].join(" ");
    return spawnTool(line, [], { ...options, shell: true });
  }
  return spawnTool(file, args, options);
}

/**
 * Запускает форк OpenSpec с аргументами: SYMPHYSIS_OPENSPEC (.js или исполняемый) либо `openspec` из PATH.
 * Инсталлятор телеметрию не порождает: каждый вызов идёт с OPENSPEC_TELEMETRY=0 (F-116.A).
 * Возвращает результат spawnSync; `notFound: true` — форка нет, ненулевой `status` или `error` — форк есть и отказал.
 */
export function runOpenspec(args, { cwd } = {}) {
  // Шим npm без `node.exe` рядом зовёт голое `node`, и `cmd.exe` ищет его сначала в `cwd`. Ключ снимается без учёта регистра: дубля в блоке нет.
  const env = Object.fromEntries(Object.entries(process.env).filter(([key]) => key.toLowerCase() !== "nodefaultcurrentdirectoryinexepath"));
  const options = { encoding: "utf8", cwd, env: { ...env, OPENSPEC_TELEMETRY: "0", NoDefaultCurrentDirectoryInExePath: "1" } };
  // Абсолютный путь: у вызова может быть свой cwd.
  const chosen = process.env.SYMPHYSIS_OPENSPEC ? path.resolve(process.env.SYMPHYSIS_OPENSPEC) : null;
  let r;
  if (chosen) {
    if (!fs.existsSync(chosen)) return NOT_FOUND;
    r = chosen.endsWith(".js") ? spawnTool(process.execPath, [chosen, ...args], options) : spawnFile(chosen, args, options);
  } else if (win) {
    const file = findOnPath("openspec");
    if (!file) return NOT_FOUND;
    r = spawnFile(file, args, options);
  } else {
    r = spawnTool("openspec", args, options);
    if (r.error?.code === "ENOENT") return NOT_FOUND;
  }
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
