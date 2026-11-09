import { test } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { hasSources, payloadMatches, skillDirs, stripProvenance, syncPayload, toolsFiles, ROOT } from "../scripts/sync-payload.js";
import { tempDir } from "../test-support/temp-dir.js";

const FILES = [
  "openspec/schemas/symphysis/schema.yaml",
  "openspec/schemas/symphysis/steps.md",
  "openspec/config.symphysis.yaml",
  "tools/journal.py",
  "tools/journal_model.py",
  "tools/journal_render.py",
  "tools/journal_apply.py",
  "tools/roots.py",
  "tools/viewer_render.py",
  "tools/attack_table.py",
  "tools/attack_scope.py",
  "tools/journal_cli.py",
  "tools/journal_sites.py",
  "tools/journal_consequences.py",
  "tools/symphysis_config.py",
  "tools/step_help.py",
  "tools/openspec_run.py",
  "tools/trace_graph.py",
  "tools/trace_modules.py",
  "tools/anchor_refs.py",
  "tools/playground-template.html",
  "tools/journal.schema.json",
  "docs/terms.md",
  "docs/journal-cli.md",
  "docs/config.md",
  "docs/candidate.md",
  "docs/attack-table.md",
  "docs/driver.md",
  "docs/module-declarations.md",
  "docs/THIRD-PARTY-NOTICES.md",
  "agents/symphysis-attack-driver.md",
  "agents/symphysis-edge-probe-driver.md",
  "agents/symphysis-prohibition-probe-driver.md",
  "agents/symphysis-consequences-driver.md",
  "agents/symphysis-research-driver.md",
];

/** Строки контура разработки, которых в тексте продукта нет (docs/skills-canon.md, раздел 1). */
const DEV_ONLY = [/upstream\//, /docs\/analysis\//, /TRANSLATION-NOTES/, /sources\//, /слово владельца/, /\b2026-\d\d/, /F-\d+\.[A-Z]\b/, /<!--\s*(?:src|dev)\b/];

const tmp = () => tempDir("symphysis-payload-");

test("payload содержит все перечисленные источники", () => {
  const dest = tmp();
  syncPayload(dest);
  for (const f of FILES) assert.ok(fs.existsSync(path.join(dest, f)), f);
  const skills = skillDirs(ROOT).map(({ name }) => name);
  assert.equal(skills.length, 7, JSON.stringify(skills));
  for (const s of skills) assert.ok(fs.existsSync(path.join(dest, "skills", s, "SKILL.md")), s);
  assert.deepEqual(fs.readdirSync(path.join(dest, "skills")).sort(), [...skills].sort());
  assert.ok(fs.readdirSync(path.join(dest, "openspec", "schemas", "symphysis", "templates")).length > 0);
});

test("образец конфига: из каталога схемы в прежний путь payload, в каталог схемы payload не идёт (F-37)", () => {
  const src = path.join(ROOT, "openspec", "schemas", "symphysis", "config.symphysis.yaml");
  assert.equal(fs.existsSync(path.join(ROOT, "openspec", "config.symphysis.yaml")), false);
  const dest = tmp();
  syncPayload(dest);
  assert.ok(fs.readFileSync(path.join(dest, "openspec", "config.symphysis.yaml")).equals(fs.readFileSync(src)));
  assert.equal(fs.existsSync(path.join(dest, "openspec", "schemas", "symphysis", "config.symphysis.yaml")), false);
});

test("тесты модуля схемы в payload не идут: каталог схемы без tests/ (F-23)", () => {
  assert.ok(fs.existsSync(path.join(ROOT, "openspec", "schemas", "symphysis", "tests", "test_schema.py")));
  const dest = tmp();
  syncPayload(dest);
  assert.equal(fs.existsSync(path.join(dest, "openspec", "schemas", "symphysis", "tests")), false);
});

test("устаревший файл в payload удаляется", () => {
  const dest = tmp();
  fs.writeFileSync(path.join(dest, "stale.txt"), "x");
  fs.mkdirSync(path.join(dest, "tools"));
  fs.writeFileSync(path.join(dest, "tools", "old.py"), "x");
  syncPayload(dest);
  assert.ok(!fs.existsSync(path.join(dest, "stale.txt")));
  assert.ok(!fs.existsSync(path.join(dest, "tools", "old.py")));
});

test("устаревший файл удаляется и по кириллическому пути", () => {
  const dest = tempDir("symphysis-доставка-");
  fs.mkdirSync(path.join(dest, "tools"));
  fs.writeFileSync(path.join(dest, "tools", "old.py"), "x");
  syncPayload(dest);
  assert.ok(!fs.existsSync(path.join(dest, "tools", "old.py")));
});

test("payloadMatches: свежий payload совпадает, правка и лишний файл — нет", () => {
  const dest = tmp();
  syncPayload(dest);
  assert.equal(payloadMatches(dest), true);
  fs.appendFileSync(path.join(dest, "tools", "journal.py"), "#");
  assert.equal(payloadMatches(dest), false);
  syncPayload(dest);
  fs.writeFileSync(path.join(dest, "tools", "лишний.py"), "x");
  assert.equal(payloadMatches(dest), false);
  syncPayload(dest);
  fs.unlinkSync(path.join(dest, "tools", "journal.py"));
  assert.equal(payloadMatches(dest), false);
});

test("payloadMatches: файлы mermaid в составе: свежий совпадает, правка копии — нет", () => {
  const dest = tmp();
  syncPayload(dest);
  assert.equal(payloadMatches(dest), true);
  fs.appendFileSync(path.join(dest, "tools", "mermaid.LICENSE"), "#");
  assert.equal(payloadMatches(dest), false);
});

test("hasSources: корень репозитория — да, чужой каталог — нет", () => {
  assert.equal(hasSources(ROOT), true);
  assert.equal(hasSources(tmp()), false);
});

test("скиллы собираются по маске <модуль>/skills/symphysis-*, каталога skills/ в корне нет (F-67)", () => {
  assert.equal(fs.existsSync(path.join(ROOT, "skills")), false);
  const found = skillDirs(ROOT);
  for (const { name, src } of found) assert.match(src, new RegExp(`^[^./][^/]*/skills/${name}$`), src);
  assert.ok(found.some(({ src }) => src === "probes/skills/symphysis-edge-probe"), JSON.stringify(found));
});

test("скилл в каталоге с точкой (.claude/skills после установки в самом ядре) в payload не идёт", () => {
  const root = tmp();
  fs.mkdirSync(path.join(root, ".claude", "skills", "symphysis-x"), { recursive: true });
  fs.mkdirSync(path.join(root, "decisions", "skills", "symphysis-y"), { recursive: true });
  assert.deepEqual(skillDirs(root), [{ name: "symphysis-y", src: "decisions/skills/symphysis-y" }]);
});

test("одно имя скилла в двух модулях: ошибка с обоими путями, payload не тронут", () => {
  const dest = tmp();
  fs.writeFileSync(path.join(dest, "keep.txt"), "x");
  const root = tmp();
  for (const mod of ["decisions", "viewer"]) {
    fs.mkdirSync(path.join(root, mod, "skills", "symphysis-x"), { recursive: true });
    fs.writeFileSync(path.join(root, mod, "skills", "symphysis-x", "SKILL.md"), "x");
  }
  assert.throws(() => syncPayload(dest, root), /decisions\/skills\/symphysis-x и viewer\/skills\/symphysis-x/);
  assert.ok(fs.existsSync(path.join(dest, "keep.txt")));
});

test("корень без скиллов в модулях: понятная ошибка, payload не тронут", () => {
  const dest = tmp();
  fs.writeFileSync(path.join(dest, "keep.txt"), "x");
  const badRoot = tmp();
  assert.throws(() => syncPayload(dest, badRoot), /skills/);
  assert.ok(fs.existsSync(path.join(dest, "keep.txt")));
});


test("payload несёт файл mermaid и его лицензию (F-53)", () => {
  const dest = tmp();
  syncPayload(dest);
  const src = path.join(ROOT, "installer", "node_modules", "mermaid");
  assert.ok(fs.readFileSync(path.join(dest, "tools", "mermaid.min.js")).equals(fs.readFileSync(path.join(src, "dist", "mermaid.min.js"))));
  assert.ok(fs.readFileSync(path.join(dest, "tools", "mermaid.LICENSE")).equals(fs.readFileSync(path.join(src, "LICENSE"))));
});

test("файла mermaid нет при сборке поставки: ошибка с причиной, payload не тронут (F-100)", () => {
  const dest = tmp();
  fs.writeFileSync(path.join(dest, "keep.txt"), "x");
  const root = tmp();
  fs.mkdirSync(path.join(root, "decisions", "skills", "symphysis-x"), { recursive: true });
  assert.throws(() => syncPayload(dest, root), /mermaid/);
  assert.ok(fs.existsSync(path.join(dest, "keep.txt")));
});

test("файл mermaid не в git ядра (F-53)", () => {
  const listed = spawnSync("git", ["ls-files", "*mermaid.min.js", "*mermaid.LICENSE"], { cwd: ROOT, encoding: "utf8" });
  assert.equal(listed.status, 0, listed.stderr);
  assert.equal(listed.stdout.trim(), "");
});

test("payload не несёт sources/ и TRANSLATION-NOTES.md скиллов", () => {
  const dest = tmp();
  syncPayload(dest);
  const files = [];
  const walk = (d) => { for (const e of fs.readdirSync(d, { withFileTypes: true })) { const f = path.join(d, e.name); if (e.isDirectory()) walk(f); else files.push(f); } };
  walk(path.join(dest, "skills"));
  assert.ok(files.length > 0);
  for (const f of files) {
    assert.ok(!f.split(path.sep).includes("sources"), f);
    assert.ok(path.basename(f) !== "TRANSLATION-NOTES.md", f);
  }
});

test("stripProvenance: вырезает комментарии src и dev строкой и блоком, прочие комментарии оставляет", () => {
  const text = [
    "Правило один.",
    "<!-- src: upstream/gsd-core/x.md:12; F-07.A -->",
    "Правило два.",
    "<!-- dev",
    "  слово владельца 2026-11-05: так и было",
    "-->",
    "<!-- обычный комментарий шаблона -->",
    "Правило три.",
    "",
  ].join("\n");
  assert.equal(stripProvenance(text), ["Правило один.", "Правило два.", "<!-- обычный комментарий шаблона -->", "Правило три.", ""].join("\n"));
});

test("общие файлы docs/*.md в payload без строк контура разработки", () => {
  const dest = tmp();
  syncPayload(dest);
  const docs = fs.readdirSync(path.join(dest, "docs")).filter((n) => n.endsWith(".md"));
  assert.ok(docs.length >= 6, JSON.stringify(docs));
  for (const name of docs) {
    const text = fs.readFileSync(path.join(dest, "docs", name), "utf8");
    for (const re of DEV_ONLY) assert.ok(!re.test(text), `${name}: ${re}`);
  }
});

test("тела агентов в payload без комментариев провенанса и строк контура разработки", () => {
  const dest = tmp();
  syncPayload(dest);
  const agents = fs.readdirSync(path.join(dest, "agents"));
  assert.equal(agents.length, 5, JSON.stringify(agents));
  for (const name of agents) {
    const text = fs.readFileSync(path.join(dest, "agents", name), "utf8");
    for (const re of DEV_ONLY) assert.ok(!re.test(text), `${name}: ${re}`);
  }
});

test("тела скиллов в payload без комментариев провенанса", () => {
  const dest = tmp();
  syncPayload(dest);
  for (const s of fs.readdirSync(path.join(dest, "skills"))) {
    const text = fs.readFileSync(path.join(dest, "skills", s, "SKILL.md"), "utf8");
    assert.ok(!/<!--\s*(?:src|dev)\b/.test(text), s);
  }
});

test("файлы tools плоско по имени: повтор имени в двух модулях — ошибка с обоими путями (M5)", () => {
  assert.throws(() => toolsFiles(["a/x.py", "b/y.py", "c/x.py"]), /x\.py.*a\/x\.py.*c\/x\.py/);
  assert.equal(toolsFiles(["a/x.py", "b/y.py"]).length, 2);
  assert.ok(toolsFiles().length > 0);
});
