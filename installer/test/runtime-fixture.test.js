import { test } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { createRuntimeFixture } from "../test-support/runtime-fixture.js";

const base = path.join(os.tmpdir(), "symphysis-fixture-tests");
const fork = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..", "upstream", "openspec", "bin", "openspec.js");
const fixture = (t) => {
  const value = createRuntimeFixture(base);
  t.after(() => value.cleanup());
  return value;
};
const within = (root, target) => {
  const rel = path.relative(root, target);
  return rel && !rel.startsWith("..") && !path.isAbsolute(rel);
};

test("fixture profiles and all writes stay below the explicit temporary base", (t) => {
  const f = fixture(t);
  assert.ok(within(base, f.root));
  for (const key of ["HOME", "USERPROFILE", "APPDATA", "LOCALAPPDATA", "XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_CACHE_HOME", "XDG_STATE_HOME", "CODEX_HOME", "CLAUDE_CONFIG_DIR", "OPENCODE_CONFIG_DIR", "SYMPHYSIS_HOME", "TEMP", "TMP", "TMPDIR"]) {
    assert.ok(within(f.root, f.env[key]), key);
  }
  for (const roots of Object.values(f.clientRoots)) for (const dir of Object.values(roots)) assert.ok(within(f.root, dir));
  assert.notEqual(f.clientRoots.codex.skills, path.join(f.env.CODEX_HOME, "skills"));
  assert.equal(f.env.OPENSPEC_TELEMETRY, "0");
  assert.throws(() => createRuntimeFixture("relative"), /absolute/);
  assert.throws(() => f.write(path.join(f.root, "..", "outside.txt"), "bad"), /escapes/);
  assert.throws(() => f.store("../outside"), /kebab-case/);
  assert.throws(() => f.payload("global", { files: { "../outside.txt": "bad" } }), /escapes/);
});

test("global-only payload does not create project runtime, including a data-only roots map", (t) => {
  const f = fixture(t);
  const first = f.store("store-a");
  const second = f.store("store-b", { dataOnly: true });
  const global = f.payload("global");
  assert.equal(path.basename(first.changeRoot), path.basename(second.changeRoot));
  assert.notEqual(first.journal, second.journal);
  assert.equal(fs.existsSync(path.join(first.root, ".symphysis")), false);
  assert.deepEqual(fs.readdirSync(path.join(second.root, ".symphysis", "tools")), ["journal-roots.json"]);
  for (const store of [first, second]) assert.equal(fs.existsSync(path.join(store.root, ".symphysis", "tools", "journal.py")), false);
  assert.equal(global.root, path.join(f.userDir, "runtime"));
  assert.ok(fs.existsSync(path.join(global.toolsRoot, "journal.py")));
  assert.ok(fs.existsSync(path.join(global.schemaRoot, "schema.yaml")));
  assert.equal(global.manifest.scope, "global");
  assert.ok(global.files.every(({ path: target }) => within(global.root, target)));
});

test("local and legacy payloads have independent local layout without user runtime", (t) => {
  const f = fixture(t);
  const first = f.store("store-a");
  const second = f.store("store-b");
  const local = f.payload("local", { store: first });
  const legacy = f.payload("local", { store: second, legacy: true });
  assert.equal(local.root, path.join(first.root, ".symphysis"));
  assert.ok(fs.existsSync(path.join(local.schemaRoot, "schema.yaml")));
  assert.ok(fs.existsSync(path.join(first.root, ".claude", "skills", "symphysis-brainstorm", "SKILL.md")));
  assert.ok(fs.existsSync(local.manifestPath));
  assert.equal(legacy.manifestPath, null);
  assert.equal(fs.existsSync(path.join(legacy.root, "install-manifest.json")), false);
  assert.ok(fs.existsSync(path.join(legacy.toolsRoot, "journal.py")));
  assert.equal(fs.existsSync(path.join(f.userDir, "runtime")), false);
});

test("caller can copy an explicit payload and supply a corrupt manifest without changing the source", (t) => {
  const f = fixture(t);
  const source = f.at("supplied-payload");
  const bytes = Buffer.from([0, 255, 10, 128]);
  f.write(path.join(source, "tools", "binary.dat"), bytes);
  const installed = f.payload("global", { payloadDir: source, manifest: { format: 99 } });
  assert.deepEqual(fs.readFileSync(path.join(installed.toolsRoot, "binary.dat")), bytes);
  assert.deepEqual(JSON.parse(fs.readFileSync(installed.manifestPath, "utf8")), { format: 99 });
  assert.deepEqual(fs.readFileSync(path.join(source, "tools", "binary.dat")), bytes);
});

test("guarded writes and cleanup refuse a junction or symlink without touching its destination", (t) => {
  const f = fixture(t);
  const outside = fixture(t);
  const target = outside.at("foreign");
  fs.mkdirSync(target);
  fs.writeFileSync(path.join(target, "keep.txt"), "keep");
  const link = f.at("redirect");
  fs.symlinkSync(target, link, process.platform === "win32" ? "junction" : "dir");
  try {
    assert.throws(() => f.write(path.join(link, "bad.txt"), "bad"), /link/);
    assert.throws(() => f.cleanup(), /link/);
    assert.deepEqual(fs.readdirSync(target), ["keep.txt"]);
  } finally {
    fs.unlinkSync(link);
  }
});

test("pinned OpenSpec context resolves two fixture stores and a config-only pointer", { skip: !fs.existsSync(fork) }, (t) => {
  const f = fixture(t);
  const first = f.store("store-a");
  const second = f.store("store-b", { dataOnly: true });
  const pointer = f.pointer("source-a", first.id);
  const run = (cwd, ...args) => {
    const result = spawnSync(process.execPath, [fork, "context", ...args, "--json"], { cwd, env: f.env, encoding: "utf8", timeout: 15000 });
    assert.equal(result.status, 0, result.stderr || result.error?.message);
    return JSON.parse(result.stdout);
  };
  for (const store of [first, second]) assert.equal(path.resolve(run(store.root).root.path), store.root);
  const context = run(pointer);
  assert.equal(path.resolve(context.root.path), first.root);
  assert.equal(context.root.source, "declared");
  assert.equal(path.resolve(run(pointer, "--store", second.id).root.path), second.root);
  assert.deepEqual(fs.readdirSync(path.join(pointer, "openspec")), ["config.yaml"]);
});
