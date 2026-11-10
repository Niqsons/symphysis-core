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
import { resolveRuntime } from "./runtime-resolver.js";
import { installationHash, readInstallationManifest, normalizeInstallationRequest } from "./installation-plan.js";
import { fileURLToPath } from "node:url";
import { clientTargets } from "./client-targets.js";
import { acquireReader } from "./runtime-leases.js";
import { evaluateClientReadiness } from "./client-readiness.js";

const SETTINGS_FILE = "symphysis.yaml";
const TOOL_MODULES = ["journal.py", "journal_apply.py", "journal_cli.py", "journal_model.py", "journal_render.py", "journal.schema.json", "roots.py", "runtime_context.py", "viewer_render.py", "attack_table.py", "attack_scope.py", "journal_sites.py", "journal_consequences.py", "symphysis_config.py", "openspec_run.py", "trace_graph.py", "anchor_refs.py", "sync_check.py"];

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
function forkFinding(env = process.env, run = runOpenspec) {
  const { openspecPin, openspecSource } = forkPin();
  const install = `npm i -g ./${openspecSource}`;
  const r = run(["--version"], { env });
  if (r.notFound) return `openspec: не найден (SYMPHYSIS_OPENSPEC или PATH); нужен форк ${openspecPin}: ${install}`;
  if (r.error || r.status !== 0) return `openspec: ${describeFailure(r).replace(/^openspec /, "")}; нужен форк ${openspecPin}: ${install}`;
  const actual = String(r.stdout).trim();
  return actual === openspecPin ? null : `openspec: версия ${actual}, нужна ${openspecPin} (форк symphysis): ${install}`;
}

/** Строки скрипта настроек: `[..]` — заметка, `[!!]` — находка. Файл инсталлятор сам не разбирает (F-135.B). */
function settingsLines(root, py, tool, findings, notes, env = process.env) {
  if (!fs.existsSync(path.join(root, SETTINGS_FILE))) {
    notes.push(`${SETTINGS_FILE}: нет файла, действует всё включено; создать: symphysis install`);
    return;
  }
  if (!py || !fs.existsSync(tool)) return;
  const r = spawnTool(py, ["-X", "utf8", tool, "--project", root, "--strict"], { encoding: "utf8", env });
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
function settingsTracked(root, env = process.env, file = SETTINGS_FILE) {
  const r = spawnTool("git", ["-C", root, "ls-files", "--error-unmatch", file], { encoding: "utf8", env });
  return !r.error && r.status === 0;
}
function trackedRoots(root, env, findings) {
  for (const file of [".symphysis/tools/journal-roots.json", "tools/journal-roots.json"]) if (settingsTracked(root, env, file)) findings.push(`${file}: отслеживается git — выполнить: git rm --cached ${file}`);
}

/** Строка о действующем глобальном конфиге: и о втором файле, если он есть (F-122). */
function configNote(env = process.env) {
  const other = otherConfigPath(env);
  return `openspec: глобальный конфиг ${globalConfigPath(env)}${other ? `; есть ещё ${other}, он действует без XDG_CONFIG_HOME` : ""}`;
}

/** Python: `python`, затем `python3`; версия не закрепляется. Возвращает имя команды или null. */
export function findPython(env = process.env) {
  for (const cmd of ["python", "python3"]) {
    const r = spawnTool(cmd, ["--version"], { encoding: "utf8", env });
    if (!r.error && r.status === 0) return cmd;
  }
  return null;
}

/**
 * Сверяет установку symphysis в проекте. Только называет расхождения, ничего не чинит.
 * `findings` — отказы (каждая строка начинается с имени файла или предмета); `notes` — сигналы (журналы).
 */
function checkLegacy(project, { skillsDirs = [], agentsDirs = [], payloadDir = DEFAULT_PAYLOAD, sourceRoot = ROOT, env = process.env, executeTools = true } = {}) {
  const root = path.resolve(project);
  const t = targets(root, skillsDirs, agentsDirs);
  const findings = [];
  const notes = [];

  const fork = forkFinding(env);
  if (fork) findings.push(fork);

  // Запуск из клона: после `git pull` установка молча положила бы прежний payload (F-114.A).
  if (fs.existsSync(sourceRoot) && hasSources(sourceRoot) && !payloadMatches(payloadDir, sourceRoot)) findings.push("payload старее исходников — выполнить: npm --prefix installer ci");

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

  const py = findPython(env);
  if (!py) findings.push("python: python или python3 не отвечает");

  const clientLines = continueLines(selectedClients(root, t.skillsDirs));
  findings.push(...clientLines.findings);
  notes.push(...clientLines.notes);

  if (executeTools) settingsLines(root, py, path.join(toolsDir, "symphysis_config.py"), findings, notes, env);
  if (settingsTracked(root, env)) findings.push(`${SETTINGS_FILE}: отслеживается git — выполнить: git rm --cached ${SETTINGS_FILE}`);
  trackedRoots(root, env, findings);

  const changes = path.join(root, "openspec", "changes");
  const journalPy = path.join(toolsDir, "journal.py");
  if (executeTools && py && fs.existsSync(journalPy) && fs.existsSync(changes)) {
    for (const e of fs.readdirSync(changes, { withFileTypes: true }).sort((a, b) => a.name.localeCompare(b.name))) {
      const j = path.join(changes, e.name, "decisions.json");
      if (!e.isDirectory() || !fs.existsSync(j)) continue;
      const r = spawnTool(py, ["-X", "utf8", journalPy, "check", j], { encoding: "utf8", env });
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

  notes.push(configNote(env));

  const tele = telemetryState(env);
  if (tele === "off") notes.push("telemetry: выключена");
  else if (tele === "missing") notes.push("telemetry: конфиг OpenSpec не найден — появится после первого openspec init");
  else if (tele === "unreadable") notes.push("telemetry: конфиг OpenSpec не читается — форк в этом случае телеметрию выключает");
  else findings.push(`telemetry: включена — выключить: ${TELEMETRY_OFF_COMMAND}`);

  return { ok: findings.length === 0, findings, notes };
}

/** Scope-aware, read-only check; file readiness never asserts native discovery. */
export function check(project, options = {}) {
  const { scope, env = process.env, store, run } = options;
  const root = path.resolve(project ?? process.cwd());
  if (scope !== undefined && !["local", "global"].includes(scope)) throw Object.assign(new Error("--scope: допустимы local либо global"), { exitCode: 2 });
  const context = resolveRuntime({ project: root, store, env, ...(run ? { run } : {}) });
  let lease;
  if (context.status === "ready") {
    try { lease = acquireReader(context); }
    catch (error) { context.status = "blocked"; context.diagnostics.push({ code: error.code, message: error.message, action: "Повтори check после завершения управления поставкой" }); }
  }
  try {
    if (context.scope === "local" && context.runtime?.legacy) {
      const result = checkLegacy(context.store.root, { ...options,
        skillsDirs: (options.skillsDirs ?? []).map((directory) => path.resolve(root, directory)),
        agentsDirs: (options.agentsDirs ?? []).map((directory) => path.resolve(root, directory)),
        executeTools: context.status === "ready" && (!scope || scope === "local"),
      });
      result.findings.push(...context.diagnostics.map((issue) => `${issue.code}: ${issue.message}; ${issue.action}`));
      if (scope && scope !== "local") result.findings.push(`--scope ${scope}: resolver выбрал local; требуется явная миграция`);
      result.findings = [...new Set(result.findings)];
      return { ...result, ok: result.findings.length === 0, clients: [], context };
    }
    return checkSelectedContext(context, root, options);
  }
  finally { lease?.release(); }
}

function checkSelectedContext(context, root, options) {
  const { scope, env = process.env, run, payloadDir = DEFAULT_PAYLOAD, sourceRoot = ROOT } = options;
  const findings = context.diagnostics.map((issue) => `${issue.code}: ${issue.message}; ${issue.action}`);
  const notes = [];
  const unavailable = new Set((context.warnings ?? []).map((warning) => warning.path).filter(Boolean));
  for (const warning of context.warnings ?? []) notes.push(`${warning.path && context.scope === "local" ? `${rel(context.store.root, warning.path)}: ` : ""}${warning.message}; ${warning.action}`);
  if (scope && context.scope && context.scope !== scope) findings.push(`--scope ${scope}: resolver выбрал ${context.scope}; смена режима требует явной миграции`);
  if (fs.existsSync(sourceRoot) && hasSources(sourceRoot) && !payloadMatches(payloadDir, sourceRoot)) findings.push("payload старее исходников — выполнить: npm --prefix installer ci");
  let manifest = null;
  if (context.runtime?.manifestPath) {
    try {
      const raw = JSON.parse(fs.readFileSync(context.runtime.manifestPath, "utf8"));
      const request = normalizeInstallationRequest({ ...raw, root: path.dirname(context.runtime.manifestPath) });
      manifest = readInstallationManifest(context.runtime.manifestPath, request);
    } catch (error) { findings.push(`manifest: ${error.message}`); }
  }
  const integrity = [];
  for (const file of manifest?.files ?? []) {
    if (unavailable.has(file.path) || (context.scope === "local" && file.source === "tools/symphysis-version.txt")) continue;
    const display = context.scope === "local" ? rel(context.store.root, file.path) : file.path;
    try {
      if (installationHash(fs.readFileSync(file.path)) !== file.sha256) integrity.push(file.source.startsWith("openspec/schemas/") ? `схема: байты отличаются от payload: ${display}` : `${display}: байты отличаются от manifest`);
    } catch (error) { integrity.push(`${display}: ${error.code === "ENOENT" ? "нет файла" : "файл не читается"}`); }
  }
  if (integrity.length) {
    for (let index = findings.length - 1; index >= 0; index--) if (/^(?:local-damaged|resource-missing):/.test(findings[index])) findings.splice(index, 1);
    findings.unshift(...integrity);
  }
  {
    const configRoot = context.store?.root ?? root;
    const config = ["config.yaml", "config.yml"].map((name) => path.join(configRoot, "openspec", name)).find((file) => fs.existsSync(file));
    if (!config && (context.runtime || fs.existsSync(path.join(root, ".symphysis", "install-manifest.json")))) findings.push("openspec/config.yaml: нет файла");
    else if (config) {
      try {
        const schema = parse(fs.readFileSync(config, "utf8"))?.schema;
        if (context.runtime && schema !== "symphysis") findings.push(`${rel(configRoot, config)}: schema не symphysis (${schema ?? "не задана"})`);
      } catch (error) { findings.push(`${rel(configRoot, config)}: не разбирается (${String(error.message).split("\n")[0]})`); }
    }
  }
  if (context.diagnostics.some((issue) => ["planning-root-invalid", "fork-incompatible"].includes(issue.code))) {
    const fork = forkFinding(env, run);
    if (fork) findings.unshift(fork);
  }
  const clients = evaluateClientReadiness(manifest);
  for (const client of clients) {
    const files = manifest.files.filter((file) => file.clientId === client.id);
    if (context.scope === "global") for (const file of client.missing) findings.push(`${client.id}: отсутствует или изменён ${file.path}`);
    for (const id of client.missingWorkflows) findings.push(`${client.id}: нет управляемого workflow ${id}`);
    if (!files.some((file) => file.purpose === "skill")) findings.push(`${client.id}: нет управляемых скиллов`);
    if (!files.some((file) => file.purpose === "agent")) findings.push(`${client.id}: нет управляемых агентов`);
    notes.push(`${client.id}: filesystem ${client.filesystem}; native discovery: unconfirmed; session verification: unconfirmed`);
  }
  if (manifest && !clients.length) findings.push("clients: нет управляемых клиентских targets");
  if ((options.clients?.length || options.skillsDirs?.length || options.agentsDirs?.length) && context.scope) {
    const requested = clientTargets({ scope: context.scope, project: context.store.root, clients: options.clients ?? [], skillsDirs: options.skillsDirs ?? [], agentsDirs: options.agentsDirs ?? [], env });
    for (const client of requested) {
      const installed = manifest?.clients.find((item) => item.id === client.id);
      if (!installed) { findings.push(`${client.id}: клиент не входит в выбранную управляемую поставку`); continue; }
      for (const kind of ["skills", "agents"]) for (const target of client[`${kind}Roots`]) if (!(installed[`${kind}Roots`] ?? []).some((root) => path.relative(root, target) === "")) findings.push(`${client.id}: ${target} не входит в управляемые ${kind} targets`);
    }
  }
  if (!findPython(env)) findings.push("python: python или python3 не отвечает");
  if (context.status === "ready" && (!scope || scope === context.scope)) {
    const bin = fileURLToPath(new URL("../bin/symphysis.js", import.meta.url));
    const selected = ["--project", context.store.root];
    const invoke = (tool, args) => spawnTool(process.execPath, [bin, ...selected, tool, ...args], { encoding: "utf8", env });
    if (fs.existsSync(path.join(context.store.root, SETTINGS_FILE))) {
      const result = invoke("config", ["--strict"]);
      for (const line of String(result.stdout ?? "").split(/\r?\n/)) {
        if (line.startsWith("[!!] ")) findings.push(line.slice(5));
        if (line.startsWith("[..] ")) notes.push(line.slice(5));
      }
      if (result.error || ![0, 2].includes(result.status) || (result.status === 2 && !String(result.stdout).includes("[!!] "))) findings.push(`settings: dispatcher не проверил настройки выбранного store (${String(result.stderr || result.error?.message || result.status).trim()})`);
    } else notes.push(`symphysis.yaml: нет файла, действует всё включено; создать: symphysis ${context.scope === "local" ? "install" : "init"}`);
    if (settingsTracked(context.store.root, env)) findings.push(`${SETTINGS_FILE}: отслеживается git — выполнить: git rm --cached ${SETTINGS_FILE}`);
    trackedRoots(context.store.root, env, findings);
    const changes = path.join(context.store.root, "openspec", "changes");
    if (fs.existsSync(changes)) for (const entry of fs.readdirSync(changes, { withFileTypes: true })) {
      const journal = path.join(changes, entry.name, "decisions.json");
      if (!entry.isDirectory() || !fs.existsSync(journal)) continue;
      const result = invoke("journal", ["check", journal]);
      const relative = rel(context.store.root, journal);
      if (result.error || result.status !== 0) {
        const errorText = String(result.stderr ?? "");
        if (!result.error && errorText.includes("[!!]")) findings.push(`${relative}: журнал негоден по схеме`);
        else findings.push(`${relative}: journal.py check не отработал (${String(result.error?.message ?? errorText.split(/\r?\n/).find((line) => line.trim()) ?? result.status).trim()})`);
      } else {
        const lines = String(result.stdout).split(/\r?\n/).filter(Boolean);
        notes.push(`${relative}: ${lines.find((line) => line.includes("улик сверено")) ?? ""}`);
        for (const line of lines) if (line.startsWith("[!!] ")) notes.push(`${relative}: ${line.slice(5)}`);
      }
    }
  }
  notes.push(configNote(env));
  const telemetry = telemetryState(env);
  if (telemetry === "off") notes.push("telemetry: выключена");
  else if (telemetry === "missing") notes.push("telemetry: конфиг OpenSpec не найден — появится после первого openspec init");
  else if (telemetry === "unreadable") notes.push("telemetry: конфиг OpenSpec не читается — форк в этом случае телеметрию выключает");
  else findings.push(`telemetry: включена — выключить: ${TELEMETRY_OFF_COMMAND}`);
  return { ok: findings.length === 0, findings: [...new Set(findings)], notes, clients, context };
}
