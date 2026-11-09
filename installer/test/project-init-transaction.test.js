import { test } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { createRuntimeFixture } from "../test-support/runtime-fixture.js";
import { installationFiles } from "../test-support/installation-fixture.js";
import { installationHash } from "../lib/installation-plan.js";
import { acquireWriter } from "../lib/runtime-leases.js";
import { initProject, recoverProjectInitialization } from "../lib/project-init.js";

const moduleURL = new URL("../lib/project-init.js", import.meta.url).href;
const fork = fileURLToPath(new URL("../../upstream/openspec/bin/openspec.js", import.meta.url));
function fixture(t) {
  const f = createRuntimeFixture(path.join(os.tmpdir(), "symphysis-init-transaction-tests"));
  f.env.SYMPHYSIS_OPENSPEC = fork;
  const store = f.store("store-a", { declaration: false });
  const other = f.store("store-b");
  const source = f.pointer("source", store.id);
  const payload = f.payload("global");
  const config = f.write(path.join(payload.root, "openspec", "config.symphysis.yaml"), "schema: symphysis\nrules:\n  specs:\n    - Fixture rule\noperations:\n  apply:\n    guidance:\n      - Fixture guidance\n");
  payload.manifest.files.push({ path: config, source: "openspec/config.symphysis.yaml", purpose: "config", sha256: installationHash(fs.readFileSync(config)) });
  f.json(payload.manifestPath, payload.manifest);
  f.write(f.at("user-data", "openspec", "schemas", "symphysis", "schema.yaml"), fs.readFileSync(path.join(payload.schemaRoot, "schema.yaml")));
  const root = path.join(store.root, ".symphysis");
  const pending = path.join(root, ".store-init-transaction.json");
  const claim = path.join(root, ".store-init-recovery.json");
  t.after(() => f.cleanup());
  return { f, store, other, source, payload, root, pending, claim, options: { project: source, env: f.env } };
}
function crash(state, mode, step, index = undefined) {
  const script = state.f.write(state.f.at("crash-store-init.mjs"), `
import {initProject,recoverProjectInitialization} from ${JSON.stringify(moduleURL)};
const options={project:process.env.FIXTURE_PROJECT,env:process.env,fault(event){if(event.name===process.env.FIXTURE_FAULT&&(!process.env.FIXTURE_FAULT_INDEX||event.index===Number(process.env.FIXTURE_FAULT_INDEX)))process.exit(75);}};
if(process.env.FIXTURE_MODE==="recover")recoverProjectInitialization(options);else initProject(options);
`);
  const result = spawnSync(process.execPath, [script], { cwd: state.source, env: { ...state.f.env,
    FIXTURE_PROJECT: state.source, FIXTURE_MODE: mode, FIXTURE_FAULT: step, FIXTURE_FAULT_INDEX: index === undefined ? "" : String(index) }, encoding: "utf8", timeout: 15000 });
  assert.equal(result.status, 75, result.stderr);
  return fs.existsSync(state.pending) ? JSON.parse(fs.readFileSync(state.pending, "utf8")) : null;
}
const recover = (state) => recoverProjectInitialization(state.options);
function assertClean(state) {
  assert.equal(fs.existsSync(state.pending), false);
  assert.equal(fs.existsSync(state.claim), false);
  assert.equal(fs.existsSync(path.join(state.root, ".install-lock")), false);
  assert.equal(fs.existsSync(path.join(state.root, "install-manifest.json")), false);
  assert.deepEqual(fs.readdirSync(path.join(state.f.userDir, ".leases")), []);
  acquireWriter({ root: state.f.userDir }).release();
}

for (const step of ["journal", "stage-open", "stage-written", "backup-open", "backup-renamed", "target-renamed"]) {
  test(`verified init crash at ${step} restores store data and releases only its global reader`, (t) => {
    const state = fixture(t);
    const before = installationFiles(state.store.root);
    const other = installationFiles(state.other.root);
    const source = installationFiles(state.source);
    const record = crash(state, "init", step);
    assert.equal(record.kind, "store-init");
    assert.equal(fs.existsSync(record.reader.descriptor.file), true);
    assert.deepEqual(recover(state), { recovered: true, action: "rolled-back" });
    assert.deepEqual(installationFiles(state.store.root), before);
    assert.deepEqual(installationFiles(state.other.root), other);
    assert.deepEqual(installationFiles(state.source), source);
    assertClean(state);
  });
}

for (const step of ["recovery-claimed", "recovery-stage-removed", "recovery-target-removed", "recovery-backup-restored", "recovery-resources-cleaned", "recovery-reader-unlinked", "recovery-reader-recorded", "recovery-writer-unlinked", "recovery-pending-unlinked", "recovery-pending-recorded"]) {
  test(`init recovery itself resumes a process exit at ${step}`, (t) => {
    const state = fixture(t);
    const before = installationFiles(state.store.root);
    crash(state, "init", "target-renamed", step === "recovery-target-removed" ? 1 : undefined);
    crash(state, "recover", step);
    assert.deepEqual(recover(state), { recovered: true, action: "rolled-back" });
    assert.deepEqual(installationFiles(state.store.root), before);
    assertClean(state);
  });
}

for (const step of ["receipt-published", "cleanup-receipt-published", "cleanup-reader-unlinked", "cleanup-writer-unlinked", "cleanup-pending-unlinked"]) {
  test(`published init survives a process exit at ${step} without becoming a local runtime`, (t) => {
    const state = fixture(t);
    crash(state, "init", step);
    const data = installationFiles(state.store.root).filter(([file]) => !file.includes(".store-init-") && !file.includes("/.symphysis-init-") && !file.endsWith("/.install-lock"));
    assert.deepEqual(recover(state), { recovered: true, action: "completed" });
    assert.deepEqual(installationFiles(state.store.root), data);
    assert.ok(fs.existsSync(path.join(state.root, "store-init.json")));
    assertClean(state);
  });
}

test("a changed file after init publication is preserved, including explicit user deletion", (t) => {
  for (const deleted of [false, true]) {
    const state = fixture(t);
    const record = crash(state, "init", "receipt-published");
    const target = record.operations.find((operation) => operation.kind === "store-declaration").path;
    if (deleted) fs.unlinkSync(target); else fs.writeFileSync(target, "user changed declaration\n");
    const before = installationFiles(state.f.root);
    assert.throws(() => recover(state), { code: "store-initialization-conflict" });
    assert.deepEqual(installationFiles(state.f.root), before);
  }
});

test("same-bytes target replacement is preserved during init recovery", (t) => {
  const state = fixture(t);
  const record = crash(state, "init", "target-renamed");
  const current = record.operations[0].path;
  const replacement = state.f.write(state.f.at("replacement"), fs.readFileSync(current));
  fs.unlinkSync(current); fs.renameSync(replacement, current);
  const before = installationFiles(state.f.root);
  assert.throws(() => recover(state), { code: "store-initialization-conflict" });
  assert.deepEqual(installationFiles(state.f.root), before);
});

test("a live or reused recovery PID cannot take ownership of a store init claim", (t) => {
  const state = fixture(t);
  crash(state, "init", "target-renamed");
  crash(state, "recover", "recovery-claimed");
  const claim = JSON.parse(fs.readFileSync(state.claim, "utf8"));
  claim.owner.pid = process.pid;
  state.f.json(state.claim, claim);
  const before = installationFiles(state.f.root);
  assert.throws(() => recover(state), { code: "installation-busy" });
  assert.deepEqual(installationFiles(state.f.root), before);
});

test("a replaced global reader and a replaced claim do not become owned through matching bytes", (t) => {
  for (const which of ["reader", "claim"]) {
    const state = fixture(t);
    const record = crash(state, "init", "target-renamed");
    if (which === "claim") crash(state, "recover", "recovery-claimed");
    const file = which === "reader" ? record.reader.descriptor.file : state.claim;
    const replacement = state.f.write(state.f.at("replacement-proof.json"), fs.readFileSync(file));
    fs.unlinkSync(file); fs.renameSync(replacement, file);
    const before = installationFiles(state.f.root);
    assert.throws(() => recover(state), { code: "store-initialization-conflict" });
    assert.deepEqual(installationFiles(state.f.root), before);
  }
});

test("a parent junction never redirects init recovery into another directory", (t) => {
  const state = fixture(t);
  crash(state, "init", "target-renamed");
  const saved = state.f.at("saved-init-state");
  const foreign = state.f.at("foreign-init-state");
  state.f.write(path.join(foreign, "keep.txt"), "foreign\n");
  fs.renameSync(state.root, saved);
  fs.symlinkSync(foreign, state.root, process.platform === "win32" ? "junction" : "dir");
  try {
    assert.throws(() => recover(state), /reparse|ссылк/);
    assert.deepEqual(fs.readdirSync(foreign), ["keep.txt"]);
    assert.equal(fs.readFileSync(path.join(foreign, "keep.txt"), "utf8"), "foreign\n");
  } finally { fs.unlinkSync(state.root); fs.renameSync(saved, state.root); }
});

test("partial temporary init journals block a healthy owned recovery without removal", (t) => {
  const state = fixture(t);
  const record = crash(state, "init", "target-renamed");
  crash(state, "recover", "recovery-claimed");
  const claim = JSON.parse(fs.readFileSync(state.claim, "utf8"));
  for (const file of [path.join(state.root, `.store-init-record-${record.id}.tmp`), path.join(state.root, `.store-init-recovery-${claim.id}.tmp`)]) {
    state.f.write(file, "unconfirmed partial update\n");
    const before = installationFiles(state.f.root);
    assert.throws(() => recover(state), { code: "store-initialization-conflict" });
    assert.deepEqual(installationFiles(state.f.root), before);
    fs.unlinkSync(file);
  }
});

test("unrelated global leases are not pruned while the init's verified reader is released", (t) => {
  const state = fixture(t);
  const record = crash(state, "init", "stage-written");
  const foreign = state.f.write(path.join(state.f.userDir, ".leases", "foreign.json"), "foreign reader\n");
  assert.deepEqual(recover(state), { recovered: true, action: "rolled-back" });
  assert.equal(fs.existsSync(record.reader.descriptor.file), false);
  assert.equal(fs.readFileSync(foreign, "utf8"), "foreign reader\n");
});

test("foreign or malformed recovery/temporary records and tampered typed targets refuse without writes", (t) => {
  const state = fixture(t);
  const record = crash(state, "init", "target-renamed");
  record.operations[0].path = state.other.journal;
  state.f.json(state.pending, record);
  const before = installationFiles(state.f.root);
  assert.throws(() => recover(state), { code: "store-initialization-conflict" });
  assert.deepEqual(installationFiles(state.f.root), before);
  for (const [file, bytes] of [[state.claim, "{"], [path.join(state.root, ".store-init-record-partial.tmp"), "partial record\n"]]) {
    state.f.write(file, bytes);
    const snapshot = installationFiles(state.f.root);
    assert.throws(() => recover(state));
    assert.deepEqual(installationFiles(state.f.root), snapshot);
  }
});
