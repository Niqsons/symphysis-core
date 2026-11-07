import fs from "node:fs";
import path from "node:path";
import { parse } from "yaml";
import { continueLines, selectedClients } from "./clients.js";
import { globalConfigPath, otherConfigPath } from "./global-config.js";
import { targets } from "./paths.js";
import { DEFAULT_PAYLOAD } from "./install.js";
import { describeFailure, forkPin, runOpenspec, spawnTool } from "./openspec-bin.js";
import { telemetryState, TELEMETRY_OFF_COMMAND } from "./telemetry.js";
import { hasSources, payloadMatches, ROOT } from "../scripts/sync-payload.js";

const SETTINGS_FILE = "symphysis.yaml";
const TOOL_MODULES = ["journal.py", "journal_apply.py", "journal_cli.py", "journal_model.py", "journal_render.py", "journal.schema.json", "roots.py", "viewer_render.py", "attack_table.py", "journal_sites.py", "journal_consequences.py", "symphysis_config.py", "openspec_run.py", "trace_graph.py", "anchor_refs.py"];

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

/** Строка о форке или null: «не найден» и отказ самого форка — разные исходы; обе называют тарбол (F-31.A, F-36.A). */
function forkFinding() {
  const { openspecPin, openspecSource } = forkPin();
  const install = `npm i -g ./${openspecSource}`;
  const r = runOpenspec(["--version"]);
  if (r.notFound) return `openspec: не найден (SYMPHYSIS_OPENSPEC или PATH); нужен форк ${openspecPin}: ${install}`;
  if (r.error || r.status !== 0) return `openspec: ${describeFailure(r).replace(/^openspec /, "")}; нужен форк ${openspecPin}: ${install}`;
  const actual = String(r.stdout).trim();
  return actual === openspecPin ? null : `openspec: версия ${actual}, нужна ${openspecPin} (форк symphysis): ${install}`;
}

/** Строки скрипта настроек: `[..]` — заметка, `[!!]` — находка. Файл инсталлятор сам не разбирает (F-135.B). */
function settingsLines(root, py, tool, findings, notes) {
  if (!fs.existsSync(path.join(root, SETTINGS_FILE))) {
    notes.push(`${SETTINGS_FILE}: нет файла, действует всё включено; создать: symphysis install`);
    return;
  }
  if (!py || !fs.existsSync(tool)) return;
  const r = spawnTool(py, ["-X", "utf8", tool, "--project", root, "--strict"], { encoding: "utf8" });
  if (r.error || (r.status !== 0 && r.status !== 2)) {
    const first = (r.error ? r.error.message : String(r.stderr ?? "").split(/\r?\n/).find((l) => l.trim())) ?? `код ${r.status}`;
    findings.push(`symphysis_config.py: не отработал (${first.trim()})`);
    return;
  }
  for (const line of String(r.stdout).split(/\r?\n/)) {
    if (line.startsWith("[!!] ")) findings.push(line.slice(5));
    else if (line.startsWith("[..] ")) notes.push(line.slice(5));
  }
}

/** `symphysis.yaml` в индексе git проекта: `.gitignore` его уже не снимет (F-111.A). Нет git или репозитория — сигнала нет. */
function settingsTracked(root) {
  const r = spawnTool("git", ["-C", root, "ls-files", "--error-unmatch", SETTINGS_FILE], { encoding: "utf8" });
  return !r.error && r.status === 0;
}

/** Строка о действующем глобальном конфиге: и о втором файле, если он есть (F-122). */
function configNote() {
  const other = otherConfigPath();
  return `openspec: глобальный конфиг ${globalConfigPath()}${other ? `; есть ещё ${other}, он действует без XDG_CONFIG_HOME` : ""}`;
}

/** Python: `python`, затем `python3`; версия не закрепляется. Возвращает имя команды или null. */
export function findPython() {
  for (const cmd of ["python", "python3"]) {
    const r = spawnTool(cmd, ["--version"], { encoding: "utf8" });
    if (!r.error && r.status === 0) return cmd;
  }
  return null;
}

/**
 * Сверяет установку symphysis в проекте. Только называет расхождения, ничего не чинит.
 * `findings` — отказы (каждая строка начинается с имени файла или предмета); `notes` — сигналы (журналы).
 */
export function check(project, { skillsDirs = [], agentsDirs = [], payloadDir = DEFAULT_PAYLOAD, sourceRoot = ROOT } = {}) {
  const root = path.resolve(project);
  const t = targets(root, skillsDirs, agentsDirs);
  const findings = [];
  const notes = [];

  const fork = forkFinding();
  if (fork) findings.push(fork);

  // Запуск из клона: после `git pull` установка молча положила бы прежний payload (F-114.A).
  if (hasSources(sourceRoot) && !payloadMatches(payloadDir, sourceRoot)) findings.push("payload старее исходников — выполнить: npm --prefix installer ci");

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
  const agentsSrc = path.join(payloadDir, "agents");
  const agentNames = fs.existsSync(agentsSrc) ? fs.readdirSync(agentsSrc).filter((n) => /^symphysis-.*-driver\.md$/.test(n)) : [];
  for (const dir of t.agentsDirs) {
    for (const name of agentNames) {
      const f = path.join(dir, name);
      if (!fs.existsSync(f)) findings.push(`${rel(root, f)}: нет файла`);
    }
  }

  const toolsDir = path.join(t.toolsDir, "tools");
  const payloadDocs = path.join(payloadDir, "docs");
  const toolFiles = [
    ...TOOL_MODULES.map((m) => path.join(toolsDir, m)),
    // `docs/` payload целиком: общие файлы скиллов, уведомления MIT; схема журнала — в `tools/` (F-41 A).
    ...walk(payloadDocs).map((f) => path.join(t.toolsDir, "docs", path.relative(payloadDocs, f))),
    path.join(toolsDir, "journal-roots.json"),
  ];
  for (const f of toolFiles) if (!fs.existsSync(f)) findings.push(`${rel(root, f)}: нет файла`);
  // Страница работает и без файла, показывает схему текстом, поэтому это сигнал, а не находка (F-39, F-101).
  const mermaidFile = path.join(toolsDir, "mermaid.min.js");
  if (!fs.existsSync(mermaidFile)) notes.push(`${rel(root, mermaidFile)}: нет файла, страница покажет схему текстом; рисунок вернёт symphysis install`);

  const py = findPython();
  if (!py) findings.push("python: python или python3 не отвечает");

  const clientLines = continueLines(selectedClients(root, t.skillsDirs));
  findings.push(...clientLines.findings);
  notes.push(...clientLines.notes);

  settingsLines(root, py, path.join(toolsDir, "symphysis_config.py"), findings, notes);
  if (settingsTracked(root)) findings.push(`${SETTINGS_FILE}: отслеживается git — выполнить: git rm --cached ${SETTINGS_FILE}`);

  const changes = path.join(root, "openspec", "changes");
  const journalPy = path.join(toolsDir, "journal.py");
  if (py && fs.existsSync(journalPy) && fs.existsSync(changes)) {
    for (const e of fs.readdirSync(changes, { withFileTypes: true }).sort((a, b) => a.name.localeCompare(b.name))) {
      const j = path.join(changes, e.name, "decisions.json");
      if (!e.isDirectory() || !fs.existsSync(j)) continue;
      const r = spawnTool(py, ["-X", "utf8", journalPy, "check", j], { encoding: "utf8" });
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
        // Сигналы сверки и описи доходят до человека, код не меняют (F-78.A).
        for (const l of lines) if (l.startsWith("[!!] ")) notes.push(`${rel(root, j)}: ${l.slice(5)}`);
      }
    }
  }

  notes.push(configNote());

  const tele = telemetryState();
  if (tele === "off") notes.push("telemetry: выключена");
  else if (tele === "missing") notes.push("telemetry: конфиг OpenSpec не найден — появится после первого openspec init");
  else if (tele === "unreadable") notes.push("telemetry: конфиг OpenSpec не читается — форк в этом случае телеметрию выключает");
  else findings.push(`telemetry: включена — выключить: ${TELEMETRY_OFF_COMMAND}`);

  return { ok: findings.length === 0, findings, notes };
}
