import { test } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { createRuntimeFixture } from "../test-support/runtime-fixture.js";
import { installationFiles } from "../test-support/installation-fixture.js";
import { installationSnapshot } from "../lib/installation-plan.js";
import { runOpenspec } from "../lib/openspec-bin.js";
import { resolveMigrationContext, resolveRuntime } from "../lib/runtime-resolver.js";

const fork = fileURLToPath(new URL("../../upstream/openspec/bin/openspec.js", import.meta.url));
function fixture(t, { local = true, global = true, legacy = false, declaration = false } = {}) {
  const f = createRuntimeFixture(path.join(os.tmpdir(), "symphysis-migration-context-tests"));
  t.after(() => f.cleanup()); f.env.SYMPHYSIS_OPENSPEC = fork;
  const store = f.store("store-a", { declaration });
  const source = f.pointer("source", store.id);
  const ownLocal = local ? f.payload("local", { store, legacy }) : null;
  const ownGlobal = global ? f.payload("global") : null;
  if (ownGlobal) f.write(f.at("user-data", "openspec", "schemas", "symphysis", "schema.yaml"), fs.readFileSync(path.join(ownGlobal.schemaRoot, "schema.yaml")));
  const calls = [];
  const run = (args, options) => { calls.push({ args, options }); return runOpenspec(args, options); };
  const options = { project: source, to: "global", env: f.env, run };
  return { f, store, source, local: ownLocal, global: ownGlobal, calls, options };
}
function proof(source) {
  const manifest = JSON.parse(fs.readFileSync(source.runtime.manifestPath, "utf8"));
  return { root: source.runtime.schemaRoot, manifestPath: source.runtime.manifestPath, generation: manifest.generation,
    files: manifest.files.filter((entry) => entry.source.startsWith("openspec/schemas/symphysis/")).map((entry) => ({ path: entry.path, sha256: entry.sha256, snapshot: installationSnapshot(entry.path) })) };
}

test("management preview uses one native planning root and never changes public local priority", (t) => {
  const state = fixture(t); const before = installationFiles(state.f.root);
  const result = resolveMigrationContext({ ...state.options, schemaRemovalProof: proof });
  assert.equal(result.operationReady, true, JSON.stringify(result.diagnostics));
  assert.equal(result.managementOnly, true); assert.equal(result.sourceContext.scope, "local");
  assert.equal(result.sourceContext.runtime.root, state.local.root); assert.equal(result.candidateContext.runtime.root, state.global.root);
  assert.equal(result.sourceContext.status, "blocked"); assert.equal(result.candidateContext.status, "blocked");
  assert.equal(result.planningRoot.root, state.store.root);
  assert.equal(state.calls.filter(({ args }) => args[0] === "context").length, 1);
  assert.deepEqual(installationFiles(state.f.root), before);
  assert.equal(resolveRuntime({ project: state.source, env: state.f.env }).scope, "local");
});

test("a local schema shadow needs complete verified removal proof", (t) => {
  const state = fixture(t);
  const result = resolveMigrationContext(state.options);
  assert.equal(result.operationReady, false);
  assert.ok(result.diagnostics.some((item) => item.code === "migration-ownership-unconfirmed"));
  assert.equal(result.candidateContext.scope, "global"); assert.equal(result.candidateContext.status, "blocked");
});

for (const flaw of ["generation", "partial", "unknown-file", "modified-file", "replaced-inode", "manifest-generation-race"]) test(`migration removal proof ${flaw} refuses and preserves files`, (t) => {
  const state = fixture(t);
  const result = resolveMigrationContext({ ...state.options, schemaRemovalProof(source) {
    const value = proof(source);
    if (flaw === "generation") value.generation = "other-generation";
    if (flaw === "partial") value.files.pop();
    if (flaw === "unknown-file") state.f.write(path.join(source.runtime.schemaRoot, "foreign.txt"), "foreign\n");
    if (flaw === "modified-file") fs.writeFileSync(value.files[0].path, "changed after preview\n");
    if (flaw === "replaced-inode") { const next = state.f.write(state.f.at("replacement-schema"), fs.readFileSync(value.files[0].path)); fs.unlinkSync(value.files[0].path); fs.renameSync(next, value.files[0].path); }
    if (flaw === "manifest-generation-race") { const manifest = JSON.parse(fs.readFileSync(value.manifestPath, "utf8")); manifest.generation = "changed-after-preview"; state.f.json(value.manifestPath, manifest); }
    return value;
  } });
  assert.equal(result.operationReady, false);
  assert.ok(result.diagnostics.some((item) => item.code === "migration-proof-invalid"), JSON.stringify(result.diagnostics));
  assert.equal(result.sourceContext.scope, "local"); assert.equal(fs.existsSync(state.local.manifestPath), true);
});

test("a good local removal proof does not excuse a bad native user projection", (t) => {
  const state = fixture(t);
  const user = state.f.at("user-data", "openspec", "schemas", "symphysis", "schema.yaml");
  state.f.write(user, "name: other\nversion: 1\n");
  const before = installationFiles(state.f.root);
  const result = resolveMigrationContext({ ...state.options, schemaRemovalProof: proof });
  assert.equal(result.operationReady, false);
  assert.ok(result.diagnostics.some((item) => item.code === "schema-source-conflict"));
  assert.deepEqual(installationFiles(state.f.root), before);
});

test("missing global runtime requests explicit install, never a fallback or implicit initialization", (t) => {
  const state = fixture(t, { global: false });
  const before = installationFiles(state.f.root);
  const result = resolveMigrationContext({ ...state.options, schemaRemovalProof: proof });
  assert.equal(result.operationReady, false);
  assert.ok(result.diagnostics.some((item) => item.code === "runtime-missing" && item.action.includes("install --scope global")));
  assert.deepEqual(installationFiles(state.f.root), before);
});

test("legacy local without an ownership manifest is a preview conflict", (t) => {
  const state = fixture(t, { legacy: true });
  const result = resolveMigrationContext(state.options);
  assert.equal(result.operationReady, false);
  assert.ok(result.diagnostics.some((item) => item.code === "migration-ownership-unconfirmed"));
  assert.equal(result.sourceContext.runtime.legacy, true);
});

test("already missing owned schema files need no deletion and do not excuse unknown actual files", (t) => {
  const state = fixture(t);
  const file = path.join(state.local.schemaRoot, "steps.md");
  state.local.manifest.files.push({ path: file, source: "openspec/schemas/symphysis/steps.md", purpose: "schema", sha256: "a".repeat(64) });
  state.f.json(state.local.manifestPath, state.local.manifest);
  const result = resolveMigrationContext({ ...state.options, schemaRemovalProof: proof });
  assert.equal(result.operationReady, true, JSON.stringify(result.diagnostics));
  assert.equal(result.candidateContext.compatibility.status, "unconfirmed");
});

test("to-local exposes only source/planning/API base before the package candidate plan", (t) => {
  const state = fixture(t, { local: false, declaration: true });
  const before = installationFiles(state.f.root);
  const result = resolveMigrationContext({ ...state.options, to: "local" });
  assert.equal(result.operationReady, true, JSON.stringify(result.diagnostics));
  assert.equal(result.candidateContext, null); assert.equal(result.sourceContext.scope, "global");
  assert.equal(result.sourceContext.status, "blocked");
  assert.equal(state.calls.filter(({ args }) => args[0] === "context").length, 1);
  assert.deepEqual(installationFiles(state.f.root), before);
});

for (const flaw of ["declaration-missing", "declaration-incompatible", "schema-source-conflict", "resource-missing"]) test(`migration never repairs authoritative global source ${flaw}`, (t) => {
  const state = fixture(t, { local: false, declaration: true });
  if (flaw === "declaration-missing") fs.unlinkSync(path.join(state.store.root, "openspec", "symphysis.json"));
  if (flaw === "declaration-incompatible") state.f.json(path.join(state.store.root, "openspec", "symphysis.json"), { format: 1, runtimeApi: 2, schemaApi: 1 });
  if (flaw === "schema-source-conflict") state.f.write(state.f.at("user-data", "openspec", "schemas", "symphysis", "schema.yaml"), "name: changed\nversion: 1\n");
  if (flaw === "resource-missing") fs.unlinkSync(path.join(state.global.toolsRoot, "journal.py"));
  const before = installationFiles(state.f.root);
  const result = resolveMigrationContext({ ...state.options, to: "local" });
  assert.equal(result.operationReady, false);
  assert.equal(result.candidateContext, null);
  assert.ok(result.diagnostics.some((issue) => issue.code === flaw), JSON.stringify(result.diagnostics));
  assert.deepEqual(installationFiles(state.f.root), before);
});

test("migration refuses a damaged authoritative local source before candidate selection", (t) => {
  const state = fixture(t);
  fs.writeFileSync(path.join(state.local.toolsRoot, "journal.py"), "changed\n");
  let called = false;
  const result = resolveMigrationContext({ ...state.options, schemaRemovalProof() { called = true; return null; } });
  assert.equal(result.operationReady, false); assert.equal(result.candidateContext, null); assert.equal(called, false);
  assert.ok(result.diagnostics.some((issue) => issue.code === "local-damaged"));
});

for (const value of ["not-json", { format: 1, runtimeApi: 2, schemaApi: 1 }]) test("local-to-global cannot repair an existing incompatible store declaration", (t) => {
  const state = fixture(t);
  const file = path.join(state.store.root, "openspec", "symphysis.json");
  if (typeof value === "string") state.f.write(file, value); else state.f.json(file, value);
  const result = resolveMigrationContext({ ...state.options, schemaRemovalProof: proof });
  assert.equal(result.operationReady, false); assert.equal(result.candidateContext, null);
  assert.ok(result.diagnostics.some((issue) => issue.code === "declaration-incompatible"));
});

test("JSON callbacks and unknown targets are refused before native discovery", (t) => {
  const state = fixture(t);
  for (const options of [{ schemaRemovalProof: {} }, { schemaRemovalProof: "function" }, { to: "other" }]) {
    const result = resolveMigrationContext({ ...state.options, ...options });
    assert.equal(result.operationReady, false); assert.equal(result.planningRoot, null);
  }
  assert.equal(state.calls.length, 0);
});
