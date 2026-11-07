import { test, before, afterEach } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { syncPayload } from "../scripts/sync-payload.js";
import { targets } from "../lib/paths.js";
import { install } from "../lib/install.js";
import { check } from "../lib/check.js";
import { requireFork } from "../scripts/build-vendor.js";
import { tempDir } from "../test-support/temp-dir.js";
import { makeClone } from "../test-support/clone.js";

const here = path.dirname(fileURLToPath(import.meta.url));
const bin = path.resolve(here, "..", "bin", "symphysis.js");
const FORK = path.resolve(here, "..", "..", "upstream", "openspec", "bin", "openspec.js");
const PIN = "1.16.1+symphysis.5";
let payloadDir;
const tmp = () => tempDir("symphysis-check-");
const saved = { openspec: process.env.SYMPHYSIS_OPENSPEC, path: process.env.PATH, Path: process.env.Path, xdg: process.env.XDG_CONFIG_HOME };
const cfgFile = () => path.join(process.env.XDG_CONFIG_HOME, "openspec", "config.json");
// Сценарии о строках скрипта настроек требуют PyYAML у `python` из PATH; остальным файл настроек не нужен.
const withYaml = { skip: spawnSync("python", ["-c", "import yaml"]).status === 0 ? false : "у python из PATH нет PyYAML: python -m pip install pyyaml" };
const writeCfg = (obj) => {
  fs.mkdirSync(path.dirname(cfgFile()), { recursive: true });
  fs.writeFileSync(cfgFile(), JSON.stringify(obj));
};

before(() => {
  requireFork(FORK);
  payloadDir = tmp();
  syncPayload(payloadDir);
});

afterEach(() => {
  for (const [k, v] of [["SYMPHYSIS_OPENSPEC", saved.openspec], ["PATH", saved.path], ["Path", saved.Path], ["XDG_CONFIG_HOME", saved.xdg]]) {
    if (v === undefined) delete process.env[k];
    else process.env[k] = v;
  }
});

// Глобальный конфиг форка — всегда временный каталог: настоящий конфиг пользователя тесты не трогают.
function installedWithSettings() {
  process.env.XDG_CONFIG_HOME = tmp();
  process.env.SYMPHYSIS_OPENSPEC = FORK;
  const p = tmp();
  // Клиент настроен: файл команды форка; сценарии о самой команде живут ниже.
  fs.mkdirSync(path.join(p, ".claude", "commands", "opsx"), { recursive: true });
  fs.writeFileSync(path.join(p, ".claude", "commands", "opsx", "continue.md"), "x");
  install(p, { payloadDir });
  return p;
}
/** Установка без файла настроек: строки скрипта и PyYAML этим тестам ни к чему. */
function installed() {
  const p = installedWithSettings();
  fs.rmSync(path.join(p, "symphysis.yaml"));
  return p;
}
const runCheck = (p) => check(p, { payloadDir });
const cli = (...args) => spawnSync(process.execPath, [bin, ...args], { encoding: "utf8", env: process.env });

const MINIMAL_JOURNAL = {
  title: "т",
  source: "s.md",
  records: [
    {
      id: "F-01", question: "вопрос?", kind: "развилка", status: "открыт", addressee: "", depends_on: [], delivery: "",
      options: [{ letter: "A", text: "вариант", added: false, unlikely: null, evidence: [{ path: "x.md", quote: "q" }] }],
      antipodes: [], recommendation: null, decision: null, reversibility: null, outcome: null,
      parking: [], dispute: "", consequences: "", evidence: [], comments: [],
    },
  ],
};

test("после install: ok, находок нет, заметки — состав, конфиг и телеметрия", withYaml, () => {
  const p = installedWithSettings();
  const r = runCheck(p);
  assert.deepEqual(r.findings, []);
  assert.equal(r.ok, true);
  assert.ok(r.notes.includes("symphysis.yaml: ветки отказа вкл, допущения вкл, проба краёв вкл, водители: атака вкл, пробы выкл, опись выкл, исследование вкл"), JSON.stringify(r.notes));
  assert.ok(r.notes.some((n) => n.startsWith(`openspec: глобальный конфиг ${cfgFile()}`)), JSON.stringify(r.notes));
  assert.ok(r.notes.includes("telemetry: выключена"), JSON.stringify(r.notes));
});

test("байт схемы подменён: findings[0] называет schema.yaml", () => {
  const p = installed();
  const f = path.join(targets(p).schemaDir, "schema.yaml");
  const b = fs.readFileSync(f);
  b[b.length - 1] ^= 1;
  fs.writeFileSync(f, b);
  const r = runCheck(p);
  assert.equal(r.ok, false);
  assert.equal(r.findings[0], "схема: байты отличаются от payload: openspec/schemas/symphysis/schema.yaml");
  assert.deepEqual(fs.readFileSync(f), b, "гейт не чинит");
});

test("файл схемы удалён: нет файла", () => {
  const p = installed();
  fs.rmSync(path.join(targets(p).schemaDir, "schema.yaml"));
  const r = runCheck(p);
  assert.ok(r.findings.some((f) => /openspec\/schemas\/symphysis\/schema\.yaml: нет файла/.test(f)), JSON.stringify(r.findings));
});

test("config без schema / с чужой / отсутствует", () => {
  const p = installed();
  const cfg = targets(p).configPath;
  fs.writeFileSync(cfg, fs.readFileSync(cfg, "utf8").replace(/^schema: symphysis\r?\n/m, ""));
  let r = runCheck(p);
  assert.ok(r.findings.some((f) => f.startsWith("openspec/config.yaml: schema не symphysis")), JSON.stringify(r.findings));
  fs.writeFileSync(cfg, "schema: spec-driven\n");
  r = runCheck(p);
  assert.ok(r.findings.some((f) => f === "openspec/config.yaml: schema не symphysis (spec-driven)"), JSON.stringify(r.findings));
  fs.rmSync(cfg);
  r = runCheck(p);
  assert.ok(r.findings.includes("openspec/config.yaml: нет файла"), JSON.stringify(r.findings));
});

test("удалён SKILL.md: finding называет его", () => {
  const p = installed();
  fs.rmSync(path.join(targets(p).skillsDirs[0], "symphysis-attack", "SKILL.md"));
  const r = runCheck(p);
  assert.ok(r.findings.includes(".claude/skills/symphysis-attack/SKILL.md: нет файла"), JSON.stringify(r.findings));
});

test("удалено тело агента: finding называет его", () => {
  const p = installed();
  fs.rmSync(path.join(targets(p).agentsDirs[0], "symphysis-research-driver.md"));
  const r = runCheck(p);
  assert.ok(r.findings.includes(".claude/agents/symphysis-research-driver.md: нет файла"), JSON.stringify(r.findings));
});

test("скиллы проверяются в каждом skillsDir", () => {
  process.env.XDG_CONFIG_HOME = tmp();
  process.env.SYMPHYSIS_OPENSPEC = FORK;
  const p = tmp();
  fs.mkdirSync(path.join(p, "a", "commands", "opsx"), { recursive: true });
  fs.writeFileSync(path.join(p, "a", "commands", "opsx", "continue.md"), "x");
  install(p, { payloadDir, skillsDirs: ["a/skills", "b/skills"] });
  fs.rmSync(path.join(p, "symphysis.yaml"));
  fs.rmSync(path.join(p, "b", "skills", "symphysis-brainstorm", "SKILL.md"));
  const r = check(p, { payloadDir, skillsDirs: ["a/skills", "b/skills"] });
  assert.deepEqual(r.findings, ["b/skills/symphysis-brainstorm/SKILL.md: нет файла"]);
});

test("инструменты: нет journal.py, схемы json, корней", () => {
  const p = installed();
  const t = targets(p).toolsDir;
  fs.rmSync(path.join(t, "tools", "journal.py"));
  fs.rmSync(path.join(t, "tools", "journal.schema.json"));
  fs.rmSync(path.join(t, "tools", "journal-roots.json"));
  const r = runCheck(p);
  for (const f of [".symphysis/tools/journal.py", ".symphysis/tools/journal.schema.json", ".symphysis/tools/journal-roots.json"]) {
    assert.ok(r.findings.includes(`${f}: нет файла`), `${f}: ${JSON.stringify(r.findings)}`);
  }
});

test("общие файлы docs: нет terms.md или уведомлений — finding называет файл", () => {
  const p = installed();
  const t = targets(p).toolsDir;
  fs.rmSync(path.join(t, "docs", "terms.md"));
  fs.rmSync(path.join(t, "docs", "THIRD-PARTY-NOTICES.md"));
  const r = runCheck(p);
  for (const f of [".symphysis/docs/terms.md", ".symphysis/docs/THIRD-PARTY-NOTICES.md"]) {
    assert.ok(r.findings.includes(`${f}: нет файла`), `${f}: ${JSON.stringify(r.findings)}`);
  }
});

test("инструменты: каждый модуль из состава проверяется, три новых тоже", () => {
  const modules = ["journal_apply.py", "journal_cli.py", "journal_model.py", "journal_render.py", "roots.py", "viewer_render.py", "attack_table.py", "attack_scope.py", "journal_sites.py", "journal_consequences.py", "symphysis_config.py"];
  const p = installed();
  const t = targets(p).toolsDir;
  for (const m of modules) fs.rmSync(path.join(t, "tools", m));
  const r = runCheck(p);
  for (const m of modules) {
    assert.ok(r.findings.includes(`.symphysis/tools/${m}: нет файла`), `${m}: ${JSON.stringify(r.findings)}`);
  }
});

test("`project-installer`: «Скрипта нет при проверке установки»: находка называет файл и «нет файла» (F-126)", () => {
  const p = installed();
  const t = targets(p).toolsDir;
  for (const m of ["trace_graph.py", "openspec_run.py", "anchor_refs.py"]) fs.rmSync(path.join(t, "tools", m));
  const r = runCheck(p);
  for (const m of ["trace_graph.py", "openspec_run.py", "anchor_refs.py"]) assert.ok(r.findings.includes(`.symphysis/tools/${m}: нет файла`), `${m}: ${JSON.stringify(r.findings)}`);
  assert.equal(r.ok, false);
});

test("`project-installer`: «Скрипта нет при проверке установки»: CLI check даёт код 2", () => {
  const p = installed();
  fs.rmSync(path.join(targets(p).toolsDir, "tools", "trace_graph.py"));
  const r = spawnSync(process.execPath, [bin, "check", "--project", p], { encoding: "utf8", env: { ...process.env, SYMPHYSIS_OPENSPEC: FORK } });
  assert.equal(r.status, 2, r.stdout + r.stderr);
  assert.ok(r.stdout.includes(".symphysis/tools/trace_graph.py: нет файла"), r.stdout);
});

test("`trace-snapshot`: «Проверка установки»: архив с изменением без graph/ строки не даёт (F-62)", () => {
  const p = installed();
  const dir = path.join(p, "openspec", "changes", "archive", "2026-11-01-old-change");
  fs.mkdirSync(dir, { recursive: true });
  fs.writeFileSync(path.join(dir, "proposal.md"), "# old\n");
  const before = runCheck(p);
  const all = [...before.findings, ...before.notes].join("\n");
  assert.ok(!/old-change|archive|graph|снимк/i.test(all), all);
  assert.ok(!fs.existsSync(path.join(dir, "graph")));
});

test("версия не пин: finding с обеими версиями", () => {
  const p = installed();
  const fake = path.join(tmp(), "fake.js");
  fs.writeFileSync(fake, 'console.log("1.15.0");\n');
  process.env.SYMPHYSIS_OPENSPEC = fake;
  const r = runCheck(p);
  assert.ok(r.findings.some((f) => f.includes(`openspec: версия 1.15.0, нужна ${PIN}`)), JSON.stringify(r.findings));
});

test("бинаря нет ни в окружении, ни в PATH: не найден", () => {
  const p = installed();
  delete process.env.SYMPHYSIS_OPENSPEC;
  process.env.PATH = tmp();
  process.env.Path = process.env.PATH;
  const r = runCheck(p);
  assert.ok(r.findings.some((f) => f.startsWith("openspec: не найден (SYMPHYSIS_OPENSPEC или PATH)") && f.includes(PIN)), JSON.stringify(r.findings));
});

test("python: находится по имени python, версия не закреплена", () => {
  const found = spawnSync("python", ["-c", "import sys; print(sys.executable)"], { encoding: "utf8" });
  assert.equal(found.status, 0, "нет python в PATH: тест не прогнать");
  const p = installed();
  const one = path.join(p, "openspec", "changes", "one");
  fs.mkdirSync(one, { recursive: true });
  fs.writeFileSync(path.join(one, "decisions.json"), JSON.stringify(MINIMAL_JOURNAL));
  // В PATH только каталог настоящего python: других имён интерпретатора там нет.
  process.env.PATH = path.dirname(found.stdout.trim());
  process.env.Path = process.env.PATH;
  const r = runCheck(p);
  assert.ok(!r.findings.some((f) => f.startsWith("python:")), JSON.stringify(r.findings));
  assert.match(r.notes.find((n) => n.startsWith("openspec/changes/one/decisions.json: ")) ?? "", /улик сверено/);
});

test("python не найден: finding называет имена без версии", () => {
  const p = installed();
  process.env.PATH = tmp();
  process.env.Path = process.env.PATH;
  const r = runCheck(p);
  assert.ok(r.findings.includes("python: python или python3 не отвечает"), JSON.stringify(r.findings));
});

test("журнал: годный даёт note, негодный — finding", () => {
  const p = installed();
  const good = path.join(p, "openspec", "changes", "one");
  fs.mkdirSync(good, { recursive: true });
  fs.writeFileSync(path.join(good, "decisions.json"), JSON.stringify(MINIMAL_JOURNAL));
  let r = runCheck(p);
  assert.equal(r.ok, true, JSON.stringify(r.findings));
  const note = r.notes.find((n) => n.startsWith("openspec/changes/one/decisions.json: "));
  assert.match(note, /улик сверено/);

  const bad = path.join(p, "openspec", "changes", "two");
  fs.mkdirSync(bad, { recursive: true });
  fs.writeFileSync(path.join(bad, "decisions.json"), "{}");
  r = runCheck(p);
  assert.equal(r.ok, false);
  assert.ok(r.findings.includes("openspec/changes/two/decisions.json: журнал негоден по схеме"), JSON.stringify(r.findings));
});

test("журнал не JSON: finding «не отработал», а не «негоден по схеме»", () => {
  const p = installed();
  const bad = path.join(p, "openspec", "changes", "broken");
  fs.mkdirSync(bad, { recursive: true });
  fs.writeFileSync(path.join(bad, "decisions.json"), "{");
  const r = runCheck(p);
  const f = r.findings.find((x) => x.startsWith("openspec/changes/broken/decisions.json:"));
  assert.ok(f && f.includes("journal.py check не отработал"), JSON.stringify(r.findings));
});

test("CLI: check ok — код 0, «check: ok»; после правки схемы — код 2 и [!!]", () => {
  const p = installed();
  let r = cli("check", "--project", p);
  assert.equal(r.status, 0, r.stdout + r.stderr);
  assert.match(r.stdout, /^check: ok$/m);
  const f = path.join(targets(p).schemaDir, "schema.yaml");
  fs.appendFileSync(f, "# x\n");
  r = cli("check", "--project", p);
  assert.equal(r.status, 2);
  assert.match(r.stdout, /^\[!!\] схема: байты отличаются от payload: openspec\/schemas\/symphysis\/schema\.yaml$/m);
  assert.match(r.stdout, /^check: 1 расхождений$/m);
});

test("CLI: расхождение байтов схемы — [!!] с путём файла, код 2", () => {
  const p = installed();
  const rel = "openspec/schemas/symphysis/templates/intent.md";
  fs.appendFileSync(path.join(p, rel), "x");
  const r = cli("check", "--project", p);
  assert.equal(r.status, 2);
  assert.ok(r.stdout.split(/\r?\n/).includes(`[!!] схема: байты отличаются от payload: ${rel}`), r.stdout);
});

test("telemetry: install выключил — [..] выключена, код 0", () => {
  const p = installed();
  assert.equal(JSON.parse(fs.readFileSync(cfgFile(), "utf8")).telemetry.enabled, false);
  const r = cli("check", "--project", p);
  assert.equal(r.status, 0, r.stdout);
  assert.match(r.stdout, /^\[\.\.\] telemetry: выключена$/m);
});

test("telemetry: конфига OpenSpec нет — сигнал, код 0", () => {
  const p = installed();
  fs.rmSync(cfgFile());
  const r = cli("check", "--project", p);
  assert.equal(r.status, 0, r.stdout);
  assert.match(r.stdout, /^\[\.\.\] telemetry: конфиг OpenSpec не найден — появится после первого openspec init$/m);
});

test("telemetry: включена — [!!] с командой, код 2; ключ не задан — то же", () => {
  const p = installed();
  const line = /^\[!!\] telemetry: включена — выключить: openspec config set telemetry\.enabled false$/m;
  writeCfg({ telemetry: { enabled: true, anonymousId: "00000000-0000-4000-8000-000000000000" } });
  let r = cli("check", "--project", p);
  assert.equal(r.status, 2, r.stdout);
  assert.match(r.stdout, line);
  writeCfg({ profile: "core" });
  r = cli("check", "--project", p);
  assert.equal(r.status, 2);
  assert.match(r.stdout, line);
});

test("telemetry: конфиг не JSON — сигнал, код 0", () => {
  const p = installed();
  fs.writeFileSync(cfgFile(), "{");
  const r = cli("check", "--project", p);
  assert.equal(r.status, 0, r.stdout);
  assert.match(r.stdout, /^\[\.\.\] telemetry: конфиг OpenSpec не читается/m);
});

// --- /opsx:continue у выбранного клиента ------------------------------------

const CONTINUE_MISSING = "continue: команда /opsx:continue не установлена у claude — выполнить: symphysis install";
const CLIENT_NOT_SET = "continue: клиент не настроен — выполнить: openspec init --tools claude";

/** Установка без файлов клиента: схема цела, команды нет. */
function bareInstalled(skillsDirs = []) {
  process.env.XDG_CONFIG_HOME = tmp();
  process.env.SYMPHYSIS_OPENSPEC = FORK;
  const p = tmp();
  install(p, { payloadDir, skillsDirs });
  return p;
}

test("Команды нет: клиент настроен, а команды и скилла нет — [!!] с именем клиента, код 2", () => {
  const p = bareInstalled();
  fs.mkdirSync(path.join(p, ".claude", "skills", "openspec-apply-change"));
  const r = cli("check", "--project", p);
  assert.equal(r.status, 2, r.stdout);
  assert.ok(r.stdout.split(/\r?\n/).includes(`[!!] ${CONTINUE_MISSING}`), r.stdout);
});

test("Команда есть: строки [!!] continue нет", () => {
  const p = installed();
  const r = cli("check", "--project", p);
  assert.equal(r.status, 0, r.stdout);
  assert.doesNotMatch(r.stdout, /continue:/);
});

test("Команда у настроенного клиента: скилл считается установкой, клиент — имя каталога без точки", () => {
  const p = bareInstalled();
  const skill = path.join(p, ".claude", "skills", "openspec-continue-change");
  fs.mkdirSync(skill);
  fs.writeFileSync(path.join(skill, "SKILL.md"), "x");
  assert.ok(!runCheck(p).findings.some((f) => f.startsWith("continue:")));
  const other = bareInstalled([".opencode/skills"]);
  fs.mkdirSync(path.join(other, ".opencode", "commands", "opsx"), { recursive: true });
  const r = check(other, { payloadDir, skillsDirs: [".opencode/skills"] });
  assert.ok(r.findings.includes("continue: команда /opsx:continue не установлена у opencode — выполнить: symphysis install"), JSON.stringify(r.findings));
});

test("Два каталога: команда у .claude, файлов форка у .agents нет — заметка, а не [!!]", () => {
  const dirs = [".claude/skills", ".agents/skills"];
  const p = bareInstalled(dirs);
  fs.mkdirSync(path.join(p, ".claude", "commands", "opsx"), { recursive: true });
  fs.writeFileSync(path.join(p, ".claude", "commands", "opsx", "continue.md"), "x");
  const r = check(p, { payloadDir, skillsDirs: dirs });
  assert.ok(!r.findings.some((f) => f.startsWith("continue:")), JSON.stringify(r.findings));
  assert.ok(r.notes.includes(".agents: файлов форка нет, туда поставлены только скиллы symphysis"), JSON.stringify(r.notes));
});

test("Два каталога: команды нет ни в одном — один [!!], клиент без файлов форка заметкой", () => {
  const dirs = [".claude/skills", ".agents/skills"];
  const p = bareInstalled(dirs);
  fs.mkdirSync(path.join(p, ".claude", "commands", "opsx"), { recursive: true });
  const r = check(p, { payloadDir, skillsDirs: dirs });
  assert.deepEqual(r.findings.filter((f) => f.startsWith("continue:")), [CONTINUE_MISSING]);
  assert.ok(r.notes.includes(".agents: файлов форка нет, туда поставлены только скиллы symphysis"), JSON.stringify(r.notes));
});

test("Клиент не настроен: своя строка, код 2, подсказка where.exe и which; клиентов сам не ищет", () => {
  const p = bareInstalled();
  const r = cli("check", "--project", p);
  assert.equal(r.status, 2, r.stdout);
  const out = r.stdout.split(/\r?\n/);
  assert.ok(out.includes(`[!!] ${CLIENT_NOT_SET}`), r.stdout);
  const hint = out.find((l) => l.startsWith("[..] continue: "));
  assert.ok(hint, r.stdout);
  for (const s of ["where.exe claude", "where.exe opencode", "which", "--skills-dir"]) assert.ok(hint.includes(s), `${s}: ${hint}`);
});

// --- symphysis.yaml ---------------------------------------------------------

const settings = (p) => path.join(p, "symphysis.yaml");
const ALL_ON = "symphysis.yaml: ветки отказа вкл, допущения вкл, проба краёв вкл, водители: атака вкл, пробы выкл, опись выкл, исследование вкл";

test("Годный файл: [..] с составом, код 0", withYaml, () => {
  const p = installed();
  fs.writeFileSync(settings(p), "consequences:\n  assumptions: false\n");
  const r = cli("check", "--project", p);
  assert.equal(r.status, 0, r.stdout);
  assert.ok(r.stdout.split(/\r?\n/).includes("[..] symphysis.yaml: ветки отказа вкл, допущения выкл, проба краёв вкл, водители: атака вкл, пробы выкл, опись выкл, исследование вкл"), r.stdout);
});

test("Неизвестная линза: [!!] от скрипта, код 2, линзы не выключены", withYaml, () => {
  // `project-settings`: «Неизвестная линза» (F-108)
  const p = installed();
  fs.writeFileSync(settings(p), "attack:\n  trace-lnik: false\n");
  const r = cli("check", "--project", p);
  assert.equal(r.status, 2, r.stdout);
  const out = r.stdout.split(/\r?\n/);
  assert.ok(out.includes("[!!] symphysis.yaml: неизвестная линза trace-lnik"), r.stdout);
  assert.ok(out.some((l) => l.startsWith("[..] symphysis.yaml: линзы атаки: ") && !l.includes("выкл")), r.stdout);
});

test("Опечатка в ключе: [!!] от скрипта, код 2", withYaml, () => {
  const p = installed();
  fs.writeFileSync(settings(p), "edge-probe:\n  enabled: false\n");
  const r = cli("check", "--project", p);
  assert.equal(r.status, 2, r.stdout);
  assert.ok(r.stdout.split(/\r?\n/).includes("[!!] symphysis.yaml: неизвестный ключ edge-probe"), r.stdout);
  assert.ok(r.stdout.split(/\r?\n/).includes(`[..] ${ALL_ON}`), r.stdout);
});

for (const [name, text, line] of [
  ["недопустимое значение", "edge_probe:\n  enabled: no\n", "symphysis.yaml: недопустимое значение no"],
  ["файл не разбирается", "edge_probe:\n\tenabled: false\n", "symphysis.yaml: не разбирается"],
  ["плоская запись", "edge_probe: false\n", "symphysis.yaml: edge_probe — нужен вложенный ключ"],
]) {
  test(`Настройки: ${name} — [!!], код 2, выбор включён`, withYaml, () => {
    const p = installed();
    fs.writeFileSync(settings(p), text);
    const r = runCheck(p);
    assert.equal(r.ok, false);
    assert.ok(r.findings.includes(line), JSON.stringify(r.findings));
    assert.ok(r.notes.includes(ALL_ON), JSON.stringify(r.notes));
  });
}

test("Файла настроек нет: заметка из сценария, код не меняется, скрипт не нужен", () => {
  const p = installed();
  fs.writeFileSync(path.join(targets(p).toolsDir, "tools", "symphysis_config.py"), 'raise SystemExit("не должен зваться")\n');
  const r = cli("check", "--project", p);
  assert.equal(r.status, 0, r.stdout);
  assert.ok(r.stdout.split(/\r?\n/).includes("[..] symphysis.yaml: нет файла, действует всё включено; создать: symphysis install"), r.stdout);
});

test("BOM принимается: состав прочитан, код 0", withYaml, () => {
  const p = installed();
  fs.writeFileSync(settings(p), Buffer.concat([Buffer.from([0xef, 0xbb, 0xbf]), Buffer.from("edge_probe:\n  enabled: false\n")]));
  const r = cli("check", "--project", p);
  assert.equal(r.status, 0, r.stdout);
  assert.match(r.stdout, /проба краёв выкл/);
});

test("Не UTF-8: [!!] symphysis.yaml: не UTF-8, код 2", () => {
  const p = installed();
  fs.writeFileSync(settings(p), Buffer.concat([Buffer.from("edge_probe:\n  enabled: "), Buffer.from([0xe2, 0xfb, 0xea]), Buffer.from("\n")]));
  const r = cli("check", "--project", p);
  assert.equal(r.status, 2, r.stdout);
  assert.ok(r.stdout.split(/\r?\n/).includes("[!!] symphysis.yaml: не UTF-8"), r.stdout);
});

test("Скрипт настроек упал: [!!] с причиной, файл инсталлятор сам не разбирает", () => {
  const p = installedWithSettings();
  fs.writeFileSync(path.join(targets(p).toolsDir, "tools", "symphysis_config.py"), 'raise SystemExit("сломан")\n');
  const r = runCheck(p);
  assert.ok(r.findings.includes("symphysis_config.py: не отработал (сломан)"), JSON.stringify(r.findings));
  assert.ok(!r.notes.some((n) => n.startsWith("symphysis.yaml:")), JSON.stringify(r.notes));
});

test("Python нет: прежняя находка, строки состава нет", () => {
  const p = installedWithSettings();
  process.env.PATH = tmp();
  process.env.Path = process.env.PATH;
  const r = runCheck(p);
  assert.ok(r.findings.includes("python: python или python3 не отвечает"), JSON.stringify(r.findings));
  assert.ok(!r.notes.some((n) => n.startsWith("symphysis.yaml:")), JSON.stringify(r.notes));
});

test("У найденного Python нет PyYAML: состав всё включено и [!!] с командой, код 2", () => {
  const venv = tmp();
  const made = spawnSync("python", ["-m", "venv", "--without-pip", venv], { encoding: "utf8" });
  assert.equal(made.status, 0, made.stdout + made.stderr);
  const p = installed();
  fs.writeFileSync(settings(p), "edge_probe:\n  enabled: false\n");
  const env = { ...process.env, SYMPHYSIS_OPENSPEC: FORK };
  for (const k of Object.keys(env)) if (k.toLowerCase() === "path") delete env[k];
  env[process.platform === "win32" ? "Path" : "PATH"] = path.join(venv, process.platform === "win32" ? "Scripts" : "bin");
  const r = spawnSync(process.execPath, [bin, "check", "--project", p], { encoding: "utf8", env });
  assert.equal(r.status, 2, r.stdout + r.stderr);
  const out = r.stdout.split(/\r?\n/);
  assert.ok(out.includes(`[..] ${ALL_ON}`), r.stdout);
  assert.ok(out.includes("[!!] symphysis.yaml: нет пакета PyYAML — выполнить: python -m pip install pyyaml"), r.stdout);
});

test("Файл уже отслеживается git: [!!] с командой, код 2", () => {
  const p = installedWithSettings();
  const noConfig = path.join(tmp(), "gitconfig");
  fs.writeFileSync(noConfig, "");
  const gitEnv = { ...process.env, GIT_CONFIG_GLOBAL: noConfig, GIT_CONFIG_NOSYSTEM: "1" };
  const git = (...a) => assert.equal(spawnSync("git", ["-c", "user.name=t", "-c", "user.email=t@t", ...a], { cwd: p, encoding: "utf8", env: gitEnv }).status, 0, a.join(" "));
  git("init", "-q");
  git("add", "-f", "symphysis.yaml");
  git("commit", "-qm", "ошибка");
  const r = cli("check", "--project", p);
  assert.equal(r.status, 2, r.stdout);
  assert.ok(r.stdout.split(/\r?\n/).includes("[!!] symphysis.yaml: отслеживается git — выполнить: git rm --cached symphysis.yaml"), r.stdout);
  git("rm", "-q", "--cached", "symphysis.yaml");
  assert.doesNotMatch(cli("check", "--project", p).stdout, /отслеживается git/);
});

// --- payload и исходники ----------------------------------------------------

const STALE_PAYLOAD = "payload старее исходников — выполнить: npm --prefix installer ci";

test("payload старее исходников: [!!] при запуске из клона", () => {
  const p = installed();
  const old = tmp();
  syncPayload(old);
  fs.appendFileSync(path.join(old, "tools", "journal.py"), "# прежняя версия\n");
  const r = check(p, { payloadDir: old });
  assert.ok(r.findings.includes(STALE_PAYLOAD), JSON.stringify(r.findings));
});

test("payload старее исходников: лишний файл в payload тоже расхождение", () => {
  const p = installed();
  const old = tmp();
  syncPayload(old);
  fs.writeFileSync(path.join(old, "tools", "journal_old.py"), "x");
  assert.ok(check(p, { payloadDir: old }).findings.includes(STALE_PAYLOAD));
});

test("Клон в модульной раскладке: без skills/ check из клона сигналит устаревший payload, код 2 (F-60)", () => {
  const clone = makeClone(tmp(), { git: false });
  assert.equal(fs.existsSync(path.join(clone, "skills")), false);
  // Инсталлятор клона: его ROOT — клон, payload по умолчанию — `installer/payload` клона.
  const inst = path.join(clone, "installer");
  for (const rel of ["bin", "lib", "scripts", "package.json"]) fs.cpSync(path.join(here, "..", rel), path.join(inst, rel), { recursive: true });
  fs.cpSync(path.join(here, "..", "node_modules", "yaml"), path.join(inst, "node_modules", "yaml"), { recursive: true });
  syncPayload(path.join(inst, "payload"), clone);
  fs.appendFileSync(path.join(clone, "cli", "journal.py"), "\n# новее payload\n");
  const p = installed();
  const r = spawnSync(process.execPath, [path.join(inst, "bin", "symphysis.js"), "check", "--project", p], { encoding: "utf8", env: process.env });
  assert.equal(r.status, 2, r.stdout + r.stderr);
  assert.ok(r.stdout.split(/\r?\n/).includes(`[!!] ${STALE_PAYLOAD}`), r.stdout);
});

test("Инсталлятор не из клона: сверки нет, строки о payload нет", () => {
  const p = installed();
  const old = tmp();
  syncPayload(old);
  fs.appendFileSync(path.join(old, "tools", "journal.py"), "# прежняя версия\n");
  const r = check(p, { payloadDir: old, sourceRoot: tmp() });
  assert.ok(!r.findings.some((f) => f.includes("payload")), JSON.stringify(r.findings));
});

// --- глобальный конфиг ------------------------------------------------------

/** Окружение одной команды: каталог, где конфиг лежит без XDG_CONFIG_HOME, — тоже временный. */
function noXdgHome(withConfig) {
  const home = tmp();
  const second = process.platform === "win32" ? path.join(home, "openspec", "config.json") : path.join(home, ".config", "openspec", "config.json");
  if (withConfig) {
    fs.mkdirSync(path.dirname(second), { recursive: true });
    fs.writeFileSync(second, "{}\n");
  }
  return { second, env: { APPDATA: home, HOME: home, USERPROFILE: home } };
}

test("Один конфиг: [..] с путём, код не меняется", () => {
  const p = installed();
  const { env } = noXdgHome(false);
  const r = spawnSync(process.execPath, [bin, "check", "--project", p], { encoding: "utf8", env: { ...process.env, ...env } });
  assert.equal(r.status, 0, r.stdout + r.stderr);
  assert.ok(r.stdout.split(/\r?\n/).includes(`[..] openspec: глобальный конфиг ${cfgFile()}`), r.stdout);
});

test("Два конфига: [..] называет оба, код не меняется", () => {
  const p = installed();
  const { env, second } = noXdgHome(true);
  const r = spawnSync(process.execPath, [bin, "check", "--project", p], { encoding: "utf8", env: { ...process.env, ...env } });
  assert.equal(r.status, 0, r.stdout + r.stderr);
  assert.ok(r.stdout.split(/\r?\n/).includes(`[..] openspec: глобальный конфиг ${cfgFile()}; есть ещё ${second}, он действует без XDG_CONFIG_HOME`), r.stdout);
});

// --- сигналы журнала --------------------------------------------------------

test("Сигнал доходит до symphysis check: строка [..] <журнал>: ..., код не меняется", () => {
  const p = installed();
  const one = path.join(p, "openspec", "changes", "one");
  fs.mkdirSync(one, { recursive: true });
  fs.writeFileSync(path.join(one, "decisions.json"), JSON.stringify(MINIMAL_JOURNAL));
  const direct = spawnSync("python", ["-X", "utf8", path.join(targets(p).toolsDir, "tools", "journal.py"), "check", path.join(one, "decisions.json")], { encoding: "utf8" });
  assert.match(direct.stdout, /^\[!!\] F-01: /m, "журнал теста должен давать сигнал сверки");
  const signal = direct.stdout.split(/\r?\n/).find((l) => l.startsWith("[!!] F-01: ")).slice("[!!] ".length);
  const r = cli("check", "--project", p);
  assert.equal(r.status, 0, r.stdout);
  assert.ok(r.stdout.split(/\r?\n/).includes(`[..] openspec/changes/one/decisions.json: ${signal}`), r.stdout);
});

test("Форк отказал: своя находка, а не «не найден»", () => {
  const p = installed();
  const fake = path.join(tmp(), "fake.js");
  fs.writeFileSync(fake, 'console.error("boom"); process.exit(3);\n');
  process.env.SYMPHYSIS_OPENSPEC = fake;
  const r = runCheck(p);
  const line = r.findings.find((f) => f.startsWith("openspec: "));
  assert.ok(line?.includes("не отработал (код 3: boom)"), JSON.stringify(r.findings));
  assert.ok(!line.includes("не найден"), line);
});

test("нет файла mermaid: сигнал [..], находки нет, страница работает и с текстом (F-101)", () => {
  const p = installed();
  fs.rmSync(path.join(targets(p).toolsDir, "tools", "mermaid.min.js"));
  const r = runCheck(p);
  assert.deepEqual(r.findings, []);
  assert.ok(r.notes.some((n) => n.startsWith(".symphysis/tools/mermaid.min.js:")), JSON.stringify(r.notes));
});

test("steps.md отличается от payload: сигнал о схеме (F-23)", () => {
  const p = installed();
  const f = path.join(targets(p).schemaDir, "steps.md");
  fs.appendFileSync(f, "\nправка\n");
  const r = runCheck(p);
  assert.ok(r.findings.includes("схема: байты отличаются от payload: openspec/schemas/symphysis/steps.md"), JSON.stringify(r.findings));
});

test("Сигнала `check` нет: файл версии и step_help.py: сигнала нет, как бы они ни лежали (F-36, F-65)", () => {
  const p = installed();
  const tools = path.join(targets(p).toolsDir, "tools");
  const base = runCheck(p).findings;
  fs.writeFileSync(path.join(tools, "symphysis-version.txt"), "0.0.1+0000000\n");
  assert.deepEqual(runCheck(p).findings, base);
  fs.rmSync(path.join(tools, "symphysis-version.txt"));
  assert.deepEqual(runCheck(p).findings, base);
  fs.writeFileSync(path.join(tools, "step_help.py"), "# другой\n");
  assert.deepEqual(runCheck(p).findings, base);
  fs.rmSync(path.join(tools, "step_help.py"));
  assert.deepEqual(runCheck(p).findings, base);
});
