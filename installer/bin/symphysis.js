#!/usr/bin/env node
import fs from "node:fs";
import path from "node:path";
import { parseArgs } from "node:util";
import { install } from "../lib/install.js";
import { check, findPython } from "../lib/check.js";
import { spawnTool } from "../lib/openspec-bin.js";
import { targets } from "../lib/paths.js";

const USAGE = `symphysis — схема OpenSpec symphysis, скиллы и инструменты журнала в проект

Использование:
  symphysis install [--project <dir>] [--skills-dir <dir>]... [--force]
  symphysis check   [--project <dir>] [--skills-dir <dir>]...
  symphysis config  [--project <dir>]
  symphysis --help

Команды:
  install   поставить схему, скиллы и инструменты журнала в проект, создать личный
            symphysis.yaml и внести его в .gitignore; если нет /opsx:continue, обновить
            проект, не трогая профиль. Звать, когда symphysis ставится в проект впервые
            или обновляется
  check     назвать расхождения установки, версии форка OpenSpec, команды /opsx:continue
            и настроек (не чинит). Звать, когда нужно проверить, что установка цела,
            например перед работой или после обновления
  config    показать состав из symphysis.yaml: ветки отказа, допущения, проба
            краёв. Звать, когда человек хочет узнать, с чем пойдёт следующий шаг:
            тот же состав и те же сигналы получает скилл от symphysis_config.py

Параметры:
  --project <dir>     корень проекта (по умолчанию — текущий каталог)
  --skills-dir <dir>  каталог скиллов выбранного клиента; повторяемый; относительный
                      путь — от --project; без параметра — один .claude/skills.
                      Какой клиент есть: where.exe claude, where.exe opencode в
                      PowerShell, which в bash
  --force             перезаписать существующее (install)
  -h, --help          эта справка

Маркеры check: [!!] расхождение, [..] сигнал, на код не влияет.
Код выхода: 0 | 2 (расхождения или usage) | 1 (внутренняя ошибка);
у install форка или клиента может не быть: команда на потом в stdout, код 0;
у config сигналы код не меняют: 0, неверный --project — 2
`;

let parsed;
try {
  parsed = parseArgs({
    allowPositionals: true,
    options: {
      project: { type: "string" },
      "skills-dir": { type: "string", multiple: true },
      force: { type: "boolean" },
      help: { type: "boolean", short: "h" },
    },
  });
} catch (e) {
  process.stderr.write(`${e.message}\n\n${USAGE}`);
  process.exit(2);
}

const { values, positionals } = parsed;
const cmd = positionals[0];

if (positionals.length > 1 && !values.help) {
  process.stderr.write(`лишние аргументы: ${positionals.slice(1).join(" ")}

${USAGE}`);
  process.exit(2);
}

if (values.help || cmd === "help") {
  process.stdout.write(USAGE);
} else if (cmd === "install") {
  let r;
  try {
    r = install(values.project ?? process.cwd(), { skillsDirs: values["skills-dir"] ?? [], force: Boolean(values.force) });
  } catch (e) {
    process.stderr.write(`symphysis install: ${e.message}\n`);
    process.exit(1);
  }
  process.stdout.write(`записано ${r.written.length}\n`);
  for (const m of r.messages) process.stdout.write(`${m}\n`);
  if (r.skipped.length) {
    for (const s of r.skipped) process.stderr.write(`${s}\n`);
    process.stderr.write("перезапись существующих файлов: --force\n");
  }
} else if (cmd === "check") {
  let r;
  try {
    r = check(values.project ?? process.cwd(), { skillsDirs: values["skills-dir"] ?? [] });
  } catch (e) {
    process.stderr.write(`symphysis check: ${e.message}\n`);
    process.exit(1);
  }
  for (const f of r.findings) process.stdout.write(`[!!] ${f}\n`);
  for (const n of r.notes) process.stdout.write(`[..] ${n}\n`);
  process.stdout.write(r.ok ? "check: ok\n" : `check: ${r.findings.length} расхождений\n`);
  process.exit(r.ok ? 0 : 2);
} else if (cmd === "config") {
  const project = values.project ?? process.cwd();
  if (!fs.statSync(project, { throwIfNoEntry: false })?.isDirectory()) {
    process.stderr.write(`symphysis config: --project: каталога нет: ${project}\n`);
    process.exit(2);
  }
  const py = findPython();
  const tool = path.join(targets(path.resolve(project)).toolsDir, "tools", "symphysis_config.py");
  const fail = (line) => {
    process.stdout.write(`[!!] ${line}\n`);
    process.exit(2);
  };
  if (!py) fail("python: python или python3 не отвечает");
  if (!fs.existsSync(tool)) fail("symphysis_config.py: нет файла — выполнить: symphysis install");
  const r = spawnTool(py, ["-X", "utf8", tool, "--project", project], { encoding: "utf8" });
  if (r.error || r.status !== 0) {
    const first = (r.error ? r.error.message : String(r.stderr ?? "").split(/\r?\n/).find((l) => l.trim())) ?? `код ${r.status}`;
    fail(`symphysis_config.py: не отработал (${first.trim()})`);
  }
  process.stdout.write(r.stdout);
} else {
  process.stderr.write(`${cmd ? `неизвестная команда: ${cmd}\n\n` : ""}${USAGE}`);
  process.exit(2);
}
