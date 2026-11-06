import { test, before, afterEach } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { syncPayload, skillDirs, ROOT } from "../scripts/sync-payload.js";
import { targets } from "../lib/paths.js";
import { install } from "../lib/install.js";
import { check, findPython } from "../lib/check.js";
import { requireFork } from "../scripts/build-vendor.js";
import { tempDir } from "../test-support/temp-dir.js";
import { makeClone } from "../test-support/clone.js";

const FORK = path.resolve(ROOT, "upstream", "openspec", "bin", "openspec.js");
const tmp = () => tempDir("symphysis-layout-");
const saved = { openspec: process.env.SYMPHYSIS_OPENSPEC, xdg: process.env.XDG_CONFIG_HOME };

const walk = (dir, prefix = "") =>
  fs.readdirSync(dir, { withFileTypes: true }).flatMap((e) => (e.isDirectory() ? walk(path.join(dir, e.name), `${prefix}${e.name}/`) : [`${prefix}${e.name}`]));

/** Клон-образец, в каталоге схемы которого лежат `README.md` модуля и каталог тестов, а у скилла — свой каталог тестов. */
function cloneWithReadme() {
  const clone = makeClone(tmp(), { git: false });
  const schema = path.join(clone, "openspec", "schemas", "symphysis");
  fs.writeFileSync(path.join(schema, "README.md"), "# модуль схемы\n");
  fs.mkdirSync(path.join(schema, "tests"), { recursive: true });
  fs.writeFileSync(path.join(schema, "tests", "test_probe.py"), "# проба\n");
  const [skill] = skillDirs(clone);
  const skillTests = path.join(clone, skill.src, "tests");
  fs.mkdirSync(skillTests, { recursive: true });
  fs.writeFileSync(path.join(skillTests, "test_probe.py"), "# проба\n");
  return { clone, skill };
}

before(() => requireFork(FORK));
afterEach(() => {
  for (const [k, v] of [["SYMPHYSIS_OPENSPEC", saved.openspec], ["XDG_CONFIG_HOME", saved.xdg]]) {
    if (v === undefined) delete process.env[k];
    else process.env[k] = v;
  }
});

test("`project-installer`: «Установка без README схемы»: README и tests/ каталога схемы в проект не идут (F-36)", () => {
  process.env.XDG_CONFIG_HOME = tmp();
  const { clone } = cloneWithReadme();
  const payloadDir = tmp();
  syncPayload(payloadDir, clone);
  const inPayload = path.join(payloadDir, "openspec", "schemas", "symphysis");
  assert.equal(fs.existsSync(path.join(inPayload, "README.md")), false, "README в payload");
  const p = tmp();
  install(p, { payloadDir, sourceRoot: clone });
  const schemaDir = targets(p).schemaDir;
  for (const f of ["schema.yaml", "steps.md"]) assert.ok(fs.existsSync(path.join(schemaDir, f)), f);
  assert.ok(fs.readdirSync(path.join(schemaDir, "templates")).length > 0);
  assert.equal(fs.existsSync(path.join(schemaDir, "README.md")), false);
  assert.equal(fs.existsSync(path.join(schemaDir, "tests")), false);
});

test("`project-installer`: «Сверка не ждёт README»: check не называет README каталога схемы", () => {
  process.env.XDG_CONFIG_HOME = tmp();
  const { clone } = cloneWithReadme();
  const payloadDir = tmp();
  syncPayload(payloadDir, clone);
  const p = tmp();
  install(p, { payloadDir, sourceRoot: clone });
  const r = check(p, { payloadDir, sourceRoot: clone });
  const lines = [...r.findings, ...r.notes].filter((l) => /README/.test(l));
  assert.deepEqual(lines, []);
});

test("`repository-layout`: «Тесты модуля схемы»: в payload нет файлов каталогов тестов модулей (F-58)", () => {
  const { clone, skill } = cloneWithReadme();
  const payloadDir = tmp();
  syncPayload(payloadDir, clone);
  const bad = walk(payloadDir).filter((f) => f.split("/").includes("tests") || /(^|\/)test_[^/]*\.py$/.test(f));
  assert.deepEqual(bad, []);
  assert.ok(fs.existsSync(path.join(payloadDir, "skills", skill.name, "SKILL.md")));
});

test("состав настоящего payload: ни каталогов tests/, ни README схемы", () => {
  const payloadDir = tmp();
  syncPayload(payloadDir);
  const files = walk(payloadDir);
  assert.deepEqual(files.filter((f) => f.split("/").includes("tests")), []);
  assert.equal(files.includes("openspec/schemas/symphysis/README.md"), false);
});

const python = findPython();

test("служебная, F-65: после install каждая точка входа .symphysis/tools/ отвечает на --help кодом 0", { skip: python ? false : "python не найден в PATH" }, () => {
  process.env.XDG_CONFIG_HOME = tmp();
  const payloadDir = tmp();
  syncPayload(payloadDir);
  const p = tmp();
  install(p, { payloadDir });
  const toolsDir = path.join(targets(p).toolsDir, "tools");
  const entries = fs.readdirSync(toolsDir).filter((f) => f.endsWith(".py"));
  // Библиотечные модули без разбора аргументов: их --help не проверяется, но импорт обязан проходить.
  const entryPoints = ["journal.py", "step_help.py", "trace_graph.py", "symphysis_config.py", "roots.py", "viewer_render.py", "journal_sites.py", "journal_consequences.py"];
  for (const f of entryPoints) assert.ok(entries.includes(f), `нет ${f}: ${entries}`);
  for (const f of entryPoints) {
    const r = spawnSync(python, ["-X", "utf8", path.join(toolsDir, f), "--help"], { cwd: p, encoding: "utf8" });
    assert.equal(r.status, 0, `${f} --help: ${r.stdout}${r.stderr}`);
  }
  for (const f of entries.filter((e) => !entryPoints.includes(e))) {
    const mod = path.basename(f, ".py");
    const r = spawnSync(python, ["-X", "utf8", "-c", `import ${mod}`], { cwd: toolsDir, encoding: "utf8" });
    assert.equal(r.status, 0, `import ${mod}: ${r.stderr}`);
  }
});
