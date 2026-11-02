import { test } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { hasSources, payloadMatches, syncPayload, ROOT } from "../scripts/sync-payload.js";

const FILES = [
  "openspec/schemas/symphysis/schema.yaml",
  "openspec/config.symphysis.yaml",
  "tools/journal.py",
  "tools/journal_model.py",
  "tools/journal_render.py",
  "tools/journal_apply.py",
  "tools/journal_cli.py",
  "tools/journal_sites.py",
  "tools/journal_consequences.py",
  "tools/symphysis_config.py",
  "tools/playground-template.html",
  "docs/journal.schema.json",
];

const tmp = () => fs.mkdtempSync(path.join(os.tmpdir(), "symphysis-payload-"));

test("payload содержит все перечисленные источники", () => {
  const dest = tmp();
  syncPayload(dest);
  for (const f of FILES) assert.ok(fs.existsSync(path.join(dest, f)), f);
  const skills = fs.readdirSync(path.join(ROOT, "skills")).filter((n) => n.startsWith("symphysis-"));
  assert.ok(skills.length >= 4);
  for (const s of skills) assert.ok(fs.existsSync(path.join(dest, "skills", s, "SKILL.md")), s);
  assert.ok(fs.readdirSync(path.join(dest, "openspec", "schemas", "symphysis", "templates")).length > 0);
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
  const dest = fs.mkdtempSync(path.join(os.tmpdir(), "symphysis-доставка-"));
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

test("корень без skills: понятная ошибка, payload не тронут", () => {
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
  fs.mkdirSync(path.join(root, "skills"));
  assert.throws(() => syncPayload(dest, root), /mermaid/);
  assert.ok(fs.existsSync(path.join(dest, "keep.txt")));
});

test("файл mermaid не в git ядра (F-53)", () => {
  const listed = spawnSync("git", ["ls-files", "*mermaid.min.js", "*mermaid.LICENSE"], { cwd: ROOT, encoding: "utf8" });
  assert.equal(listed.status, 0, listed.stderr);
  assert.equal(listed.stdout.trim(), "");
});
