import { test } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { createHash } from "node:crypto";
import { spawnSync } from "node:child_process";
import { createRuntimeFixture } from "../test-support/runtime-fixture.js";
import { resolveRuntime } from "../lib/runtime-resolver.js";
import { checkRuntimeCompatibility } from "../lib/runtime-compatibility.js";
import { acquireReader, acquireWriter } from "../lib/runtime-leases.js";

const fork = fileURLToPath(new URL("../../upstream/openspec/bin/openspec.js", import.meta.url));
const bin = fileURLToPath(new URL("../bin/symphysis.js", import.meta.url));
const schema = "name: symphysis\nversion: 1\ndescription: Fixture\nartifacts:\n  - id: intent\n    generates: intent.md\n    description: Intent\n    template: intent.md\n    requires: []\n";
const hash = (bytes) => createHash("sha256").update(bytes).digest("hex");
function fixture(t, scope = "local") {
  const f = createRuntimeFixture(path.join(os.tmpdir(), "symphysis-optional-resource-tests"));
  t.after(() => f.cleanup()); f.env.SYMPHYSIS_OPENSPEC = fork;
  const store = f.store("store-a"); const payload = f.payload(scope, { store });
  const add = (source, text, projection = false) => {
    const file = projection ? f.at("user-data", "openspec", "schemas", "symphysis", source.slice("openspec/schemas/symphysis/".length)) : scope === "local" && source.startsWith("openspec/") ? path.join(store.root, source) : path.join(payload.root, source);
    f.write(file, text);
    const entry = { path: file, source, sha256: hash(Buffer.from(text)), purpose: source.startsWith("tools/") ? "tool" : "schema", ...(projection ? { projection: true } : {}) };
    const existing = payload.manifest.files.findIndex((item) => item.path === file);
    if (existing === -1) payload.manifest.files.push(entry); else payload.manifest.files[existing] = entry;
    return file;
  };
  add("openspec/schemas/symphysis/schema.yaml", schema);
  add("openspec/schemas/symphysis/steps.md", "## intent\nFixture text\n");
  const mermaid = add("tools/mermaid.min.js", "globalThis.mermaid = {};\n");
  add("tools/mermaid.LICENSE", "MIT fixture\n");
  const version = add("tools/symphysis-version.txt", "0.1.0-fixture\n");
  add("tools/journal.py", "print('journal-ok')\n");
  if (scope === "global") {
    add("openspec/schemas/symphysis/schema.yaml", schema, true);
    add("openspec/schemas/symphysis/steps.md", "## intent\nFixture text\n", true);
  }
  f.json(payload.manifestPath, payload.manifest);
  const resolve = () => resolveRuntime({ project: store.root, env: f.env });
  const cli = (...args) => spawnSync(process.execPath, [bin, "--project", store.root, ...args], { cwd: f.root, env: f.env, encoding: "utf8", timeout: 15000 });
  return { f, store, payload, add, mermaid, version, resolve, cli };
}

for (const missing of [false, true]) test(`local Mermaid ${missing ? "missing" : "hash mismatch"} selects text fallback without borrowing global bytes`, (t) => {
  const state = fixture(t); state.f.payload("global");
  if (missing) fs.unlinkSync(state.mermaid); else fs.writeFileSync(state.mermaid, "unverified script bytes\n");
  const result = state.resolve();
  assert.equal(result.status, "ready", JSON.stringify(result.diagnostics));
  assert.equal(result.scope, "local"); assert.equal(result.resources.assets.mermaid, undefined);
  assert.ok(result.warnings.some((item) => item.source === "tools/mermaid.min.js" && item.path === state.mermaid));
  assert.deepEqual(result.diagnostics, []);
  assert.equal(state.cli("journal", "view-json", state.store.journal).stdout.trim(), "journal-ok");
});

for (const missing of [false, true]) test(`local help ${missing ? "missing" : "untrusted"} leaves journal ready and cannot execute`, (t) => {
  const state = fixture(t); const helper = path.join(state.payload.toolsRoot, "step_help.py");
  const marker = state.f.at("must-not-execute.txt");
  if (missing) fs.unlinkSync(helper); else fs.writeFileSync(helper, `from pathlib import Path\nPath(${JSON.stringify(marker)}).write_text('executed')\n`);
  const result = state.resolve();
  assert.equal(result.status, "ready", JSON.stringify(result.diagnostics)); assert.equal(result.resources.tools.help, undefined);
  assert.ok(result.warnings.some((item) => item.source === "tools/step_help.py"));
  const help = state.cli("help", "--change", state.store.change);
  assert.equal(help.status, 2); assert.match(help.stderr, /resource-missing/); assert.equal(help.stdout, "");
  assert.equal(fs.existsSync(marker), false);
  const journal = state.cli("journal", "view-json", state.store.journal);
  assert.equal(journal.status, 0, journal.stderr); assert.equal(journal.stdout.trim(), "journal-ok");
});

test("local informational version does not create an integrity warning or failure", (t) => {
  const state = fixture(t);
  for (const missing of [false, true]) {
    if (missing) fs.unlinkSync(state.version); else fs.writeFileSync(state.version, "0.0.1+different\n");
    const result = state.resolve();
    assert.equal(result.status, "ready", JSON.stringify(result.diagnostics));
    assert.equal(result.warnings.some((item) => item.source === "tools/symphysis-version.txt"), false);
    assert.equal(result.resources.assets.version, undefined);
  }
});

for (const source of ["tools/mermaid.min.js", "tools/step_help.py", "tools/symphysis-version.txt"]) test(`global ${source} remains strict`, (t) => {
  const state = fixture(t, "global"); const target = state.payload.manifest.files.find((entry) => entry.source === source).path;
  fs.writeFileSync(target, "changed outside installer\n");
  const result = state.resolve();
  assert.equal(result.status, "blocked"); assert.equal(result.diagnostics[0].code, "resource-missing");
  assert.equal(result.warnings.some((item) => item.path === target), false);
});

for (const scope of ["local", "global"]) test(`${scope}: missing registered steps permits empty texts, existing damaged steps remains fatal`, (t) => {
  const state = fixture(t, scope); const steps = path.join(state.payload.schemaRoot, "steps.md");
  fs.unlinkSync(steps);
  let result = state.resolve();
  assert.equal(result.status, "ready", JSON.stringify(result.diagnostics)); assert.equal(result.resources.assets.steps, undefined);
  assert.ok(result.warnings.some((item) => item.source === "openspec/schemas/symphysis/steps.md" && item.path === steps));
  fs.writeFileSync(steps, "present but corrupted\n"); result = state.resolve();
  assert.equal(result.status, "blocked"); assert.equal(result.warnings.some((item) => item.path === steps), false);
});

test("global projection may omit steps but a present projection is still checked against manifest", (t) => {
  const state = fixture(t, "global"); const projected = state.payload.manifest.files.find((entry) => entry.source.endsWith("/steps.md") && entry.projection).path;
  fs.unlinkSync(projected); assert.equal(state.resolve().status, "ready");
  fs.writeFileSync(projected, "corrupted projection\n"); assert.equal(state.resolve().status, "blocked");
  assert.equal(checkRuntimeCompatibility(state.resolve(), { env: state.f.env })[0].code, "schema-source-conflict");
});

test("essential Python and settings helpers remain mandatory and local never falls back", (t) => {
  for (const tool of ["journal.py", "symphysis_config.py"]) {
    const state = fixture(t); state.f.payload("global");
    fs.writeFileSync(path.join(state.payload.toolsRoot, tool), "changed\n");
    const result = state.resolve();
    assert.equal(result.status, "blocked"); assert.equal(result.scope, "local"); assert.equal(result.diagnostics[0].code, "local-damaged");
  }
});

test("partial store-init journals block readers and writers without automatic removal", (t) => {
  const state = fixture(t); const context = state.resolve();
  for (const name of [".store-init-record-partial.tmp", ".store-init-recovery-partial.tmp"]) {
    const file = state.f.write(path.join(state.payload.root, name), "partial\n");
    assert.throws(() => acquireReader(context), { code: "installation-busy" });
    assert.throws(() => acquireWriter({ root: state.payload.root }), { code: "installation-busy" });
    assert.equal(fs.readFileSync(file, "utf8"), "partial\n"); fs.unlinkSync(file);
  }
});
