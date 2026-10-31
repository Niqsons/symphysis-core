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

const here = path.dirname(fileURLToPath(import.meta.url));
const bin = path.resolve(here, "..", "bin", "symphysis.js");
const FORK = path.resolve(here, "..", "..", "upstream", "openspec", "bin", "openspec.js");
const PIN = "1.15.0-symphysis.2";
const hasFork = fs.existsSync(FORK);
let payloadDir;
const tmp = () => fs.mkdtempSync(path.join(os.tmpdir(), "symphysis-check-"));
const saved = { openspec: process.env.SYMPHYSIS_OPENSPEC, path: process.env.PATH, Path: process.env.Path };

before(() => {
  assert.ok(hasFork, `нет форка для зелёного случая: ${FORK}`);
  payloadDir = tmp();
  syncPayload(payloadDir);
});

afterEach(() => {
  for (const [k, v] of [["SYMPHYSIS_OPENSPEC", saved.openspec], ["PATH", saved.path], ["Path", saved.Path]]) {
    if (v === undefined) delete process.env[k];
    else process.env[k] = v;
  }
});

function installed() {
  process.env.SYMPHYSIS_OPENSPEC = FORK;
  const p = tmp();
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

test("после install: ok, findings и notes пусты", () => {
  const p = installed();
  const r = runCheck(p);
  assert.deepEqual(r.findings, []);
  assert.equal(r.ok, true);
  assert.deepEqual(r.notes, []);
});

test("байт схемы подменён: findings[0] называет schema.yaml", () => {
  const p = installed();
  const f = path.join(targets(p).schemaDir, "schema.yaml");
  const b = fs.readFileSync(f);
  b[b.length - 1] ^= 1;
  fs.writeFileSync(f, b);
  const r = runCheck(p);
  assert.equal(r.ok, false);
  assert.match(r.findings[0], /schema\.yaml/);
  assert.match(r.findings[0], /схема изменена/);
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
  process.env.SYMPHYSIS_OPENSPEC = FORK;
  const p = tmp();
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

test("журнал: годный даёт note, негодный — finding", () => {
  const p = installed();
  const good = path.join(p, "openspec", "changes", "one");
  fs.mkdirSync(good, { recursive: true });
  fs.writeFileSync(path.join(good, "decisions.json"), JSON.stringify(MINIMAL_JOURNAL));
  let r = runCheck(p);
  assert.equal(r.ok, true, JSON.stringify(r.findings));
  assert.match(r.notes[0], /^openspec\/changes\/one\/decisions\.json: /);
  assert.match(r.notes[0], /улик сверено/);

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
  assert.match(r.stdout, /^\[!!\] openspec\/schemas\/symphysis\/schema\.yaml: схема изменена$/m);
  assert.match(r.stdout, /^check: 1 расхождений$/m);
});
