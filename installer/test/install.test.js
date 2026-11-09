import { test, before, beforeEach, afterEach } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { createHash } from "node:crypto";
import { fileURLToPath } from "node:url";
import { syncPayload } from "../scripts/sync-payload.js";
import { targets } from "../lib/paths.js";
import { install } from "../lib/install.js";
import { requireFork } from "../scripts/build-vendor.js";
import { tempDir } from "../test-support/temp-dir.js";
import { REPO, gitIn, makeClone as makeCloneIn } from "../test-support/clone.js";
import { parse } from "yaml";

const bin = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "bin", "symphysis.js");
const SUFFIX = "(есть, отличается — перезапись: --force)";
let payloadDir;
const tmp = () => tempDir("symphysis-install-");
const run = (...args) => spawnSync(process.execPath, [bin, ...args], { encoding: "utf8" });

const FORK = process.env.SYMPHYSIS_OPENSPEC || path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..", "upstream", "openspec", "bin", "openspec.js");
const OFF_COMMAND = "openspec config set telemetry.enabled false";
const saved = { openspec: process.env.SYMPHYSIS_OPENSPEC, path: process.env.PATH, Path: process.env.Path, xdg: process.env.XDG_CONFIG_HOME };
const cfgFile = () => path.join(process.env.XDG_CONFIG_HOME, "openspec", "config.json");

// Глобальный конфиг форка — всегда временный каталог: настоящий конфиг пользователя тесты не трогают.
beforeEach(() => {
  process.env.XDG_CONFIG_HOME = tmp();
});

afterEach(() => {
  for (const [k, v] of [["SYMPHYSIS_OPENSPEC", saved.openspec], ["PATH", saved.path], ["Path", saved.Path], ["XDG_CONFIG_HOME", saved.xdg]]) {
    if (v === undefined) delete process.env[k];
    else process.env[k] = v;
  }
});

before(() => {
  requireFork(FORK);
  payloadDir = tmp();
  syncPayload(payloadDir);
});

test("install в пустой проект: все цели существуют", () => {
  const p = tmp();
  const r = install(p, { payloadDir });
  const t = targets(p);
  assert.ok(fs.existsSync(path.join(t.schemaDir, "schema.yaml")));
  assert.ok(!fs.existsSync(path.join(t.schemaDir, "config.symphysis.yaml")), "образец конфига — не файл схемы проекта (F-37)");
  assert.ok(!fs.existsSync(path.join(t.schemaDir, "tests")), "тесты модуля схемы в проект не идут");
  assert.ok(fs.existsSync(t.configPath));
  for (const d of t.skillsDirs) assert.ok(fs.existsSync(path.join(d, "symphysis-brainstorm", "SKILL.md")));
  for (const d of t.agentsDirs) assert.ok(fs.existsSync(path.join(d, "symphysis-attack-driver.md")));
  assert.ok(fs.existsSync(path.join(p, ".claude", "agents", "symphysis-research-driver.md")));
  assert.ok(fs.existsSync(path.join(t.toolsDir, "tools", "journal.py")));
  assert.ok(fs.existsSync(path.join(t.toolsDir, "tools", "playground-template.html")));
  assert.ok(fs.existsSync(path.join(t.toolsDir, "tools", "journal.schema.json")));   // схема журнала — рядом с кодом (F-41)
  const canonicalSchema = fs.readFileSync(new URL("../../decisions/journal.schema.json", import.meta.url));
  for (const dir of ["tools", "docs"]) {
    assert.deepEqual(fs.readFileSync(path.join(t.toolsDir, dir, "journal.schema.json")), canonicalSchema);
  }
  for (const d of ["terms.md", "journal-cli.md", "config.md", "candidate.md", "attack-table.md", "THIRD-PARTY-NOTICES.md"]) {
    assert.ok(fs.existsSync(path.join(t.toolsDir, "docs", d)), d);
  }
  assert.equal(fs.readFileSync(path.join(t.toolsDir, "tools", "journal-roots.json"), "utf8"), '{"": "<root>/.."}\n');
  assert.deepEqual(r.merged, []);
  assert.ok(r.written.includes("openspec/config.yaml"));
  assert.ok(r.written.every((w) => !w.includes("\\")));
  assert.deepEqual(r.skipped, []);
});

test("повторный install: written и skipped пусты", () => {
  const p = tmp();
  install(p, { payloadDir });
  const r = install(p, { payloadDir });
  assert.deepEqual(r.written, []);
  assert.deepEqual(r.skipped, []);
  assert.deepEqual(r.merged, []);
});

test("слияние config.yaml: схема, rules, комментарий", () => {
  const p = tmp();
  fs.mkdirSync(path.join(p, "openspec"));
  const cfg = path.join(p, "openspec", "config.yaml");
  fs.writeFileSync(cfg, "# мой комментарий\nschema: spec-driven\nrules:\n  specs:\n    - своя строка\n  mine-only:\n    - x\nextra: 1\n");
  const r = install(p, { payloadDir });
  const text = fs.readFileSync(cfg, "utf8");
  assert.match(text, /^schema: symphysis$/m);
  assert.match(text, /# мой комментарий/);
  assert.match(text, /^extra: 1$/m);
  assert.deepEqual(r.merged, ["openspec/config.yaml"]);
  assert.deepEqual(r.messages.filter((m) => m.startsWith("config.yaml")), ["config.yaml уже был: схема переключена с spec-driven на symphysis, rules добавлены"]);
  assert.ok(!r.written.includes("openspec/config.yaml"));
  const ours = fs.readFileSync(path.join(payloadDir, "openspec", "config.symphysis.yaml"), "utf8");
  assert.ok(ours.includes("решение излагается, не принимается"));
  for (const s of ["у каждого требования хотя бы один сценарий GIVEN/WHEN/THEN", "решение излагается, не принимается"]) assert.ok(text.includes(s), s);
  assert.ok(text.indexOf("своя строка") < text.indexOf("у каждого требования"));
  assert.match(text, /mine-only:/);
  // повторный запуск не дублирует
  install(p, { payloadDir });
  assert.equal(fs.readFileSync(cfg, "utf8"), text);
});

test("слияние: схема уже symphysis — иное сообщение", () => {
  const p = tmp();
  fs.mkdirSync(path.join(p, "openspec"));
  fs.writeFileSync(path.join(p, "openspec", "config.yaml"), "schema: symphysis\n");
  const r = install(p, { payloadDir });
  assert.deepEqual(r.messages.filter((m) => m.startsWith("config.yaml")), ["config.yaml уже был: схема symphysis, rules добавлены"]);
});

test("слияние: rules.<key> скаляр — конфликт до записи", () => {
  const p = tmp();
  fs.mkdirSync(path.join(p, "openspec"));
  const cfg = path.join(p, "openspec", "config.yaml");
  fs.writeFileSync(cfg, "schema: symphysis\nrules:\n  specs: одна строка\n");
  assert.throws(() => install(p, { payloadDir }), /rules.specs должен быть списком/);
  assert.match(fs.readFileSync(cfg, "utf8"), /specs: одна строка/);
});

const GUIDANCE_MARK = "symphysis trace freeze";
const ANCHORS_MARK = "symphysis anchors <имя>";
const archiveGuidance = (text) => parse(text)?.operations?.archive?.guidance;

test("`project-installer`: «Новый проект»: скрипт графа, openspec_run.py и anchor_refs.py ставятся, --help даёт код 0 (F-39, F-138, trace-numbers-signals/F-65)", () => {
  const p = tmp();
  const r = install(p, { payloadDir });
  for (const f of ["trace_graph.py", "openspec_run.py", "anchor_refs.py"]) assert.ok(r.written.includes(`.symphysis/tools/${f}`), `${f}: ${JSON.stringify(r.written)}`);
  for (const f of ["trace_graph.py", "anchor_refs.py"]) {
    const h = spawnSync("python", ["-X", "utf8", path.join(".symphysis", "tools", f), "--help"], { cwd: p, encoding: "utf8" });
    assert.equal(h.status, 0, f + ": " + h.stdout + h.stderr);
    assert.ok(h.stdout.trim() !== "");
  }
});

test("`project-installer`: ownership-конфликт отменяет весь план без частичной установки", () => {
  const p = tmp();
  install(p, { payloadDir });
  const tools = path.join(targets(p).toolsDir, "tools");
  fs.rmSync(path.join(tools, "trace_graph.py"));
  fs.writeFileSync(path.join(tools, "openspec_run.py"), "# своё\n");
  assert.throws(() => install(p, { payloadDir }), /openspec_run.py.*сохранён/);
  assert.ok(!fs.existsSync(path.join(tools, "trace_graph.py")));
  assert.equal(fs.readFileSync(path.join(tools, "openspec_run.py"), "utf8"), "# своё\n");
});

test("`project-installer`: «Конфиг без подсказок»: слияние добавляет operations.archive.guidance", () => {
  const p = tmp();
  fs.mkdirSync(path.join(p, "openspec"));
  const cfg = path.join(p, "openspec", "config.yaml");
  fs.writeFileSync(cfg, "# мой\nschema: spec-driven\n");
  install(p, { payloadDir });
  const g = archiveGuidance(fs.readFileSync(cfg, "utf8"));
  assert.equal(g.length, 3, JSON.stringify(g));  // заморозка, ошибка скрипта, якоря (trace-numbers-signals/F-35)
  assert.ok(g[0].includes(GUIDANCE_MARK), g[0]);
  assert.ok(g[2].includes(ANCHORS_MARK), g[2]);
});

test("`project-installer`: «Конфиг без подсказок»: форк отдаёт подсказку полем operationGuidance", { skip: !fs.existsSync(FORK) }, () => {
  process.env.SYMPHYSIS_OPENSPEC = FORK;
  const p = tmp();
  fs.mkdirSync(path.join(p, "openspec"));
  fs.writeFileSync(path.join(p, "openspec", "config.yaml"), "schema: spec-driven\n");
  install(p, { payloadDir });
  const fork = (...a) => spawnSync(process.execPath, [FORK, ...a], { cwd: p, encoding: "utf8", env: { ...process.env, OPENSPEC_TELEMETRY: "0" } });
  let r = fork("new", "change", "demo");
  assert.equal(r.status, 0, r.stdout + r.stderr);
  r = fork("instructions", "archive", "--change", "demo", "--json");
  assert.equal(r.status, 0, r.stdout + r.stderr);
  const out = JSON.parse(r.stdout);
  assert.ok(Array.isArray(out.operationGuidance) && out.operationGuidance.some((l) => l.includes(GUIDANCE_MARK)), r.stdout);
});

test("`project-installer`: «У проекта своя подсказка»: своя строка на месте, подсказка symphysis добавлена", () => {
  const p = tmp();
  fs.mkdirSync(path.join(p, "openspec"));
  const cfg = path.join(p, "openspec", "config.yaml");
  fs.writeFileSync(cfg, "schema: symphysis\noperations:\n  archive:\n    guidance:\n      - своя строка\n  apply:\n    guidance:\n      - чужая операция\n");
  install(p, { payloadDir });
  const parsed = parse(fs.readFileSync(cfg, "utf8"));
  const g = parsed.operations.archive.guidance;
  assert.equal(g[0], "своя строка");
  assert.equal(g.length, 4, JSON.stringify(g));
  assert.ok(g[1].includes(GUIDANCE_MARK) && g[3].includes(ANCHORS_MARK), JSON.stringify(g));
  assert.deepEqual(parsed.operations.apply.guidance, ["чужая операция"]);
});

test("`project-installer`: «Повторная установка не дублирует»: подсказка заморозки одна", () => {
  const p = tmp();
  install(p, { payloadDir });
  const cfg = path.join(p, "openspec", "config.yaml");
  const once = fs.readFileSync(cfg, "utf8");
  install(p, { payloadDir });
  const again = fs.readFileSync(cfg, "utf8");
  assert.equal(again, once);
  assert.equal(archiveGuidance(again).filter((l) => l.includes(GUIDANCE_MARK)).length, 1);
  // и после слияния в существующий конфиг
  const q = tmp();
  fs.mkdirSync(path.join(q, "openspec"));
  fs.writeFileSync(path.join(q, "openspec", "config.yaml"), "schema: spec-driven\n");
  install(q, { payloadDir });
  install(q, { payloadDir });
  assert.equal(archiveGuidance(fs.readFileSync(path.join(q, "openspec", "config.yaml"), "utf8")).filter((l) => l.includes(GUIDANCE_MARK)).length, 1);
});

test("слияние: operations.archive.guidance не список — конфликт без записи", () => {
  const p = tmp();
  fs.mkdirSync(path.join(p, "openspec"));
  const cfg = path.join(p, "openspec", "config.yaml");
  fs.writeFileSync(cfg, "schema: symphysis\noperations:\n  archive:\n    guidance: одна строка\n");
  assert.throws(() => install(p, { payloadDir }), /operations.archive.guidance должен быть списком/);
  assert.match(fs.readFileSync(cfg, "utf8"), /guidance: одна строка/);
});

test("слияние: в config.yaml нет schema — свой текст сообщения", () => {
  const p = tmp();
  fs.mkdirSync(path.join(p, "openspec"));
  fs.writeFileSync(path.join(p, "openspec", "config.yaml"), "context: x\n");
  const r = install(p, { payloadDir });
  assert.deepEqual(r.messages.filter((m) => m.startsWith("config.yaml")), ["config.yaml уже был: схема установлена symphysis, rules добавлены"]);
});

test("изменённый файл скилла: конфликт сохраняет байты также с force", () => {
  const p = tmp();
  install(p, { payloadDir });
  const f = path.join(targets(p).skillsDirs[0], "symphysis-brainstorm", "SKILL.md");
  fs.writeFileSync(f, "моё");
  assert.throws(() => install(p, { payloadDir }), /ownership/);
  assert.equal(fs.readFileSync(f, "utf8"), "моё");
  assert.throws(() => install(p, { payloadDir, force: true }), /ownership/);
  assert.equal(fs.readFileSync(f, "utf8"), "моё");
});

test("существующий файл корней с другим содержимым переживает install", () => {
  const p = tmp();
  const rf = path.join(p, ".symphysis", "tools", "journal-roots.json");
  fs.mkdirSync(path.dirname(rf), { recursive: true });
  fs.writeFileSync(rf, '{"a/": "<home>"}\n');
  const r = install(p, { payloadDir, force: true });
  assert.equal(fs.readFileSync(rf, "utf8"), '{"a/": "<home>"}\n');
  assert.ok(!r.written.includes(".symphysis/tools/journal-roots.json"));
});

test("два skillsDirs: скиллы в обоих, агенты рядом с каждым", () => {
  const p = tmp();
  install(p, { payloadDir, skillsDirs: ["a/skills", "b/skills"] });
  for (const d of ["a", "b"]) assert.ok(fs.existsSync(path.join(p, d, "skills", "symphysis-brainstorm", "SKILL.md")));
  for (const d of ["a", "b"]) assert.ok(fs.existsSync(path.join(p, d, "agents", "symphysis-consequences-driver.md")));
  assert.ok(!fs.existsSync(path.join(p, ".claude", "skills")));
  assert.ok(fs.existsSync(path.join(p, ".claude", "commands", "opsx", "continue.md")), "legacy overrides сохраняют Claude workflow carrier в native commands root");
});

test("agentsDirs задан явно: агенты только туда", () => {
  const p = tmp();
  install(p, { payloadDir, skillsDirs: ["a/skills"], agentsDirs: ["x/agents"] });
  assert.ok(fs.existsSync(path.join(p, "x", "agents", "symphysis-attack-driver.md")));
  assert.ok(!fs.existsSync(path.join(p, "a", "agents")));
  const names = fs.readdirSync(path.join(p, "x", "agents"));
  assert.deepEqual(names.sort(), ["symphysis-attack-driver.md", "symphysis-consequences-driver.md",
    "symphysis-edge-probe-driver.md", "symphysis-prohibition-probe-driver.md", "symphysis-research-driver.md"]);
});

test("CLI install: изменённый файл даёт ownership-конфликт и код 2", () => {
  const p = tmp();
  let r = run("install", "--project", p);
  assert.equal(r.status, 0, r.stderr);
  assert.match(r.stdout, /записано \d+/);
  fs.writeFileSync(path.join(p, ".claude", "skills", "symphysis-brainstorm", "SKILL.md"), "моё");
  r = run("install", "--project", p);
  assert.equal(r.status, 2);
  assert.match(r.stderr, /--force/);
  assert.match(r.stderr, /--force не отменяет ownership/);
});

test("Раскладка входа: intent первым в схеме payload, шаблон intent.md на месте, .gigacode/ нет", () => {
  const p = tmp();
  install(p, { payloadDir });
  const schema = fs.readFileSync(path.join(targets(p).schemaDir, "schema.yaml"), "utf8");
  assert.equal(schema.match(/^ {2}- id: (\S+)/m)[1], "intent");
  assert.match(schema, /generates: intent\.md/);
  assert.ok(fs.existsSync(path.join(targets(p).schemaDir, "templates", "intent.md")));
  assert.ok(!fs.existsSync(path.join(p, ".gigacode")));
  assert.ok(fs.existsSync(path.join(p, ".symphysis", "tools", "journal.py")));
});

test("Раскладка входа: форк new change demo — первый артефакт intent, путь intent.md", { skip: !fs.existsSync(FORK) }, () => {
  process.env.SYMPHYSIS_OPENSPEC = FORK;
  const p = tmp();
  install(p, { payloadDir });
  const fork = (...a) => spawnSync(process.execPath, [FORK, ...a], { cwd: p, encoding: "utf8", env: { ...process.env, OPENSPEC_TELEMETRY: "0" } });
  let r = fork("new", "change", "demo");
  assert.equal(r.status, 0, r.stdout + r.stderr);
  r = fork("status", "--change", "demo", "--json");
  assert.equal(r.status, 0, r.stdout + r.stderr);
  const out = JSON.parse(r.stdout);
  assert.equal(out.artifacts[0].id, "intent", r.stdout);
  assert.ok(r.stdout.includes("intent.md"), r.stdout);
  assert.ok(fs.existsSync(path.join(p, "openspec", "changes", "demo")));
  assert.ok(!fs.existsSync(path.join(p, ".gigacode")));
});

test("Обновление схемы: изменённый файл сохранён и конфликт назван CLI", () => {
  const p = tmp();
  run("install", "--project", p);
  const f = path.join(targets(p).schemaDir, "schema.yaml");
  fs.writeFileSync(f, "name: old\n");
  assert.throws(() => install(p, { payloadDir }), /schema.yaml.*сохранён/);
  assert.equal(fs.readFileSync(f, "utf8"), "name: old\n");
  const cli = run("install", "--project", p);
  assert.equal(cli.status, 2);
  assert.match(cli.stderr, /schema.yaml.*сохранён/);
  assert.throws(() => install(p, { payloadDir, force: true }), /ownership/);
  assert.equal(fs.readFileSync(f, "utf8"), "name: old\n");
});

test("Обновление схемы: перечислены все ownership-конфликты схемы и скилла", () => {
  const p = tmp();
  install(p, { payloadDir });
  fs.writeFileSync(path.join(targets(p).schemaDir, "schema.yaml"), "a");
  fs.writeFileSync(path.join(targets(p).schemaDir, "templates", "intent.md"), "b");
  fs.writeFileSync(path.join(targets(p).skillsDirs[0], "symphysis-brainstorm", "SKILL.md"), "c");
  assert.throws(() => install(p, { payloadDir }), (error) => ["schema.yaml", "intent.md", "SKILL.md"].every((name) => error.message.includes(name)));
});

test("telemetry: чистое окружение без ключа — install пишет enabled: false", { skip: !fs.existsSync(FORK) }, () => {
  process.env.SYMPHYSIS_OPENSPEC = FORK;
  const r = install(tmp(), { payloadDir });
  assert.equal(JSON.parse(fs.readFileSync(cfgFile(), "utf8")).telemetry.enabled, false);
  assert.ok(r.messages.some((m) => m.startsWith("telemetry: выключена")), JSON.stringify(r.messages));
});

test("telemetry: ключ не задан в существующем конфиге — выключается, прочее сохраняется", { skip: !fs.existsSync(FORK) }, () => {
  process.env.SYMPHYSIS_OPENSPEC = FORK;
  fs.mkdirSync(path.dirname(cfgFile()), { recursive: true });
  fs.writeFileSync(cfgFile(), JSON.stringify({ profile: "custom", telemetry: { anonymousId: "id-1" } }));
  install(tmp(), { payloadDir });
  const cfg = JSON.parse(fs.readFileSync(cfgFile(), "utf8"));
  assert.equal(cfg.telemetry.enabled, false);
  assert.equal(cfg.telemetry.anonymousId, "id-1");
  assert.equal(cfg.profile, "custom");
});

test("telemetry: явно заданное человеком (true) install не меняет", { skip: !fs.existsSync(FORK) }, () => {
  process.env.SYMPHYSIS_OPENSPEC = FORK;
  fs.mkdirSync(path.dirname(cfgFile()), { recursive: true });
  const was = JSON.stringify({ telemetry: { enabled: true } });
  fs.writeFileSync(cfgFile(), was);
  const r = install(tmp(), { payloadDir });
  assert.equal(fs.readFileSync(cfgFile(), "utf8"), was);
  assert.ok(!r.messages.some((m) => m.startsWith("telemetry:")));
});

test("telemetry: бинаря нет — строка с командой, установка продолжается, конфиг не создан", () => {
  delete process.env.SYMPHYSIS_OPENSPEC;
  process.env.PATH = tmp();
  process.env.Path = process.env.PATH;
  const p = tmp();
  const r = install(p, { payloadDir });
  assert.ok(r.messages.includes(`telemetry: openspec не найден — выключить после установки: ${OFF_COMMAND}`), JSON.stringify(r.messages));
  assert.ok(fs.existsSync(path.join(targets(p).schemaDir, "schema.yaml")));
  assert.ok(!fs.existsSync(cfgFile()));
});

// --- /opsx:continue, глобальный конфиг, symphysis.yaml, .gitignore ---------
// Здесь каждая команда — дочерний процесс, временный конфиг задан только ей.

const commandEnv = (xdg, extra = {}) => ({ ...process.env, XDG_CONFIG_HOME: xdg, SYMPHYSIS_OPENSPEC: FORK, ...extra });
const symphysis = (env, ...args) => spawnSync(process.execPath, [bin, ...args], { encoding: "utf8", env });
const forkCli = (cwd, env, ...args) => spawnSync(process.execPath, [FORK, ...args], { cwd, encoding: "utf8", env: { ...env, OPENSPEC_TELEMETRY: "0" } });
const configFile = (xdg) => path.join(xdg, "openspec", "config.json");
const writeConfig = (xdg, obj) => {
  fs.mkdirSync(path.dirname(configFile(xdg)), { recursive: true });
  fs.writeFileSync(configFile(xdg), JSON.stringify(obj));
};
const readConfig = (xdg) => JSON.parse(fs.readFileSync(configFile(xdg), "utf8"));
const withForkDefaults = (cfg) => ({ featureFlags: {}, profile: "core", delivery: "both", ...cfg });
const continueCommand = (p) => path.join(p, ".claude", "commands", "opsx", "continue.md");
const continueSkill = (p) => path.join(p, ".claude", "skills", "openspec-continue-change");

/** Проект после `openspec init --tools claude` с этим конфигом. */
function initialized(env) {
  const p = tmp();
  const r = forkCli(p, env, "init", "--tools", "claude");
  assert.equal(r.status, 0, r.stdout + r.stderr);
  return p;
}
/** Проект, инициализированный до новой версии форка: файлы форка есть, команды нет. */
function withoutContinue(env) {
  const p = initialized(env);
  fs.rmSync(continueCommand(p));
  fs.rmSync(continueSkill(p), { recursive: true });
  return p;
}
const emptyPathEnv = (xdg) => {
  const env = { ...process.env, XDG_CONFIG_HOME: xdg };
  delete env.SYMPHYSIS_OPENSPEC;
  for (const k of Object.keys(env)) if (k.toLowerCase() === "path") delete env[k];
  env[process.platform === "win32" ? "Path" : "PATH"] = tmp();
  return env;
};
/** Поддельный форк: пишет каждый вызов в журнал, отвечает кодом 0. */
function loggingFork() {
  const dir = tmp();
  const log = path.join(dir, "calls.log");
  const js = path.join(dir, "fork.js");
  fs.writeFileSync(js, `require("node:fs").appendFileSync(${JSON.stringify(log)}, process.argv.slice(2).join(" ") + "\\n");\n`);
  fs.writeFileSync(path.join(dir, "package.json"), '{"type":"commonjs"}');
  return { js, calls: () => (fs.existsSync(log) ? fs.readFileSync(log, "utf8") : "") };
}

for (const [name, cfg] of [["заданным", { profile: "core", delivery: "both", telemetry: { enabled: false } }], ["по умолчанию", null]]) {
  test(`Прежние native carriers: профиль core ${name} — конфликт до явного review`, () => {
    const xdg = tmp();
    if (cfg) writeConfig(xdg, cfg);
    const env = commandEnv(xdg);
    const p = initialized(env);
    const before = fs.existsSync(configFile(xdg)) ? fs.readFileSync(configFile(xdg)) : null;
    const command = fs.readFileSync(continueCommand(p));
    const r = symphysis(env, "install", "--project", p);
    assert.equal(r.status, 2, r.stdout + r.stderr);
    assert.match(r.stderr, /install --preview/);
    assert.deepEqual(fs.readFileSync(continueCommand(p)), command);
    assert.deepEqual(fs.existsSync(configFile(xdg)) ? fs.readFileSync(configFile(xdg)) : null, before);
  });
}

test("Список человека и прежние native workflow сохраняются при конфликте", () => {
  const xdg = tmp();
  writeConfig(xdg, { featureFlags: {}, profile: "custom", delivery: "both", workflows: ["propose", "apply", "verify"], telemetry: { enabled: false } });
  const before = fs.readFileSync(configFile(xdg));
  const env = commandEnv(xdg);
  const p = initialized(env);
  const r = symphysis(env, "install", "--project", p);
  assert.equal(r.status, 2, r.stdout + r.stderr);
  assert.deepEqual(fs.readFileSync(configFile(xdg)), before);
  assert.match(r.stderr, /ownership/);
  assert.ok(!fs.existsSync(continueCommand(p)));
  assert.ok(!fs.existsSync(path.join(p, ".symphysis", "install-manifest.json")));
});

test("Ownership-конфликт не запускает posthook телеметрии и сохраняет список человека", () => {
  const xdg = tmp();
  writeConfig(xdg, { profile: "custom", workflows: ["propose", "apply", "verify"] });
  const env = commandEnv(xdg);
  const p = initialized(env);
  const before = fs.readFileSync(configFile(xdg));
  assert.equal(symphysis(env, "install", "--project", p).status, 2);
  assert.deepEqual(fs.readFileSync(configFile(xdg)), before);
  assert.deepEqual(readConfig(xdg).workflows, ["propose", "apply", "verify"]);
  assert.equal(readConfig(xdg).profile, "custom");
});

test("Тесты не трогают настоящий конфиг: байты до и после install с временным XDG_CONFIG_HOME", () => {
  // A neighboring synthetic config proves the write boundary without reading a real profile.
  const other = path.join(tmp(), "neighbor", "config.json");
  fs.mkdirSync(path.dirname(other));
  fs.writeFileSync(other, '{"profile":"foreign"}\n');
  const real = [other];
  const digest = () => real.map((f) => (fs.existsSync(f) ? createHash("sha256").update(fs.readFileSync(f)).digest("hex") : "нет файла"));
  const before = digest();
  const xdg = tmp();
  const r = symphysis(commandEnv(xdg), "install", "--project", tmp());
  assert.equal(r.status, 0, r.stdout + r.stderr);
  assert.deepEqual(digest(), before);
  assert.equal(readConfig(xdg).telemetry.enabled, false, "запись ушла во временный каталог");
});

test("Чужая команда с похожим именем не принимается и update не зовётся", () => {
  const fake = loggingFork();
  const p = tmp();
  fs.mkdirSync(path.dirname(continueCommand(p)), { recursive: true });
  fs.writeFileSync(continueCommand(p), "x");
  const r = symphysis(commandEnv(tmp(), { SYMPHYSIS_OPENSPEC: fake.js }), "install", "--project", p);
  assert.equal(r.status, 2, r.stdout + r.stderr);
  assert.equal(fs.readFileSync(continueCommand(p), "utf8"), "x");
  assert.doesNotMatch(fake.calls(), /update/);
});

test("Команда уже есть: скилла openspec-continue-change достаточно", () => {
  const fake = loggingFork();
  const p = tmp();
  fs.mkdirSync(continueSkill(p), { recursive: true });
  fs.writeFileSync(path.join(continueSkill(p), "SKILL.md"), "x");
  assert.equal(symphysis(commandEnv(tmp(), { SYMPHYSIS_OPENSPEC: fake.js }), "install", "--project", p).status, 0);
  assert.doesNotMatch(fake.calls(), /update/);
});

test("Прежние native файлы требуют review; отсутствующая команда не вызывает update", () => {
  const xdg = tmp();
  writeConfig(xdg, { profile: "core", telemetry: { enabled: false } });
  const env = commandEnv(xdg);
  const p = withoutContinue(env);
  const r = symphysis(env, "install", "--project", p);
  assert.equal(r.status, 2, r.stdout + r.stderr);
  assert.ok(!fs.existsSync(continueCommand(p)), r.stdout);
  assert.ok(!fs.existsSync(path.join(continueSkill(p), "SKILL.md")), r.stdout);
  assert.match(r.stderr, /install --preview/);
});

test("Форка нет: local файлы поставлены с явной диагностикой зависимости", () => {
  const xdg = tmp();
  const env = emptyPathEnv(xdg);
  const p = tmp();
  fs.mkdirSync(path.dirname(continueCommand(p)), { recursive: true });
  const r = symphysis(env, "install", "--project", p);
  assert.equal(r.status, 0, r.stdout + r.stderr);
  assert.ok(fs.existsSync(path.join(targets(p).schemaDir, "schema.yaml")));
  assert.ok(fs.existsSync(path.join(p, ".claude", "skills", "symphysis-brainstorm", "SKILL.md")));
  assert.match(r.stdout, /openspec: нужен закреплённый форк/);
  assert.ok(fs.existsSync(continueCommand(p)));
  const c = symphysis(env, "check", "--project", p);
  assert.equal(c.status, 2);
  assert.match(c.stdout, /\[!!\].*(?:OpenSpec|openspec|форк)/);
});

test("Новый local проект получает guarded native workflows без предварительного openspec init", () => {
  const xdg = tmp();
  const env = commandEnv(xdg);
  const p = tmp();
  const r = symphysis(env, "install", "--project", p);
  assert.equal(r.status, 0, r.stdout + r.stderr);
  assert.ok(fs.existsSync(path.join(targets(p).schemaDir, "schema.yaml")));
  assert.match(fs.readFileSync(continueCommand(p), "utf8"), /run `symphysis [^\n]* preflight`/);
  assert.match(r.stdout, /native discovery.*unconfirmed/);
});

test("В PATH другая версия OpenSpec: update не зовётся, сгенерированные файлы проекта не переписаны, код 0", () => {
  const dir = tmp();
  const log = path.join(dir, "calls.log");
  const js = path.join(dir, "vanilla.js");
  fs.writeFileSync(js, `require("node:fs").appendFileSync(${JSON.stringify(log)}, process.argv.slice(2).join(" ") + "\\n");\nif (process.argv[2] === "--version") console.log("1.13.1");\n`);
  fs.writeFileSync(path.join(dir, "package.json"), '{"type":"commonjs"}');
  const xdg = tmp();
  writeConfig(xdg, { profile: "core", telemetry: { enabled: false } });
  const p = tmp();
  fs.mkdirSync(path.join(p, ".claude", "commands", "opsx"), { recursive: true });
  const r = symphysis(commandEnv(xdg, { SYMPHYSIS_OPENSPEC: js }), "install", "--project", p);
  assert.equal(r.status, 0, r.stdout + r.stderr);
  assert.doesNotMatch(fs.readFileSync(log, "utf8"), /update/);
  const pin = JSON.parse(fs.readFileSync(fileURLToPath(new URL("../package.json", import.meta.url)), "utf8")).symphysis.openspecPin;
  assert.ok(r.stdout.includes(`openspec: нужен закреплённый форк ${pin}`), r.stdout);
});

test("SYMPHYSIS_OPENSPEC относительным путём: отказ usage без изменения проекта", () => {
  const xdg = tmp();
  writeConfig(xdg, { profile: "core", telemetry: { enabled: false } });
  const env = commandEnv(xdg);
  const p = withoutContinue(env);
  const rel = path.relative(process.cwd(), FORK);
  const r = symphysis({ ...env, SYMPHYSIS_OPENSPEC: rel }, "install", "--project", p);
  assert.equal(r.status, 2, r.stdout + r.stderr);
  assert.match(r.stderr, /абсолютный/);
  assert.ok(!fs.existsSync(path.join(p, ".symphysis")));
});

test("Конфиг до и после native-конфликта: заданная человеком телеметрия не изменена", () => {
  const xdg = tmp();
  const was = { profile: "core", telemetry: { enabled: true } };
  writeConfig(xdg, was);
  const env = commandEnv(xdg);
  const p = withoutContinue(env);
  const r = symphysis(env, "install", "--project", p);
  assert.equal(r.status, 2, r.stdout + r.stderr);
  assert.deepEqual(withForkDefaults(readConfig(xdg)), withForkDefaults(was));
  assert.match(r.stderr, /ownership/);
  assert.doesNotMatch(r.stdout, /^telemetry: выключена/m);
});

test("Конфиг до и после успешной установки: различие только telemetry.enabled: false", () => {
  const xdg = tmp();
  const was = { profile: "core" };
  writeConfig(xdg, was);
  const env = commandEnv(xdg);
  const p = tmp();
  const r = symphysis(env, "install", "--project", p);
  assert.equal(r.status, 0, r.stdout + r.stderr);
  assert.deepEqual(withForkDefaults(readConfig(xdg)), withForkDefaults({ ...was, telemetry: { enabled: false } }));
  assert.match(r.stdout, /^telemetry: выключена \(telemetry\.enabled: false в глобальном конфиге OpenSpec\)$/m);
  assert.ok(r.stdout.split(/\r?\n/).includes(`openspec: глобальный конфиг ${configFile(xdg)}`), r.stdout);
});

test("Профиль не задан: конфликт чужой команды не запускает update и сохраняет конфиг", () => {
  const xdg = tmp();
  writeConfig(xdg, { telemetry: { enabled: true } });
  const before = fs.readFileSync(configFile(xdg));
  const env = commandEnv(xdg);
  const p = tmp();
  fs.mkdirSync(path.join(p, ".claude", "commands", "opsx"), { recursive: true });
  fs.writeFileSync(path.join(p, ".claude", "commands", "opsx", "apply.md"), "x");
  const fake = loggingFork();
  const r = symphysis({ ...env, SYMPHYSIS_OPENSPEC: fake.js }, "install", "--project", p);
  assert.equal(r.status, 2, r.stdout + r.stderr);
  assert.doesNotMatch(fake.calls(), /update/);
  assert.deepEqual(fs.readFileSync(configFile(xdg)), before);
  assert.match(r.stderr, /ownership/);
});

test("Инсталлятор сам телеметрию не порождает: нет anonymousId и noticeSeen", () => {
  const xdg = tmp();
  const env = commandEnv(xdg);
  const p = tmp();
  const r = symphysis(env, "install", "--project", p);
  assert.equal(r.status, 0, r.stdout + r.stderr);
  const cfg = readConfig(xdg);
  assert.equal(cfg.telemetry.enabled, false);
  assert.equal(cfg.telemetry.anonymousId, undefined);
  assert.equal(cfg.telemetry.noticeSeen, undefined);
});

test("Соседи в XDG_CONFIG_HOME не тронуты: запись только в openspec/", () => {
  const xdg = tmp();
  const neighbour = path.join(xdg, "другая-программа", "настройки.json");
  fs.mkdirSync(path.dirname(neighbour));
  fs.writeFileSync(neighbour, "{}\n");
  const env = commandEnv(xdg);
  const r = symphysis(env, "install", "--project", tmp());
  assert.equal(r.status, 0, r.stdout + r.stderr);
  assert.equal(fs.readFileSync(neighbour, "utf8"), "{}\n");
  assert.deepEqual(fs.readdirSync(xdg).sort(), ["openspec", "другая-программа"].sort());
  assert.deepEqual(fs.readdirSync(path.dirname(neighbour)), ["настройки.json"]);
});

// --- symphysis.yaml --------------------------------------------------------

const settingsFile = (p) => path.join(p, "symphysis.yaml");
const gitignore = (p) => path.join(p, ".gitignore");
const lines = (file) => fs.readFileSync(file, "utf8").split(/\r?\n/);
const privateEntries = ["symphysis.yaml", ".symphysis/tools/journal-roots.json", "tools/journal-roots.json", ".symphysis/install-manifest.json", ".symphysis/.install-*", ".symphysis/.leases/", ".symphysis/store-init.json", ".symphysis/.store-init-*", ".symphysis/migration.json", ".symphysis/.migration-*", ".symphysis-install-*", ".symphysis-init-*", ".symphysis-migrate-*"];

test("Первая установка: symphysis.yaml создан, всё включено, вложенные ключи", { skip: spawnSync("python", ["-c", "import yaml"]).status === 0 ? false : "у python из PATH нет PyYAML: python -m pip install pyyaml" }, () => {
  const p = tmp();
  const r = install(p, { payloadDir });
  assert.ok(r.written.includes("symphysis.yaml"));
  const text = fs.readFileSync(settingsFile(p), "utf8");
  assert.match(text, /^consequences:\n {2}failure_branches: true\n {2}assumptions: true\nedge_probe:\n {2}enabled: true\ndrivers:\n {2}attack: true\n {2}probes: false\n {2}consequences: false\n {2}research: true\n/m);
  // Каждая линза атаки обоих файлов названа своим слугом и включена; claim-extraction одна (F-61, F-132).
  const lenses = ["context-compliance", "claim-authority", "claim-extraction", "coverage", "scenario-run", "trace-link", "rule-compliance"];
  assert.match(text, new RegExp(`\nattack:\n${lenses.map((s) => ` {2}${s}: true\n`).join("")}$`));
  const py = spawnSync("python", ["-X", "utf8", path.join(p, ".symphysis", "tools", "symphysis_config.py"), "--project", p, "--strict"], { encoding: "utf8" });
  assert.equal(py.status, 0, py.stdout + py.stderr);
  assert.deepEqual(py.stdout.trim().split(/\r?\n/), [
    "[..] symphysis.yaml: ветки отказа вкл, допущения вкл, проба краёв вкл, водители: атака вкл, пробы выкл, опись выкл, исследование вкл",
    `[..] symphysis.yaml: линзы атаки: ${lenses.map((s) => `${s} вкл`).join(", ")}`,
  ]);
});

test("Файл с правками человека: --force не меняет байты", () => {
  const p = tmp();
  const mine = Buffer.from("# моё\r\nedge_probe:\r\n  enabled: false\r\n");
  fs.writeFileSync(settingsFile(p), mine);
  const r = install(p, { payloadDir, force: true });
  assert.deepEqual(fs.readFileSync(settingsFile(p)), mine);
  assert.ok(!r.written.includes("symphysis.yaml"));
});

test("Файл настроек и изменённый инструмент сохраняются при ownership-конфликте", () => {
  const p = tmp();
  install(p, { payloadDir });
  fs.writeFileSync(settingsFile(p), "edge_probe:\n  enabled: false\n");
  const tool = path.join(p, ".symphysis", "tools", "journal.py");
  fs.writeFileSync(tool, "старый");
  assert.throws(() => install(p, { payloadDir, force: true }), /ownership/);
  assert.equal(fs.readFileSync(settingsFile(p), "utf8"), "edge_probe:\n  enabled: false\n");
  assert.equal(fs.readFileSync(tool, "utf8"), "старый");
});

// --- .gitignore ------------------------------------------------------------

test("Установка вносит строку: прежние строки на месте", () => {
  const p = tmp();
  fs.writeFileSync(gitignore(p), "node_modules/\n*.log\n");
  install(p, { payloadDir });
  assert.deepEqual(lines(gitignore(p)), ["node_modules/", "*.log", ...privateEntries, ""]);
});

test("Установка вносит строку: CRLF сохраняется, файл без конца строки не склеивается", () => {
  const p = tmp();
  fs.writeFileSync(gitignore(p), "a\r\nb");
  install(p, { payloadDir });
  assert.equal(fs.readFileSync(gitignore(p), "utf8"), ["a", "b", ...privateEntries, ""].join("\r\n"));
});

test("Повторный запуск не дублирует строку", () => {
  const p = tmp();
  fs.writeFileSync(gitignore(p), "x\n");
  install(p, { payloadDir });
  const r = install(p, { payloadDir });
  assert.equal(lines(gitignore(p)).filter((l) => l === "symphysis.yaml").length, 1);
  assert.ok(!r.messages.some((m) => m.startsWith(".gitignore")), JSON.stringify(r.messages));
});

test("Файла .gitignore нет: создан со строкой", () => {
  const p = tmp();
  install(p, { payloadDir });
  assert.deepEqual(lines(gitignore(p)), [...privateEntries, ""]);
});

test("Проект не под git: строка внесена, ошибки нет, код 0", () => {
  const p = tmp();
  const r = symphysis(commandEnv(tmp()), "install", "--project", p);
  assert.equal(r.status, 0, r.stdout + r.stderr);
  assert.ok(!fs.existsSync(path.join(p, ".git")));
  assert.ok(lines(gitignore(p)).includes("symphysis.yaml"));
});

test("Правка .gitignore названа: она уходит в git вместе с работой человека", () => {
  const p = tmp();
  const r = symphysis(commandEnv(tmp()), "install", "--project", p);
  assert.match(r.stdout, /^\.gitignore: добавлена строка symphysis\.yaml — правка уйдёт в git вместе с работой$/m);
});

const noGitConfig = path.join(tmp(), "gitconfig");
fs.writeFileSync(noGitConfig, "");
const gitEnv = { ...process.env, GIT_CONFIG_GLOBAL: noGitConfig, GIT_CONFIG_NOSYSTEM: "1" };
const git = (cwd, ...args) => {
  const r = spawnSync("git", ["-c", "user.name=t", "-c", "user.email=t@t", "-c", "init.defaultBranch=main", ...args], { cwd, encoding: "utf8", env: gitEnv });
  assert.equal(r.status, 0, `git ${args.join(" ")}: ${r.stdout}${r.stderr}`);
  return r.stdout;
};

test("git check-ignore называет symphysis.yaml после install", () => {
  const p = tmp();
  git(p, "init", "-q");
  install(p, { payloadDir });
  assert.equal(git(p, "check-ignore", "symphysis.yaml").trim(), "symphysis.yaml");
});

test("Выбор человека и служебный manifest не приезжают с клоном, local install повторно привязывает точные байты", () => {
  const origin = tmp();
  git(origin, "init", "-q", "--bare");
  const first = tmp();
  git(first, "clone", "-q", origin, ".");
  install(first, { payloadDir });
  fs.writeFileSync(settingsFile(first), "edge_probe:\n  enabled: false\n");
  git(first, "add", "-A");
  git(first, "commit", "-qm", "работа");
  git(first, "push", "-q", "origin", "HEAD:main");
  assert.doesNotMatch(git(first, "ls-files"), /^symphysis\.yaml$/m);
  assert.doesNotMatch(git(first, "ls-files"), /^\.symphysis\/(?:install-manifest\.json|tools\/journal-roots\.json)$/m);

  const second = tmp();
  git(second, "clone", "-q", "--branch", "main", origin, ".");
  assert.ok(!fs.existsSync(settingsFile(second)), "файл первого клона приехал");
  assert.ok(!fs.existsSync(path.join(second, ".symphysis", "install-manifest.json")));
  install(second, { payloadDir });
  assert.match(fs.readFileSync(settingsFile(second), "utf8"), /enabled: true/);
});

test("файл mermaid и лицензия в .symphysis/tools (F-53)", () => {
  const p = tmp();
  install(p, { payloadDir });
  const tools = targets(p).toolsDir;
  assert.ok(fs.readFileSync(path.join(tools, "tools", "mermaid.min.js")).equals(fs.readFileSync(path.join(payloadDir, "tools", "mermaid.min.js"))));
  assert.ok(fs.existsSync(path.join(tools, "tools", "mermaid.LICENSE")));
});

test("черновики .symphysis/viewer переживают install --force (F-20)", () => {
  const p = tmp();
  install(p, { payloadDir });
  const viewer = path.join(p, ".symphysis", "viewer");
  fs.mkdirSync(viewer, { recursive: true });
  const draft = path.join(viewer, "черновик.json");
  fs.writeFileSync(draft, '{"слово":"своё"}\n');
  const before = fs.readFileSync(draft);
  install(p, { payloadDir, force: true });
  assert.ok(fs.readFileSync(draft).equals(before));
});

test("Новый проект: step_help.py и steps.md ставятся в проект (F-16, F-20)", () => {
  const p = tmp();
  const r = install(p, { payloadDir });
  const t = targets(p);
  assert.ok(fs.readFileSync(path.join(t.toolsDir, "tools", "step_help.py")).equals(fs.readFileSync(path.join(payloadDir, "tools", "step_help.py"))));
  assert.ok(fs.readFileSync(path.join(t.schemaDir, "steps.md")).equals(fs.readFileSync(path.join(payloadDir, "openspec", "schemas", "symphysis", "steps.md"))));
  assert.ok(r.written.includes(".symphysis/tools/step_help.py"), JSON.stringify(r.written));
  assert.ok(r.written.includes("openspec/schemas/symphysis/steps.md"));
});

test("Новый проект: attack_scope.py ставится в .symphysis/tools (attack-stale-scope)", () => {
  const p = tmp();
  const r = install(p, { payloadDir });
  const t = targets(p);
  assert.ok(r.written.includes(".symphysis/tools/attack_scope.py"), JSON.stringify(r.written));
  assert.ok(fs.readFileSync(path.join(t.toolsDir, "tools", "attack_scope.py")).equals(fs.readFileSync(path.join(payloadDir, "tools", "attack_scope.py"))));
});

test("Новый проект: после install скрипт справки печатает JSON, шаг intent, тексты не пусты", { skip: !fs.existsSync(FORK) }, () => {
  process.env.SYMPHYSIS_OPENSPEC = FORK;
  const p = tmp();
  install(p, { payloadDir });
  const fork = spawnSync(process.execPath, [FORK, "new", "change", "demo"], { cwd: p, encoding: "utf8", env: { ...process.env, OPENSPEC_TELEMETRY: "0" } });
  assert.equal(fork.status, 0, fork.stdout + fork.stderr);
  const r = spawnSync("python", ["-X", "utf8", path.join(".symphysis", "tools", "step_help.py")], { cwd: p, encoding: "utf8", env: { ...process.env, SYMPHYSIS_OPENSPEC: FORK } });
  assert.equal(r.status, 0, r.stdout + r.stderr);
  const out = JSON.parse(r.stdout);
  assert.equal(out.error, null);
  assert.equal(out.current_step, "intent");
  assert.ok(out.steps.length > 0);
  for (const step of out.steps) {
    for (const key of ["title", "why", "mechanics"]) assert.ok(step.texts[key].trim() !== "", `${step.id}: ${key}`);
  }
});

test("Обновление без `--force`: ownership-конфликт не публикует даже недостающий файл", () => {
  const p = tmp();
  install(p, { payloadDir });
  const t = targets(p);
  fs.rmSync(path.join(t.toolsDir, "tools", "step_help.py"));
  fs.writeFileSync(path.join(t.schemaDir, "steps.md"), "своё");
  assert.throws(() => install(p, { payloadDir }), /steps.md.*сохранён/);
  assert.ok(!fs.existsSync(path.join(t.toolsDir, "tools", "step_help.py")));
  assert.equal(fs.readFileSync(path.join(t.schemaDir, "steps.md"), "utf8"), "своё");
});

// Клон-образец в модульной раскладке: `test-support/clone.js`.
const VERSION = JSON.parse(fs.readFileSync(path.join(REPO, "installer", "package.json"), "utf8")).version;
const VERSION_REL = ".symphysis/tools/symphysis-version.txt";
const VERSION_FILE_NAME = "symphysis-version.txt";
const makeClone = ({ git }) => makeCloneIn(tmp(), { git });
const head = (dir) => gitIn(dir, "rev-parse", "--short", "HEAD").stdout.trim();
const versionOf = (p) => fs.readFileSync(path.join(p, VERSION_REL), "utf8").trim();

test("версия: установка из клона пишет версию и короткий хеш (F-36)", () => {
  const clone = makeClone({ git: true });
  const pd = tmp();
  syncPayload(pd, clone);
  const p = tmp();
  install(p, { payloadDir: pd, sourceRoot: clone });
  assert.match(head(clone), /^[0-9a-f]{7,}$/);
  assert.equal(versionOf(p), `${VERSION}+${head(clone)}`);
});

test("Установка без git: версия: клон вне git — только версия, код 0 (F-36)", () => {
  const clone = makeClone({ git: false });
  const pd = tmp();
  syncPayload(pd, clone);
  const p = tmp();
  install(p, { payloadDir: pd, sourceRoot: clone });
  assert.equal(versionOf(p), VERSION);
});

test("версия: клон внутри чужого репозитория не отдаёт чужой хеш", () => {
  const outer = tmp();
  gitIn(outer, "init", "-q");
  fs.writeFileSync(path.join(outer, "a.txt"), "x");
  gitIn(outer, "add", "-A");
  gitIn(outer, "commit", "-qm", "чужой");
  const clone = makeClone({ git: false });
  const inner = path.join(outer, "inner");
  fs.cpSync(clone, inner, { recursive: true });
  const pd = tmp();
  syncPayload(pd, inner);
  const p = tmp();
  install(p, { payloadDir: pd, sourceRoot: inner });
  assert.equal(versionOf(p), VERSION);
});

test("версия: неизменённая managed поставка обновляется целиком без force", () => {
  const clone = makeClone({ git: true });
  const pd = tmp();
  syncPayload(pd, clone);
  const p = tmp();
  install(p, { payloadDir: pd, sourceRoot: clone });
  const first = versionOf(p);
  fs.appendFileSync(path.join(clone, "cli", "journal.py"), "\n# правка\n");
  gitIn(clone, "add", "-A");
  gitIn(clone, "commit", "-qm", "два");
  syncPayload(pd, clone);
  install(p, { payloadDir: pd, sourceRoot: clone });
  assert.equal(versionOf(p), `${VERSION}+${head(clone)}`);
  install(p, { payloadDir: pd, sourceRoot: clone, force: true });
  assert.equal(versionOf(p), `${VERSION}+${head(clone)}`);
  assert.notEqual(versionOf(p), first);
});

test("версия: payload старее исходников — только версия, без хеша (F-64)", () => {
  const clone = makeClone({ git: true });
  const pd = tmp();
  syncPayload(pd, clone);
  fs.appendFileSync(path.join(clone, "cli", "journal.py"), "\n# новее payload\n");
  gitIn(clone, "add", "-A");
  gitIn(clone, "commit", "-qm", "два");
  const p = tmp();
  install(p, { payloadDir: pd, sourceRoot: clone });
  assert.equal(versionOf(p), VERSION);
});

test("версия: тарбол без исходников — только версия", () => {
  const p = tmp();
  install(p, { payloadDir, sourceRoot: tmp() });
  assert.equal(versionOf(p), VERSION);
});

// Файл версии описывает поставленные инструменты (project-installer: «Файл версии»).
test("ownership-конфликт инструмента не создаёт отсутствующий файл версии", () => {
  const p = tmp();
  install(p, { payloadDir });
  const t = targets(p);
  const tools = path.join(t.toolsDir, "tools");
  fs.writeFileSync(path.join(tools, "journal_cli.py"), "своё");
  fs.rmSync(path.join(tools, VERSION_FILE_NAME));
  assert.throws(() => install(p, { payloadDir }), /journal_cli.py.*сохранён/);
  assert.equal(fs.existsSync(path.join(tools, VERSION_FILE_NAME)), false);
});

test("ownership-конфликт сохраняет изменённые инструмент и файл версии", () => {
  const p = tmp();
  install(p, { payloadDir });
  const t = targets(p);
  const tools = path.join(t.toolsDir, "tools");
  fs.writeFileSync(path.join(tools, "journal_cli.py"), "своё");
  fs.writeFileSync(path.join(tools, VERSION_FILE_NAME), "0.0.1\n");
  assert.throws(() => install(p, { payloadDir }), (error) => ["journal_cli.py", VERSION_FILE_NAME].every((name) => error.message.includes(name)));
  assert.equal(fs.readFileSync(path.join(tools, VERSION_FILE_NAME), "utf8"), "0.0.1\n");
});

test("обновление без --force: ничего не пропущено — файл версии пишется", () => {
  const p = tmp();
  install(p, { payloadDir });
  const tools = path.join(targets(p).toolsDir, "tools");
  fs.rmSync(path.join(tools, VERSION_FILE_NAME));
  install(p, { payloadDir });
  assert.ok(fs.existsSync(path.join(tools, VERSION_FILE_NAME)));
});

test("Инсталлятор оставляет файлы хука: events.jsonl и скрипт байт в байт (F-35)", () => {
  const p = tmp();
  install(p, { payloadDir });
  const viewer = path.join(p, ".symphysis", "viewer");
  fs.mkdirSync(path.join(viewer, "sessions"), { recursive: true });
  const files = {
    "events.jsonl": Buffer.from('{"change":"демо"}\n{"change":"второе"}\n', "utf8"),
    "hook.py": Buffer.from("# скрипт хука\nprint('хук')\n", "utf8"),
  };
  for (const [name, bytes] of Object.entries(files)) fs.writeFileSync(path.join(viewer, name), bytes);
  install(p, { payloadDir });
  install(p, { payloadDir, force: true });
  for (const [name, bytes] of Object.entries(files)) {
    assert.ok(fs.readFileSync(path.join(viewer, name)).equals(bytes), `${name} изменён`);
  }
});
