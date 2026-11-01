import { test } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { syncPayload, ROOT } from "../scripts/sync-payload.js";

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

test("корень без skills: понятная ошибка, payload не тронут", () => {
  const dest = tmp();
  fs.writeFileSync(path.join(dest, "keep.txt"), "x");
  const badRoot = tmp();
  assert.throws(() => syncPayload(dest, badRoot), /skills/);
  assert.ok(fs.existsSync(path.join(dest, "keep.txt")));
});
