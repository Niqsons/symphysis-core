import { test } from "node:test";
import assert from "node:assert/strict";
import path from "node:path";
import os from "node:os";
import { isFullyAbsolute, targets } from "../lib/paths.js";

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

test("fully absolute Windows paths include a drive or complete UNC share", () => {
  for (const file of ["X:/fixture", "x:\\fixture", "C:/", "\\\\server\\share", "\\\\server\\share\\fixture", "//server/share/fixture"]) assert.equal(isFullyAbsolute(file, "win32"), true, file);
  for (const file of ["relative", ".", "..", "X:fixture", "\\fixture", "/fixture", "\\\\server", "\\\\server\\", "\\\\\\server\\share", "\\\\?\\X:\\fixture", "\\\\.\\pipe\\fixture"]) assert.equal(isFullyAbsolute(file, "win32"), false, file);
});

test("fully absolute POSIX paths and invalid input types are independent of cwd", () => {
  assert.equal(isFullyAbsolute("/fixture", "linux"), true);
  assert.equal(isFullyAbsolute("/", "darwin"), true);
  for (const value of ["relative", "X:/fixture", "X:\\fixture", "\\fixture", "", "bad\0path", null, undefined, 7, {}, []]) {
    assert.equal(isFullyAbsolute(value, "linux"), false);
    if (typeof value !== "string" || !value || value.includes("\0")) assert.equal(isFullyAbsolute(value, "win32"), false);
  }
});
