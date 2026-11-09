import { test } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { createRuntimeFixture } from "../test-support/runtime-fixture.js";
import { installationFiles } from "../test-support/installation-fixture.js";
import { normalizeInstallationRequest, installationHash } from "../lib/installation-plan.js";
import { clientTargets } from "../lib/client-targets.js";
import { acquireWriter } from "../lib/runtime-leases.js";
import { forkPin, spawnTool } from "../lib/openspec-bin.js";
import { resolveRuntime } from "../lib/runtime-resolver.js";
import { previewMigration } from "../lib/migration-plan.js";
import { applyMigrationPlan, recoverMigration } from "../lib/migration-transaction.js";

const repository = fileURLToPath(new URL("../../", import.meta.url));
const moduleURL = new URL("../lib/migration-transaction.js", import.meta.url).href;
const fork = path.join(repository, "upstream", "openspec", "bin", "openspec.js");
const bin = path.join(repository, "installer", "bin", "symphysis.js");
const blobs = new Map();
function oldBlob(source) {
  if (!blobs.has(source)) {
    const result = spawnTool("git", ["-C", repository, "show", `a19a4272fcce49c3cbee1aec6feeb4193748947c:${source}`], { encoding: null });
    assert.equal(result.status, 0); blobs.set(source, Buffer.from(result.stdout));
  }
  return blobs.get(source);
}
function fixture(t, { to = "global", legacy = false, flat = false, privateData = false } = {}) {
  const f = createRuntimeFixture(path.join(os.tmpdir(), "symphysis-migration-transaction-tests"));
  t.after(() => f.cleanup()); f.env.SYMPHYSIS_OPENSPEC = fork;
  const store = f.store("store-a"), other = f.store("store-b"), source = f.pointer("source", store.id);
  const global = f.payload("global");
  const config = f.write(path.join(global.root, "openspec", "config.symphysis.yaml"), "schema: symphysis\nrules:\n  specs:\n    - Migration fixture rule\n");
  global.manifest.files.push({ path: config, source: "openspec/config.symphysis.yaml", purpose: "config", sha256: installationHash(fs.readFileSync(config)) });
  const extend = (payload, scope) => {
    const clients = clientTargets({ scope, project: store.root, clients: ["claude"], env: f.env });
    const request = normalizeInstallationRequest({ scope, root: scope === "global" ? f.userDir : payload.root, runtimeRoot: payload.root, storeRoot: scope === "global" ? null : store.root, schemaDirectory: f.at("user-data", "openspec", "schemas"), sourceVersion: "0.1.0-fixture", openspecPin: forkPin().openspecPin, clients, ...(scope === "global" ? { bootstrap: { command: process.execPath, args: [bin] } } : {}) });
    Object.assign(payload.manifest, request); f.json(payload.manifestPath, payload.manifest);
  };
  extend(global, "global");
  f.write(f.at("user-data", "openspec", "schemas", "symphysis", "schema.yaml"), fs.readFileSync(path.join(global.schemaRoot, "schema.yaml")));
  let local;
  if (to === "global" && !legacy) { local = f.payload("local", { store }); extend(local, "local"); }
  if (legacy) {
    const runtime = flat ? store.root : path.join(store.root, ".symphysis");
    for (const source of ["cli/journal.py", "cli/journal_cli.py", "decisions/journal_model.py", "decisions/journal_render.py", "roots/roots.py", "openspec-run/openspec_run.py", "trace/trace_graph.py", "anchors/anchor_refs.py", "step-help/step_help.py", "settings/symphysis_config.py"]) f.write(path.join(runtime, "tools", path.basename(source)), oldBlob(source));
    f.write(path.join(store.root, "openspec", "schemas", "symphysis", "schema.yaml"), oldBlob("openspec/schemas/symphysis/schema.yaml"));
  }
  if (privateData) {
    for (const [name, value] of [["symphysis.yaml", "# opaque fixture settings\n"], [flat ? "tools/journal-roots.json" : ".symphysis/tools/journal-roots.json", "{}\n"], [".symphysis/viewer/draft.txt", "viewer draft\n"], ["answers/reply.md", "human word\n"]]) f.write(path.join(store.root, name), value);
  }
  const root = path.join(store.root, ".symphysis");
  const options = { project: source, to, env: f.env, sourceRoot: f.at("no-source") };
  const preview = previewMigration(options);
  assert.equal(preview.ready, true, JSON.stringify(preview.conflicts));
  return { f, store, other, source, global, local, root, preview, options, pending: path.join(root, ".migration-transaction.json"), claim: path.join(root, ".migration-recovery.json"), receipt: path.join(root, "migration.json") };
}
function crash(state, mode, step, index) {
  const saved = state.f.json(state.f.at("review-plan.json"), state.preview);
  const script = state.f.write(state.f.at("migration-worker.mjs"), `
import fs from "node:fs";
import {applyMigrationPlan,recoverMigration} from ${JSON.stringify(moduleURL)};
const options={project:process.env.FIXTURE_PROJECT,env:process.env,sourceRoot:process.env.FIXTURE_SOURCE,fault(event){if(event.name===process.env.FIXTURE_STEP&&(!process.env.FIXTURE_INDEX||event.index===Number(process.env.FIXTURE_INDEX)))process.exit(75);}};
if(process.env.FIXTURE_MODE==="recover")recoverMigration(options);else applyMigrationPlan(JSON.parse(fs.readFileSync(process.env.FIXTURE_PLAN,"utf8")),{...options,confirm:true});
`);
  const result = spawnSync(process.execPath, [script], { cwd: state.source, env: { ...state.f.env, FIXTURE_PROJECT: state.source, FIXTURE_SOURCE: state.options.sourceRoot, FIXTURE_MODE: mode, FIXTURE_STEP: step, FIXTURE_INDEX: index === undefined ? "" : String(index), FIXTURE_PLAN: saved }, encoding: "utf8", timeout: 45000 });
  assert.equal(result.status, 75, `${result.stdout}\n${result.stderr}`);
  return fs.existsSync(state.pending) ? JSON.parse(fs.readFileSync(state.pending, "utf8")) : null;
}
const recover = (state, extra = {}) => recoverMigration({ project: state.source, env: state.f.env, ...extra });
const changed = (state) => state.preview.files.filter((file) => !["unchanged", "preserve"].includes(file.action));
function assertClean(state, { foreignLease = false } = {}) {
  for (const file of [state.pending, state.claim, path.join(state.root, ".install-lock")]) assert.equal(fs.existsSync(file), false, file);
  if (!foreignLease) { assert.deepEqual(fs.readdirSync(path.join(state.f.userDir, ".leases")), []); acquireWriter({ root: state.f.userDir }).release(); }
  acquireWriter({ root: state.root }).release();
}

for (const to of ["global", "local"]) test(`managed migration to ${to} keeps project data, uses the selected pointer and leaves global files intact`, (t) => {
  const state = fixture(t, { to, privateData: true });
  const beforeGlobal = installationFiles(state.f.userDir), beforeOther = installationFiles(state.other.root), beforeSource = installationFiles(state.source);
  const personal = ["symphysis.yaml", ".symphysis/tools/journal-roots.json", ".symphysis/viewer/draft.txt", "answers/reply.md", "openspec/changes/same-change/decisions.json"].map((name) => [name, fs.readFileSync(path.join(state.store.root, name))]);
  const result = applyMigrationPlan(state.preview, { ...state.options, confirm: true });
  assert.equal(result.to, to); assert.equal(result.storeRoot, state.store.root);
  assert.deepEqual(installationFiles(state.f.userDir), beforeGlobal);
  assert.deepEqual(installationFiles(state.other.root), beforeOther); assert.deepEqual(installationFiles(state.source), beforeSource);
  for (const [name, bytes] of personal) assert.deepEqual(fs.readFileSync(path.join(state.store.root, name)), bytes);
  assert.equal(fs.existsSync(path.join(state.root, "install-manifest.json")), to === "local");
  const selected = resolveRuntime({ project: state.source, env: state.f.env });
  assert.equal(selected.scope, to); assert.equal(selected.status, "ready", JSON.stringify(selected.diagnostics));
  assert.deepEqual(JSON.parse(fs.readFileSync(state.receipt, "utf8")), { format: 1, from: to === "local" ? "global" : "local", to, runtimeApi: 1, schemaApi: 1 });
  assertClean(state);
});

for (const flat of [false, true]) test(`known legacy migration retires only proven files, flat=${flat}`, (t) => {
  const state = fixture(t, { legacy: true, flat, privateData: true });
  const before = fs.readFileSync(path.join(state.store.root, "symphysis.yaml"));
  const map = path.join(state.store.root, flat ? "tools/journal-roots.json" : ".symphysis/tools/journal-roots.json");
  const mapBefore = fs.readFileSync(map);
  applyMigrationPlan(state.preview, { ...state.options, confirm: true });
  const selected = resolveRuntime({ project: state.source, env: state.f.env });
  assert.equal(selected.scope, "global"); assert.equal(selected.status, "ready", JSON.stringify(selected.diagnostics));
  assert.deepEqual(fs.readFileSync(path.join(state.store.root, "symphysis.yaml")), before);
  assert.deepEqual(fs.readFileSync(map), mapBefore);
  if (flat) assert.equal(fs.existsSync(path.join(state.root, "tools", "journal-roots.json")), false);
  assert.equal(fs.existsSync(path.join(state.root, "install-manifest.json")), false);
  assertClean(state);
});

for (const step of ["journal", "stage-open", "stage-written", "backup-open", "backup-copied", "target-removed", "target-published"]) test(`migration crash at ${step} rolls back with a resolvable planning config`, (t) => {
  const state = fixture(t);
  const before = installationFiles(state.store.root), beforeGlobal = installationFiles(state.f.userDir);
  const record = crash(state, "apply", step);
  assert.equal(record.kind, "migration");
  assert.equal(fs.existsSync(record.reader.descriptor.file), true);
  assert.equal(resolveRuntime({ project: state.source, env: state.f.env }).diagnostics[0].code, "installation-busy");
  assert.equal(recover(state).action, "rolled-back");
  assert.deepEqual(installationFiles(state.store.root), before); assert.deepEqual(installationFiles(state.f.userDir), beforeGlobal);
  assertClean(state);
});

test("crash after removing the local manifest rolls back without publishing an empty retirement manifest", (t) => {
  const state = fixture(t);
  const before = installationFiles(state.store.root);
  const index = changed(state).findIndex((file) => file.kind === "source-manifest");
  crash(state, "apply", "target-removed", index);
  assert.equal(fs.existsSync(path.join(state.root, "install-manifest.json")), false);
  assert.equal(recover(state).action, "rolled-back");
  assert.deepEqual(installationFiles(state.store.root), before); assertClean(state);
});

for (const step of ["recovery-claimed", "recovery-backup-restored", "recovery-stage-removed", "recovery-resources-cleaned", "recovery-reader-unlinked", "recovery-reader-recorded", "recovery-writer-unlinked", "recovery-writer-recorded", "recovery-pending-unlinked", "recovery-pending-recorded"]) test(`migration recovery resumes after its own process exits at ${step}`, (t) => {
  const state = fixture(t); const before = installationFiles(state.store.root);
  crash(state, "apply", "target-removed"); crash(state, "recover", step);
  assert.equal(recover(state).action, "rolled-back");
  assert.deepEqual(installationFiles(state.store.root), before); assertClean(state);
});

for (const step of ["receipt-published", "cleanup-receipt-published", "cleanup-reader-unlinked", "cleanup-writer-unlinked", "cleanup-pending-unlinked"]) test(`published migration resumes normal cleanup after process exit at ${step}`, (t) => {
  const state = fixture(t); crash(state, "apply", step);
  assert.equal(recover(state).action, "completed");
  assert.equal(resolveRuntime({ project: state.source, env: state.f.env }).scope, "global"); assertClean(state);
});

test("rollback after a created project data target remains repeatable", (t) => {
  const state = fixture(t), before = installationFiles(state.store.root);
  const index = changed(state).findIndex((file) => file.kind === "initial-settings");
  assert.ok(index >= 0);
  crash(state, "apply", "target-published", index); crash(state, "recover", "recovery-target-removed");
  assert.equal(recover(state).action, "rolled-back"); assert.deepEqual(installationFiles(state.store.root), before); assertClean(state);
});

for (const step of ["backup-open", "target-published", "receipt-published", "cleanup-reader-unlinked"]) test(`global-to-local crash at ${step} recovers a complete scope`, (t) => {
  const state = fixture(t, { to: "local" }), before = installationFiles(state.store.root), global = installationFiles(state.f.userDir);
  crash(state, "apply", step);
  const result = recover(state);
  assert.equal(result.action, ["receipt-published", "cleanup-reader-unlinked"].includes(step) ? "completed" : "rolled-back");
  if (result.action === "rolled-back") assert.deepEqual(installationFiles(state.store.root), before);
  assert.deepEqual(installationFiles(state.f.userDir), global);
  const selected = resolveRuntime({ project: state.source, env: state.f.env });
  assert.equal(selected.scope, result.action === "completed" ? "local" : "global"); assert.equal(selected.status, "ready", JSON.stringify(selected.diagnostics));
  assertClean(state);
});

for (const to of ["global", "local"]) test(`recovery refuses an incomplete ${to} registry without changing files`, (t) => {
  const state = fixture(t, { to }); const record = crash(state, "apply", "journal");
  if (to === "global") {
    record.operations.shift();
    record.operations.forEach((operation, index) => {
      operation.stage = operation.afterHash === null ? null : path.join(path.dirname(operation.path), `.symphysis-migrate-${record.id}-${index}.stage`);
      operation.backup = operation.before.hash === null ? null : path.join(path.dirname(operation.path), `.symphysis-migrate-${record.id}-${index}.backup`);
    });
  }
  else {
    const row = record.target.value.files[0];
    record.target.value.files.push({ ...row, source: "tools/unplanned.py", path: path.join(state.root, "tools", "unplanned.py") });
    record.operations.find((operation) => operation.kind === "manifest").afterHash = installationHash(Buffer.from(`${JSON.stringify(record.target.value, null, 2)}\n`));
  }
  state.f.json(state.pending, record);
  const before = installationFiles(state.f.root);
  assert.throws(() => recover(state), { code: "migration-recovery-required" });
  assert.deepEqual(installationFiles(state.f.root), before);
});

test("a global update after verified reader cleanup does not strand the finished store migration", (t) => {
  const state = fixture(t); crash(state, "apply", "cleanup-reader-unlinked");
  const writer = acquireWriter({ root: state.f.userDir });
  try {
    const manifest = JSON.parse(fs.readFileSync(state.global.manifestPath, "utf8"));
    manifest.generation = "later-global-generation"; state.f.json(state.global.manifestPath, manifest);
  } finally { writer.release(); }
  assert.equal(recover(state).action, "completed"); assertClean(state);
  assert.equal(resolveRuntime({ project: state.source, env: state.f.env }).runtime.generation, "later-global-generation");
});

for (const to of ["local", "global"]) test(`published ${to} targets changed or deleted by the user are preserved`, (t) => {
  for (const deleted of [false, true]) {
    const state = fixture(t, { to }); const record = crash(state, "apply", "receipt-published");
    const file = record.operations.find((operation) => operation.kind === "migration-receipt").path;
    if (deleted) fs.unlinkSync(file); else fs.writeFileSync(file, "user changed receipt\n");
    const before = installationFiles(state.f.root);
    assert.throws(() => recover(state), { code: "migration-recovery-required" }); assert.deepEqual(installationFiles(state.f.root), before);
  }
});

test("same-byte inode replacement, foreign reader and partial journal state cannot be pruned", (t) => {
  for (const flaw of ["target-inode", "reader-inode", "partial-journal"]) {
    const state = fixture(t), record = crash(state, "apply", "target-removed");
    if (flaw === "partial-journal") state.f.write(path.join(state.root, ".migration-record-partial.tmp"), "{");
    else {
      const file = flaw === "reader-inode" ? record.reader.descriptor.file : record.operations.find((operation) => operation.stage && fs.existsSync(operation.stage)).stage;
      const replacement = state.f.write(state.f.at("replacement"), fs.readFileSync(file)); fs.unlinkSync(file); fs.renameSync(replacement, file);
    }
    const before = installationFiles(state.f.root);
    assert.throws(() => recover(state)); assert.deepEqual(installationFiles(state.f.root), before);
  }
});

test("recovery never removes an unrelated global reader or a live/reused recovery owner", (t) => {
  const state = fixture(t); crash(state, "apply", "target-removed");
  const foreign = state.f.write(path.join(state.f.userDir, ".leases", "foreign.json"), "foreign lease\n");
  crash(state, "recover", "recovery-claimed");
  const claim = JSON.parse(fs.readFileSync(state.claim, "utf8")); claim.owner.pid = process.pid; state.f.json(state.claim, claim);
  const before = installationFiles(state.f.root); assert.throws(() => recover(state), { code: "installation-busy" }); assert.deepEqual(installationFiles(state.f.root), before);
  claim.owner.pid = 2147483647; state.f.json(state.claim, claim);
  assert.equal(recover(state).action, "rolled-back"); assert.equal(fs.readFileSync(foreign, "utf8"), "foreign lease\n"); assertClean(state, { foreignLease: true });
});
