import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { spawnSync } from "node:child_process";
import { parse } from "yaml";
import { targets } from "./paths.js";
import { DEFAULT_PAYLOAD } from "./install.js";

const here = path.dirname(fileURLToPath(import.meta.url));
const win = process.platform === "win32";
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

/** Версия форка: SYMPHYSIS_OPENSPEC (.js или исполняемый) либо `openspec` из PATH; null — не запустился. */
function openspecVersion() {
  const env = process.env.SYMPHYSIS_OPENSPEC;
  let r;
  if (env) {
    r = env.endsWith(".js")
      ? spawnSync(process.execPath, [env, "--version"], { encoding: "utf8" })
      : win && /\.(cmd|bat)$/i.test(env)
        ? spawnSync(`"${env}" --version`, { encoding: "utf8", shell: true })
        : spawnSync(env, ["--version"], { encoding: "utf8" });
  } else {
    // на Windows openspec из PATH — это openspec.cmd, его запускает только оболочка
    r = win ? spawnSync("openspec --version", { encoding: "utf8", shell: true }) : spawnSync("openspec", ["--version"], { encoding: "utf8" });
  }
  if (r.error || r.status !== 0) return null;
  return String(r.stdout).trim();
}

/** Python: на Windows `py -3.13`, иначе python3.13, затем python3. Возвращает { cmd, args, label } или null. */
function findPython() {
  const candidates = win
    ? [{ cmd: "py", args: ["-3.13"], label: "py -3.13" }]
    : [{ cmd: "python3.13", args: [], label: "python3.13" }, { cmd: "python3", args: [], label: "python3" }];
  for (const c of candidates) {
    const r = spawnSync(c.cmd, [...c.args, "--version"], { encoding: "utf8" });
    if (!r.error && r.status === 0) return c;
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
    else if (!fs.readFileSync(to).equals(fs.readFileSync(file))) findings.push(`${rel(root, to)}: схема изменена`);
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
  if (!py) findings.push(`python: ${win ? "py -3.13" : "python3.13 или python3"} не отвечает`);

  const changes = path.join(root, "openspec", "changes");
  const journalPy = path.join(toolsDir, "journal.py");
  if (py && fs.existsSync(journalPy) && fs.existsSync(changes)) {
    for (const e of fs.readdirSync(changes, { withFileTypes: true }).sort((a, b) => a.name.localeCompare(b.name))) {
      const j = path.join(changes, e.name, "decisions.json");
      if (!e.isDirectory() || !fs.existsSync(j)) continue;
      const r = spawnSync(py.cmd, [...py.args, "-X", "utf8", journalPy, "check", j], { encoding: "utf8" });
      if (r.error || r.status !== 0) findings.push(`${rel(root, j)}: журнал негоден по схеме`);
      else {
        const lines = String(r.stdout).trim().split(/\r?\n/).filter(Boolean);
        const line = lines.find((l) => l.includes("улик сверено")) ?? lines.pop() ?? "";
        notes.push(`${rel(root, j)}: ${line}`);
      }
    }
  }

  return { ok: findings.length === 0, findings, notes };
}
