import { test, before, beforeEach, afterEach } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { syncPayload } from "../scripts/sync-payload.js";
import { targets } from "../lib/paths.js";
import { install } from "../lib/install.js";

const bin = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "bin", "symphysis.js");
const SUFFIX = "(есть, отличается — перезапись: --force)";
let payloadDir;
const tmp = () => fs.mkdtempSync(path.join(os.tmpdir(), "symphysis-install-"));
const run = (...args) => spawnSync(process.execPath, [bin, ...args], { encoding: "utf8" });

const FORK = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..", "upstream", "openspec", "bin", "openspec.js");
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
  payloadDir = tmp();
  syncPayload(payloadDir);
});

test("install в пустой проект: все цели существуют", () => {
  const p = tmp();
  const r = install(p, { payloadDir });
  const t = targets(p);
  assert.ok(fs.existsSync(path.join(t.schemaDir, "schema.yaml")));
  assert.ok(fs.existsSync(t.configPath));
  for (const d of t.skillsDirs) assert.ok(fs.existsSync(path.join(d, "symphysis-brainstorm", "SKILL.md")));
  assert.ok(fs.existsSync(path.join(t.toolsDir, "tools", "journal.py")));
  assert.ok(fs.existsSync(path.join(t.toolsDir, "tools", "playground-template.html")));
  assert.ok(fs.existsSync(path.join(t.toolsDir, "docs", "journal.schema.json")));
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
  assert.deepEqual(r.messages.filter((m) => !m.startsWith("telemetry:")), ["config.yaml уже был: схема переключена с spec-driven на symphysis, rules добавлены"]);
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
  assert.deepEqual(r.messages.filter((m) => !m.startsWith("telemetry:")), ["config.yaml уже был: схема symphysis, rules добавлены"]);
});

test("слияние: rules.<key> скаляр — сообщение, значение не тронуто", () => {
  const p = tmp();
  fs.mkdirSync(path.join(p, "openspec"));
  const cfg = path.join(p, "openspec", "config.yaml");
  fs.writeFileSync(cfg, "schema: symphysis\nrules:\n  specs: одна строка\n");
  const r = install(p, { payloadDir });
  assert.ok(r.messages.includes("rules.specs не список — правила symphysis не добавлены"), JSON.stringify(r.messages));
  assert.match(fs.readFileSync(cfg, "utf8"), /specs: одна строка/);
});

test("слияние: в config.yaml нет schema — свой текст сообщения", () => {
  const p = tmp();
  fs.mkdirSync(path.join(p, "openspec"));
  fs.writeFileSync(path.join(p, "openspec", "config.yaml"), "context: x\n");
  const r = install(p, { payloadDir });
  assert.deepEqual(r.messages.filter((m) => !m.startsWith("telemetry:")), ["config.yaml уже был: схема установлена symphysis, rules добавлены"]);
});

test("изменённый файл скилла: skipped, без --force не тронут; с force — перезаписан", () => {
  const p = tmp();
  install(p, { payloadDir });
  const f = path.join(targets(p).skillsDirs[0], "symphysis-brainstorm", "SKILL.md");
  fs.writeFileSync(f, "моё");
  const r = install(p, { payloadDir });
  const rel = ".claude/skills/symphysis-brainstorm/SKILL.md";
  assert.ok(r.skipped.includes(`${rel} ${SUFFIX}`), JSON.stringify(r.skipped));
  assert.equal(fs.readFileSync(f, "utf8"), "моё");
  const r2 = install(p, { payloadDir, force: true });
  assert.ok(r2.written.includes(rel));
  assert.notEqual(fs.readFileSync(f, "utf8"), "моё");
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

test("два skillsDirs: скиллы в обоих", () => {
  const p = tmp();
  install(p, { payloadDir, skillsDirs: ["a/skills", "b/skills"] });
  for (const d of ["a", "b"]) assert.ok(fs.existsSync(path.join(p, d, "skills", "symphysis-brainstorm", "SKILL.md")));
  assert.ok(!fs.existsSync(path.join(p, ".claude")));
});

test("CLI install: код 0, записано; изменённый файл — подсказка --force в stderr", () => {
  const p = tmp();
  let r = run("install", "--project", p);
  assert.equal(r.status, 0, r.stderr);
  assert.match(r.stdout, /записано \d+/);
  fs.writeFileSync(path.join(p, ".claude", "skills", "symphysis-brainstorm", "SKILL.md"), "моё");
  r = run("install", "--project", p);
  assert.equal(r.status, 0);
  assert.match(r.stderr, /--force/);
  assert.match(r.stderr, /перезапись существующих файлов: --force/);
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

test("Обновление схемы: пропущенный файл схемы — отдельной строкой в stdout; с --force обновлён", () => {
  const p = tmp();
  run("install", "--project", p);
  const f = path.join(targets(p).schemaDir, "schema.yaml");
  fs.writeFileSync(f, "name: old\n");
  const line = "пропущен: openspec/schemas/symphysis/schema.yaml — отличается, нужен --force";
  const r = install(p, { payloadDir });
  assert.ok(r.messages.includes(line), JSON.stringify(r.messages));
  assert.equal(fs.readFileSync(f, "utf8"), "name: old\n");
  const cli = run("install", "--project", p);
  assert.ok(cli.stdout.split(/\r?\n/).includes(line), cli.stdout);
  const r2 = install(p, { payloadDir, force: true });
  assert.ok(r2.written.includes("openspec/schemas/symphysis/schema.yaml"));
  assert.notEqual(fs.readFileSync(f, "utf8"), "name: old\n");
});

test("Обновление схемы: пропущены два файла схемы — две строки; скилл в такие строки не попадает", () => {
  const p = tmp();
  install(p, { payloadDir });
  fs.writeFileSync(path.join(targets(p).schemaDir, "schema.yaml"), "a");
  fs.writeFileSync(path.join(targets(p).schemaDir, "templates", "intent.md"), "b");
  fs.writeFileSync(path.join(targets(p).skillsDirs[0], "symphysis-brainstorm", "SKILL.md"), "c");
  const r = install(p, { payloadDir });
  assert.equal(r.messages.filter((m) => m.startsWith("пропущен: ")).length, 2, JSON.stringify(r.messages));
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
