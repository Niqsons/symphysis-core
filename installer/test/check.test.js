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

const here = path.dirname(fileURLToPath(import.meta.url));
const bin = path.resolve(here, "..", "bin", "symphysis.js");
const FORK = path.resolve(here, "..", "..", "upstream", "openspec", "bin", "openspec.js");
const PIN = "1.15.0-symphysis.4";
let payloadDir;
const tmp = () => fs.mkdtempSync(path.join(os.tmpdir(), "symphysis-check-"));
const saved = { openspec: process.env.SYMPHYSIS_OPENSPEC, path: process.env.PATH, Path: process.env.Path, xdg: process.env.XDG_CONFIG_HOME };
const cfgFile = () => path.join(process.env.XDG_CONFIG_HOME, "openspec", "config.json");
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
function installed() {
  process.env.XDG_CONFIG_HOME = tmp();
  process.env.SYMPHYSIS_OPENSPEC = FORK;
  const p = tmp();
  // Клиент настроен: файл команды форка; сценарии о самой команде живут ниже.
  fs.mkdirSync(path.join(p, ".claude", "commands", "opsx"), { recursive: true });
  fs.writeFileSync(path.join(p, ".claude", "commands", "opsx", "continue.md"), "x");
  install(p, { payloadDir });
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

test("после install: ok, находок нет, заметка о телеметрии", () => {
  const p = installed();
  const r = runCheck(p);
  assert.deepEqual(r.findings, []);
  assert.equal(r.ok, true);
  assert.deepEqual(r.notes, ["telemetry: выключена"]);
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

test("скиллы проверяются в каждом skillsDir", () => {
  process.env.XDG_CONFIG_HOME = tmp();
  process.env.SYMPHYSIS_OPENSPEC = FORK;
  const p = tmp();
  fs.mkdirSync(path.join(p, "a", "commands", "opsx"), { recursive: true });
  fs.writeFileSync(path.join(p, "a", "commands", "opsx", "continue.md"), "x");
  install(p, { payloadDir, skillsDirs: ["a/skills", "b/skills"] });
  fs.rmSync(path.join(p, "b", "skills", "symphysis-brainstorm", "SKILL.md"));
  const r = check(p, { payloadDir, skillsDirs: ["a/skills", "b/skills"] });
  assert.deepEqual(r.findings, ["b/skills/symphysis-brainstorm/SKILL.md: нет файла"]);
});

test("инструменты: нет journal.py, схемы json, корней", () => {
  const p = installed();
  const t = targets(p).toolsDir;
  fs.rmSync(path.join(t, "tools", "journal.py"));
  fs.rmSync(path.join(t, "docs", "journal.schema.json"));
  fs.rmSync(path.join(t, "tools", "journal-roots.json"));
  const r = runCheck(p);
  for (const f of [".symphysis/tools/journal.py", ".symphysis/docs/journal.schema.json", ".symphysis/tools/journal-roots.json"]) {
    assert.ok(r.findings.includes(`${f}: нет файла`), `${f}: ${JSON.stringify(r.findings)}`);
  }
});

test("инструменты: каждый модуль из состава проверяется, три новых тоже", () => {
  const modules = ["journal_apply.py", "journal_cli.py", "journal_model.py", "journal_render.py", "journal_sites.py", "journal_consequences.py", "symphysis_config.py"];
  const p = installed();
  const t = targets(p).toolsDir;
  for (const m of modules) fs.rmSync(path.join(t, "tools", m));
  const r = runCheck(p);
  for (const m of modules) {
    assert.ok(r.findings.includes(`.symphysis/tools/${m}: нет файла`), `${m}: ${JSON.stringify(r.findings)}`);
  }
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
