import { test } from "node:test";
import assert from "node:assert/strict";
import path from "node:path";
import os from "node:os";
import { targets } from "../lib/paths.js";

const p = path.resolve(os.tmpdir(), "proj-x");

test("два каталога скиллов — абсолютные пути под проектом", () => {
  const t = targets(p, [".claude/skills", ".opencode/skills"]);
  assert.deepEqual(t.skillsDirs, [path.join(p, ".claude", "skills"), path.join(p, ".opencode", "skills")]);
  for (const d of t.skillsDirs) assert.ok(path.isAbsolute(d));
});

test("без --skills-dir — ровно .claude/skills", () => {
  assert.deepEqual(targets(p).skillsDirs, [path.join(p, ".claude", "skills")]);
});

test("абсолютный --skills-dir остаётся как есть", () => {
  const abs = path.resolve(os.tmpdir(), "elsewhere", "skills");
  assert.deepEqual(targets(p, [abs]).skillsDirs, [abs]);
});

test("schemaDir, configPath, toolsDir", () => {
  const t = targets(p);
  assert.equal(t.schemaDir, path.join(p, "openspec", "schemas", "symphysis"));
  assert.equal(t.configPath, path.join(p, "openspec", "config.yaml"));
  assert.equal(t.toolsDir, path.join(p, ".symphysis"));
});
