import fs from "node:fs";
import path from "node:path";
import { readGlobalConfig } from "./global-config.js";
import { describeFailure, forkPin, runOpenspec } from "./openspec-bin.js";

const COMMAND_DIR = ["commands", "opsx"];
const CONTINUE_FILE = "continue.md";
const CONTINUE_SKILL = "openspec-continue-change";
const UPDATE_LATER = "openspec update";

/** Как выбрать клиента: инсталлятор сам клиентов не ищет (F-115.D). В PowerShell `where` — псевдоним Where-Object. */
export const CLIENT_HINT = "какой клиент есть: where.exe claude, where.exe opencode в PowerShell; which claude, which opencode в bash; каталог клиента: --skills-dir";

const hasForkSkills = (skills) => fs.statSync(skills, { throwIfNoEntry: false })?.isDirectory() && fs.readdirSync(skills).some((n) => n.startsWith("openspec-"));

/**
 * Выбранные клиенты: клиент — каталог над `--skills-dir`, имя — имя этого каталога без точки.
 * Настроен — там есть созданные форком `skills/openspec-*` или `commands/opsx/`;
 * команда установлена — есть файл команды или скилл `openspec-continue-change` (F-115.D).
 */
export function selectedClients(root, skillsDirs) {
  return skillsDirs.map((skills) => {
    const dir = path.dirname(skills);
    const commands = path.join(dir, ...COMMAND_DIR);
    return {
      label: path.relative(root, dir).split(path.sep).join("/"),
      name: path.basename(dir).replace(/^\./, ""),
      configured: hasForkSkills(skills) || fs.existsSync(commands),
      hasContinue: fs.existsSync(path.join(commands, CONTINUE_FILE)) || fs.existsSync(path.join(skills, CONTINUE_SKILL, "SKILL.md")),
    };
  });
}

/** Строки `check` о команде: `[!!]`, только если команды нет ни в одном выбранном каталоге (F-124.A). */
export function continueLines(clients) {
  const findings = [];
  const notes = [];
  const configured = clients.filter((c) => c.configured);
  if (!clients.some((c) => c.hasContinue)) {
    if (configured.length) {
      findings.push(`continue: команда /opsx:continue не установлена у ${configured.map((c) => c.name).join(", ")} — выполнить: symphysis install`);
    } else {
      findings.push(`continue: клиент не настроен — выполнить: openspec init --tools ${clients[0].name}`);
      notes.push(`continue: ${CLIENT_HINT}`);
    }
  }
  if (configured.length) {
    for (const c of clients) if (!c.configured) notes.push(`${c.label}: файлов форка нет, туда поставлены только скиллы symphysis`);
  }
  return { findings, notes };
}

/** Почему обновление проекта команду не поставит или испортит конфиг; null — можно звать. Конфиг не меняется. */
function profileObstacle() {
  const { state, config } = readGlobalConfig();
  if (state !== "ok") return null;
  if (config.profile === undefined) {
    // Разовая миграция форка записала бы профиль custom со списком того, что уже стоит в проекте, без continue.
    return "continue: в глобальном конфиге не задан профиль, openspec update записал бы туда свой список — выполнить: openspec config profile core, затем openspec update";
  }
  if (config.profile === "custom" && !(config.workflows ?? []).includes("continue")) {
    return "continue: в профиле custom нет workflow continue — добавить: openspec config profile, затем openspec update";
  }
  return null;
}

/**
 * Ставит `/opsx:continue` обновлением проекта, если команды нет; профиль и список workflow не трогает (F-126.A).
 * Ничего из этого установку не останавливает: команда на потом и подсказка идут строками.
 */
export function ensureContinue(root, skillsDirs) {
  const clients = selectedClients(root, skillsDirs);
  if (clients.some((c) => c.hasContinue)) return [];
  if (!clients.some((c) => c.configured)) {
    return [`continue: клиент не настроен — выполнить потом: openspec init --tools ${clients[0].name}`, `continue: ${CLIENT_HINT}`];
  }
  const obstacle = profileObstacle();
  if (obstacle) return [obstacle];
  // Другая версия OpenSpec переписала бы файлы проекта своими и не поставила бы команду: это то же «форка нет».
  const version = runOpenspec(["--version"]);
  if (version.notFound) return [`continue: ${describeFailure(version)} — выполнить потом: ${UPDATE_LATER}`, `continue: ${CLIENT_HINT}`];
  if (version.error || version.status !== 0) return [`continue: ${describeFailure(version)} — выполнить потом: ${UPDATE_LATER}`];
  const actual = String(version.stdout).trim();
  const { openspecPin } = forkPin();
  if (actual !== openspecPin) return [`continue: openspec версии ${actual}, нужен форк ${openspecPin} — выполнить потом: ${UPDATE_LATER}`];
  const r = runOpenspec(["update", root], { cwd: root });
  if (r.notFound || r.error || r.status !== 0) return [`continue: ${describeFailure(r)} — выполнить потом: ${UPDATE_LATER}`];
  if (!selectedClients(root, skillsDirs).some((c) => c.hasContinue)) {
    return ["continue: после openspec update команды нет — проверить: openspec config profile"];
  }
  return ["continue: проект обновлён: openspec update"];
}
