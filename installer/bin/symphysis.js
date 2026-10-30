#!/usr/bin/env node
import { parseArgs } from "node:util";

const USAGE = `symphysis — схема OpenSpec symphysis, скиллы и инструменты журнала в проект

Использование:
  symphysis install [--project <dir>] [--skills-dir <dir>]... [--force]
  symphysis check   [--project <dir>]
  symphysis --help

Команды:
  install   поставить схему, скиллы и инструменты журнала в проект
  check     сверить установку и версию форка OpenSpec

Параметры:
  --project <dir>     корень проекта (по умолчанию — текущий каталог)
  --skills-dir <dir>  каталог скиллов; повторяемый; относительный путь —
                      от --project; без параметра — один .claude/skills
  --force             перезаписать существующее (install)
  -h, --help          эта справка
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

if (positionals.length > 1) {
  process.stderr.write(`лишние аргументы: ${positionals.slice(1).join(" ")}

${USAGE}`);
  process.exit(2);
}

if (values.help || cmd === "help") {
  process.stdout.write(USAGE);
} else if (cmd === "install" || cmd === "check") {
  process.stderr.write(`symphysis ${cmd}: не реализовано\n`);
  process.exit(2);
} else {
  process.stderr.write(`${cmd ? `неизвестная команда: ${cmd}\n\n` : ""}${USAGE}`);
  process.exit(2);
}
