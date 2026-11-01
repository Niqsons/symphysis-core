import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { spawnSync } from "node:child_process";
import { parse } from "yaml";
import { targets } from "./paths.js";
import { DEFAULT_PAYLOAD } from "./install.js";
import { runOpenspec } from "./openspec-bin.js";
import { telemetryState, TELEMETRY_OFF_COMMAND } from "./telemetry.js";

const here = path.dirname(fileURLToPath(import.meta.url));
const TOOL_MODULES = ["journal.py", "journal_apply.py", "journal_cli.py", "journal_model.py", "journal_render.py"];

const rel = (project, p) => path.relative(project, p).split(path.sep).join("/");

function walk(dir) {
  const out = [];
  for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, e.name);
    if (e.isDirectory()) out.push(...walk(full));
    else out.push(full);
  }
  return out;
}

function readPin() {
  const pkg = JSON.parse(fs.readFileSync(path.join(here, "..", "package.json"), "utf8"));
  return pkg.symphysis;
}

/** Версия форка; null — не запустился. */
function openspecVersion() {
  const r = runOpenspec(["--version"]);
  if (r.error || r.status !== 0) return null;
  return String(r.stdout).trim();
}

/** Python: `python`, затем `python3`; версия не закрепляется. Возвращает имя команды или null. */
function findPython() {
  for (const cmd of ["python", "python3"]) {
    const r = spawnSync(cmd, ["--version"], { encoding: "utf8" });
    if (!r.error && r.status === 0) return cmd;
  }
  return null;
}

/**
 * Сверяет установку symphysis в проекте. Только называет расхождения, ничего не чинит.
 * `findings` — отказы (каждая строка начинается с имени файла или предмета); `notes` — сигналы (журналы).
 */
export function check(project, { skillsDirs = [], payloadDir = DEFAULT_PAYLOAD } = {}) {
  const root = path.resolve(project);
  const t = targets(root, skillsDirs);
  const { openspecPin, openspecSource } = readPin();
  const findings = [];
  const notes = [];

  const actual = openspecVersion();
  if (actual === null) findings.push(`openspec: не найден (SYMPHYSIS_OPENSPEC или PATH); нужен форк ${openspecPin}: ${openspecSource}`);
  else if (actual !== openspecPin) findings.push(`openspec: версия ${actual}, нужна ${openspecPin} (форк symphysis): ${openspecSource}`);

  const schemaSrc = path.join(payloadDir, "openspec", "schemas", "symphysis");
  for (const file of walk(schemaSrc).sort()) {
    const to = path.join(t.schemaDir, path.relative(schemaSrc, file));
    if (!fs.existsSync(to)) findings.push(`${rel(root, to)}: нет файла`);
    else if (!fs.readFileSync(to).equals(fs.readFileSync(file))) findings.push(`схема: байты отличаются от payload: ${rel(root, to)}`);
  }

  const cfgRel = rel(root, t.configPath);
  if (!fs.existsSync(t.configPath)) findings.push(`${cfgRel}: нет файла`);
  else {
    let schema;
    try {
      schema = parse(fs.readFileSync(t.configPath, "utf8"))?.schema;
    } catch (e) {
      findings.push(`${cfgRel}: не разбирается (${String(e.message).split("\n")[0]})`);
      schema = null;
    }
    if (schema !== null && schema !== "symphysis") findings.push(`${cfgRel}: schema не symphysis (${schema ?? "не задана"})`);
  }

  const skillNames = fs
    .readdirSync(path.join(payloadDir, "skills"), { withFileTypes: true })
    .filter((e) => e.isDirectory() && e.name.startsWith("symphysis-"))
    .map((e) => e.name);
  for (const dir of t.skillsDirs) {
    for (const name of skillNames) {
      const f = path.join(dir, name, "SKILL.md");
      if (!fs.existsSync(f)) findings.push(`${rel(root, f)}: нет файла`);
    }
  }

  const toolsDir = path.join(t.toolsDir, "tools");
  const toolFiles = [
    ...TOOL_MODULES.map((m) => path.join(toolsDir, m)),
    path.join(t.toolsDir, "docs", "journal.schema.json"),
    path.join(toolsDir, "journal-roots.json"),
  ];
  for (const f of toolFiles) if (!fs.existsSync(f)) findings.push(`${rel(root, f)}: нет файла`);

  const py = findPython();
  if (!py) findings.push("python: python или python3 не отвечает");

  const changes = path.join(root, "openspec", "changes");
  const journalPy = path.join(toolsDir, "journal.py");
  if (py && fs.existsSync(journalPy) && fs.existsSync(changes)) {
    for (const e of fs.readdirSync(changes, { withFileTypes: true }).sort((a, b) => a.name.localeCompare(b.name))) {
      const j = path.join(changes, e.name, "decisions.json");
      if (!e.isDirectory() || !fs.existsSync(j)) continue;
      const r = spawnSync(py, ["-X", "utf8", journalPy, "check", j], { encoding: "utf8" });
      if (r.error || r.status !== 0) {
        const err = String(r.stderr ?? "");
        if (r.error || !err.includes("[!!]")) {
          const first = (r.error ? r.error.message : err.split(/\r?\n/).find((l) => l.trim())) ?? `код ${r.status}`;
          findings.push(`${rel(root, j)}: journal.py check не отработал (${first.trim()})`);
        } else findings.push(`${rel(root, j)}: журнал негоден по схеме`);
      } else {
        const lines = String(r.stdout).trim().split(/\r?\n/).filter(Boolean);
        const line = lines.find((l) => l.includes("улик сверено")) ?? "";
        notes.push(`${rel(root, j)}: ${line}`);
      }
    }
  }

  const tele = telemetryState();
  if (tele === "off") notes.push("telemetry: выключена");
  else if (tele === "missing") notes.push("telemetry: конфиг OpenSpec не найден — появится после первого openspec init");
  else if (tele === "unreadable") notes.push("telemetry: конфиг OpenSpec не читается — форк в этом случае телеметрию выключает");
  else findings.push(`telemetry: включена — выключить: ${TELEMETRY_OFF_COMMAND}`);

  return { ok: findings.length === 0, findings, notes };
}
