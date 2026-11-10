import { test } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath, pathToFileURL } from "node:url";
import { createInstallationPlan } from "../lib/installation-plan.js";
import { applyInstallationPlan, recoverInstallation } from "../lib/installation-transaction.js";
import { acquireReader } from "../lib/runtime-leases.js";
import { installationFixture, installationFiles } from "../test-support/installation-fixture.js";

const planModule = pathToFileURL(path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../lib/installation-plan.js")).href;
const transactionModule = pathToFileURL(path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../lib/installation-transaction.js")).href;
const manifestOf = (state) => JSON.parse(fs.readFileSync(path.join(state.root, "install-manifest.json"), "utf8"));
const recordOf = (state) => JSON.parse(fs.readFileSync(path.join(state.root, ".install-transaction.json"), "utf8"));

function crashInstallation(state, name = "target-renamed", index = 0) {
  const script = state.f.write(state.f.at("crash-install.mjs"), `
import {createInstallationPlan} from ${JSON.stringify(planModule)};
import {applyInstallationPlan} from ${JSON.stringify(transactionModule)};
const request=JSON.parse(process.env.FIXTURE_INSTALL_REQUEST);
request.files=request.files.map(file=>({...file,bytes:Buffer.from(file.bytes.data)}));
const plan=createInstallationPlan(request);
applyInstallationPlan(plan,{fault(event){if(event.name===process.env.FIXTURE_FAULT_NAME&&(process.env.FIXTURE_FAULT_INDEX==="last"||event.index===Number(process.env.FIXTURE_FAULT_INDEX)))process.exit(72);}});
`);
  const result = spawnSync(process.execPath, [script], { cwd: state.f.root, env: { ...state.f.env,
    FIXTURE_INSTALL_REQUEST: JSON.stringify(state.version(2)), FIXTURE_FAULT_NAME: name, FIXTURE_FAULT_INDEX: String(index) }, encoding: "utf8", timeout: 15000 });
  assert.equal(result.status, 72, result.stderr);
  return fs.existsSync(path.join(state.root, ".install-transaction.json")) ? recordOf(state) : null;
}

function crashRecovery(state, name) {
  const script = state.f.write(state.f.at("crash-recovery.mjs"), `
import {recoverInstallation} from ${JSON.stringify(transactionModule)};
recoverInstallation({root:process.env.FIXTURE_RECOVERY_ROOT},{fault(event){if(event.name===process.env.FIXTURE_RECOVERY_FAULT)process.exit(73);}});
`);
  const result = spawnSync(process.execPath, [script], { cwd: state.f.root, env: { ...state.f.env,
    FIXTURE_RECOVERY_ROOT: state.root, FIXTURE_RECOVERY_FAULT: name }, encoding: "utf8", timeout: 15000 });
  assert.equal(result.status, 73, result.stderr);
  const file = path.join(state.root, ".install-recovery-lock");
  return fs.existsSync(file) ? JSON.parse(fs.readFileSync(file, "utf8")) : null;
}

test("global update replaces one runtime and all projections while both stores stay byte-identical", (t) => {
  const state = installationFixture(t);
  const storesBefore = [state.store, state.other].map((store) => installationFiles(store.root));
  const first = applyInstallationPlan(createInstallationPlan(state.version(1)));
  const plan = createInstallationPlan(state.version(2));
  const events = [];
  const result = applyInstallationPlan(plan, { fault(event) {
    events.push(event);
    if (event.name === "stage-written") {
      const record = recordOf(state);
      const operation = record.operations[event.index];
      assert.equal(path.dirname(operation.stage), path.dirname(operation.path), "staging is adjacent even for external native targets");
    }
    if (event.name === "target-renamed" && event.index < recordOf(state).operations.length - 1) assert.equal(manifestOf(state).generation, first.generation);
  } });
  assert.notEqual(result.generation, first.generation);
  assert.equal(manifestOf(state).generation, result.generation);
  assert.ok(events.some((event) => event.name === "manifest-published"));
  for (const file of state.version(2).files) assert.deepEqual(fs.readFileSync(file.path), file.bytes);
  assert.deepEqual([state.store, state.other].map((store) => installationFiles(store.root)), storesBefore);
  assert.ok(manifestOf(state).files.some((file) => file.source === ".symphysis-runtime.json"));
  assert.equal(fs.existsSync(path.join(state.root, ".install-lock")), false);
  assert.equal(fs.existsSync(path.join(state.root, ".install-transaction.json")), false);
});

test("active reader lease refuses update before any resource publication", (t) => {
  const state = installationFixture(t);
  const installed = applyInstallationPlan(createInstallationPlan(state.version(1)));
  const reader = acquireReader({ status: "ready", scope: "global", store: { root: state.store.root },
    runtime: { root: state.runtimeRoot, manifestPath: path.join(state.root, "install-manifest.json"), generation: installed.generation } });
  const before = installationFiles(state.f.root);
  try {
    assert.throws(() => applyInstallationPlan(createInstallationPlan(state.version(2))), { code: "installation-busy" });
    assert.deepEqual(installationFiles(state.f.root), before);
  } finally { reader.release(); }
});

for (const eventName of ["stage-open", "stage-written", "backup-renamed", "target-renamed"]) {
  test(`controlled failure after ${eventName} rolls back owned bytes under the writer lock`, (t) => {
    const state = installationFixture(t);
    applyInstallationPlan(createInstallationPlan(state.version(1)));
    const before = installationFiles(state.f.root);
    assert.throws(() => applyInstallationPlan(createInstallationPlan(state.version(2)), { fault(event) {
      if (event.name === eventName && event.index === 0) throw new Error("simulated I/O failure");
    } }), /simulated/);
    assert.deepEqual(installationFiles(state.f.root), before);
    assert.equal(recoverInstallation({ root: state.root }).recovered, false);
  });
}

for (const phase of ["stage-written", "backup-renamed", "target-renamed"]) {
  test(`explicit recovery after an exited writer restores a crash at ${phase}`, (t) => {
    const state = installationFixture(t);
    const first = applyInstallationPlan(createInstallationPlan(state.version(1)));
    crashInstallation(state, phase);
    const recovered = recoverInstallation({ root: state.root, scope: "global" });
    assert.deepEqual(recovered, { recovered: true, action: "rolled-back", generation: null });
    assert.equal(manifestOf(state).generation, first.generation);
    for (const file of state.version(1).files) assert.deepEqual(fs.readFileSync(file.path), file.bytes);
    assert.equal(fs.existsSync(path.join(state.root, ".install-lock")), false);
  });
}

test("a crash after manifest publication completes verified cleanup instead of reverting the generation", (t) => {
  const state = installationFixture(t);
  applyInstallationPlan(createInstallationPlan(state.version(1)));
  const record = crashInstallation(state, "manifest-published", "last");
  const result = recoverInstallation({ root: state.root });
  assert.deepEqual(result, { recovered: true, action: "completed", generation: record.generation });
  assert.equal(manifestOf(state).generation, record.generation);
  for (const file of state.version(2).files) assert.deepEqual(fs.readFileSync(file.path), file.bytes);
});

test("recovery refuses a live or reused PID and never prunes an unknown reader", (t) => {
  const state = installationFixture(t);
  applyInstallationPlan(createInstallationPlan(state.version(1)));
  const record = crashInstallation(state);
  const lockFile = path.join(state.root, ".install-lock");
  const lock = JSON.parse(fs.readFileSync(lockFile, "utf8"));
  lock.pid = process.pid;
  record.owner.pid = process.pid;
  state.f.json(lockFile, lock);
  state.f.json(path.join(state.root, ".install-transaction.json"), record);
  assert.throws(() => recoverInstallation({ root: state.root }), { code: "installation-busy" });
  lock.pid = record.owner.pid = 2147483000;
  state.f.json(lockFile, lock);
  state.f.json(path.join(state.root, ".install-transaction.json"), record);
  const reader = state.f.write(path.join(state.root, ".leases", "foreign.json"), "foreign reader\n");
  const before = installationFiles(state.f.root);
  assert.throws(() => recoverInstallation({ root: state.root }), { code: "installation-busy" });
  assert.deepEqual(installationFiles(state.f.root), before);
  assert.equal(fs.readFileSync(reader, "utf8"), "foreign reader\n");
});

test("a user edit after a crash preserves the new file and the original backup", (t) => {
  const state = installationFixture(t);
  applyInstallationPlan(createInstallationPlan(state.version(1)));
  const record = crashInstallation(state);
  const tool = record.operations[0].path;
  fs.writeFileSync(tool, "user changed after crash\n");
  const before = installationFiles(state.f.root);
  assert.throws(() => recoverInstallation({ root: state.root }), { code: "installation-recovery-required" });
  assert.deepEqual(installationFiles(state.f.root), before);
  assert.equal(fs.readFileSync(record.operations[0].backup, "utf8"), "# runtime 1\n");
});

test("recovery does not unlink a same-bytes replacement with a different file identity", (t) => {
  const state = installationFixture(t);
  applyInstallationPlan(createInstallationPlan(state.version(1)));
  const record = crashInstallation(state);
  const tool = record.operations[0].path;
  const replacement = state.f.write(state.f.at("new-user-file.py"), fs.readFileSync(tool));
  fs.unlinkSync(tool);
  fs.renameSync(replacement, tool);
  const before = installationFiles(state.f.root);
  assert.throws(() => recoverInstallation({ root: state.root }), { code: "installation-recovery-required" });
  assert.deepEqual(installationFiles(state.f.root), before);
});

test("a substituted parent junction is refused before recovery touches its foreign destination", (t) => {
  const state = installationFixture(t);
  applyInstallationPlan(createInstallationPlan(state.version(1)));
  crashInstallation(state);
  const tools = path.join(state.runtimeRoot, "tools");
  const original = state.f.at("saved-tools");
  const foreign = state.f.at("foreign-tools");
  state.f.write(path.join(foreign, "keep.txt"), "foreign\n");
  fs.renameSync(tools, original);
  fs.symlinkSync(foreign, tools, process.platform === "win32" ? "junction" : "dir");
  try {
    assert.throws(() => recoverInstallation({ root: state.root }), /reparse|ссылк/);
    assert.deepEqual(fs.readdirSync(foreign), ["keep.txt"]);
    assert.equal(fs.readFileSync(path.join(foreign, "keep.txt"), "utf8"), "foreign\n");
  } finally { fs.unlinkSync(tools); }
});

test("a tampered recovery target cannot redirect cleanup to another file", (t) => {
  const state = installationFixture(t);
  applyInstallationPlan(createInstallationPlan(state.version(1)));
  const record = crashInstallation(state);
  const foreign = state.f.write(state.f.at("foreign.txt"), "preserve\n");
  record.operations[0].path = foreign;
  state.f.json(path.join(state.root, ".install-transaction.json"), record);
  assert.throws(() => recoverInstallation({ root: state.root }), { code: "installation-recovery-required" });
  assert.equal(fs.readFileSync(foreign, "utf8"), "preserve\n");
});

test("local recovery restores local resources and explicit native targets without any global runtime", (t) => {
  const state = installationFixture(t, "local");
  const first = applyInstallationPlan(createInstallationPlan(state.version(1)));
  crashInstallation(state, "target-renamed", 2);
  assert.equal(recoverInstallation({ root: state.root, scope: "local" }).action, "rolled-back");
  assert.equal(manifestOf(state).generation, first.generation);
  for (const file of state.version(1).files) assert.deepEqual(fs.readFileSync(file.path), file.bytes);
  assert.equal(fs.existsSync(path.join(state.f.userDir, "runtime")), false);
});

test("an unverified temporary journal is preserved and prevents cleanup of any target", (t) => {
  const state = installationFixture(t);
  applyInstallationPlan(createInstallationPlan(state.version(1)));
  const record = crashInstallation(state);
  const temp = state.f.write(path.join(state.root, `.install-record-${record.id}.tmp`), "unverified partial record\n");
  const before = installationFiles(state.f.root);
  assert.throws(() => recoverInstallation({ root: state.root }), { code: "installation-recovery-required" });
  assert.deepEqual(installationFiles(state.f.root), before);
  assert.equal(fs.readFileSync(temp, "utf8"), "unverified partial record\n");
});

for (const step of ["recovery-claimed", "recovery-stage-removed", "recovery-target-removed", "recovery-backup-restored", "recovery-resources-cleaned", "recovery-writer-unlinked", "recovery-writer-recorded", "recovery-pending-unlinked", "recovery-pending-recorded", "recovery-claim-unlinked"]) {
  test(`explicit recovery resumes its own exited process after ${step}`, (t) => {
    const state = installationFixture(t);
    const first = applyInstallationPlan(createInstallationPlan(state.version(1)));
    crashInstallation(state);
    const claim = crashRecovery(state, step);
    if (claim) {
      assert.equal(claim.kind, "recovery");
      assert.equal(claim.transaction.kind, "installation");
      assert.equal(typeof claim.pending.bytes, "string");
      assert.equal(typeof claim.writer.bytes, "string");
    }
    const resumed = recoverInstallation({ root: state.root });
    assert.equal(resumed.recovered, step !== "recovery-claim-unlinked");
    if (resumed.recovered) assert.equal(resumed.action, "rolled-back");
    assert.equal(manifestOf(state).generation, first.generation);
    for (const file of state.version(1).files) assert.deepEqual(fs.readFileSync(file.path), file.bytes);
    assert.equal(fs.existsSync(path.join(state.root, ".install-lock")), false);
    assert.equal(fs.existsSync(path.join(state.root, ".install-transaction.json")), false);
    assert.equal(fs.existsSync(path.join(state.root, ".install-recovery-lock")), false);
  });
}

for (const step of ["recovery-backup-removed", "recovery-resources-cleaned", "recovery-writer-unlinked", "recovery-pending-unlinked", "recovery-pending-recorded"]) {
  test(`a published generation survives another recovery crash at ${step}`, (t) => {
    const state = installationFixture(t);
    applyInstallationPlan(createInstallationPlan(state.version(1)));
    const published = crashInstallation(state, "manifest-published", "last");
    crashRecovery(state, step);
    assert.equal(recoverInstallation({ root: state.root }).action, "completed");
    assert.equal(manifestOf(state).generation, published.generation);
    for (const file of state.version(2).files) assert.deepEqual(fs.readFileSync(file.path), file.bytes);
  });
}

test("a recovery claim with a live or reused PID cannot be taken over", (t) => {
  const state = installationFixture(t);
  applyInstallationPlan(createInstallationPlan(state.version(1)));
  crashInstallation(state);
  const claim = crashRecovery(state, "recovery-claimed");
  claim.owner.pid = process.pid;
  state.f.json(path.join(state.root, ".install-recovery-lock"), claim);
  const before = installationFiles(state.f.root);
  assert.throws(() => recoverInstallation({ root: state.root }), { code: "installation-busy" });
  assert.deepEqual(installationFiles(state.f.root), before);
});

test("partial, foreign and same-bytes replacement recovery claims are preserved", (t) => {
  const state = installationFixture(t);
  applyInstallationPlan(createInstallationPlan(state.version(1)));
  crashInstallation(state);
  crashRecovery(state, "recovery-claimed");
  const file = path.join(state.root, ".install-recovery-lock");
  const bytes = fs.readFileSync(file);
  const replacement = state.f.write(state.f.at("replacement-claim.json"), bytes);
  fs.unlinkSync(file);
  fs.renameSync(replacement, file);
  const before = installationFiles(state.f.root);
  assert.throws(() => recoverInstallation({ root: state.root }), { code: "installation-recovery-required" });
  assert.deepEqual(installationFiles(state.f.root), before);
  for (const content of ["{", '{"id":"foreign"}\n']) {
    fs.writeFileSync(file, content);
    const snapshot = installationFiles(state.f.root);
    assert.throws(() => recoverInstallation({ root: state.root }), { code: "installation-recovery-required" });
    assert.deepEqual(installationFiles(state.f.root), snapshot);
  }
});

test("a partial recovery journal update remains blocked rather than being pruned", (t) => {
  const state = installationFixture(t);
  applyInstallationPlan(createInstallationPlan(state.version(1)));
  crashInstallation(state);
  const claim = crashRecovery(state, "recovery-claimed");
  const temp = state.f.write(path.join(state.root, `.install-recovery-${claim.id}.tmp`), "partial recovery update\n");
  const before = installationFiles(state.f.root);
  assert.throws(() => recoverInstallation({ root: state.root }), { code: "installation-recovery-required" });
  assert.deepEqual(installationFiles(state.f.root), before);
  assert.equal(fs.readFileSync(temp, "utf8"), "partial recovery update\n");
});

test("a user edit after pending cleanup preserves the file and the durable recovery proof", (t) => {
  const state = installationFixture(t);
  applyInstallationPlan(createInstallationPlan(state.version(1)));
  crashInstallation(state);
  const claim = crashRecovery(state, "recovery-pending-unlinked");
  const file = claim.final[0].path;
  fs.writeFileSync(file, "user edit after recovery cleanup\n");
  const before = installationFiles(state.f.root);
  assert.throws(() => recoverInstallation({ root: state.root }), { code: "installation-recovery-required" });
  assert.deepEqual(installationFiles(state.f.root), before);
  assert.equal(fs.existsSync(path.join(state.root, ".install-recovery-lock")), true);
});

test("a user deletion after committed publication is not silently restored from backup", (t) => {
  const state = installationFixture(t);
  applyInstallationPlan(createInstallationPlan(state.version(1)));
  const record = crashInstallation(state, "manifest-published", "last");
  const target = record.operations[0].path;
  fs.unlinkSync(target);
  const before = installationFiles(state.f.root);
  assert.throws(() => recoverInstallation({ root: state.root }), { code: "installation-recovery-required" });
  assert.deepEqual(installationFiles(state.f.root), before);
  assert.equal(fs.existsSync(target), false);
  assert.equal(fs.existsSync(record.operations[0].backup), true);
});

test("recovery of the first installation can resume after removing its newly created payload directories", (t) => {
  const state = installationFixture(t);
  crashInstallation(state);
  crashRecovery(state, "recovery-resources-cleaned");
  assert.deepEqual(recoverInstallation({ root: state.root }), { recovered: true, action: "rolled-back", generation: null });
  for (const file of state.version(2).files) assert.equal(fs.existsSync(file.path), false);
  assert.equal(fs.existsSync(path.join(state.root, "install-manifest.json")), false);
  assert.equal(fs.existsSync(path.join(state.root, ".install-recovery-lock")), false);
});

for (const step of ["cleanup-receipt-published", "cleanup-writer-unlinked", "cleanup-pending-unlinked"]) {
  test(`normal apply cleanup is recoverable after ${step}`, (t) => {
    const state = installationFixture(t);
    applyInstallationPlan(createInstallationPlan(state.version(1)));
    crashInstallation(state, step, "last");
    const generation = manifestOf(state).generation;
    assert.deepEqual(recoverInstallation({ root: state.root }), { recovered: true, action: "completed", generation });
    for (const file of state.version(2).files) assert.deepEqual(fs.readFileSync(file.path), file.bytes);
    assert.equal(fs.existsSync(path.join(state.root, ".install-lock")), false);
    assert.equal(fs.existsSync(path.join(state.root, ".install-transaction.json")), false);
    assert.equal(fs.existsSync(path.join(state.root, ".install-recovery-lock")), false);
  });
}

test("controlled rollback cleanup uses the same durable receipt if its process exits", (t) => {
  const state = installationFixture(t);
  const first = applyInstallationPlan(createInstallationPlan(state.version(1)));
  const script = state.f.write(state.f.at("crash-rollback-cleanup.mjs"), `
import {createInstallationPlan} from ${JSON.stringify(planModule)};
import {applyInstallationPlan} from ${JSON.stringify(transactionModule)};
const request=JSON.parse(process.env.FIXTURE_INSTALL_REQUEST);
request.files=request.files.map(file=>({...file,bytes:Buffer.from(file.bytes.data)}));
applyInstallationPlan(createInstallationPlan(request),{fault(event){
  if(event.name==="stage-written"&&event.index===0)throw new Error("simulated I/O failure");
  if(event.name==="cleanup-writer-unlinked")process.exit(74);
}});
`);
  const result = spawnSync(process.execPath, [script], { cwd: state.f.root, env: { ...state.f.env, FIXTURE_INSTALL_REQUEST: JSON.stringify(state.version(2)) }, encoding: "utf8", timeout: 15000 });
  assert.equal(result.status, 74, result.stderr);
  assert.deepEqual(recoverInstallation({ root: state.root }), { recovered: true, action: "rolled-back", generation: null });
  assert.equal(manifestOf(state).generation, first.generation);
  for (const file of state.version(1).files) assert.deepEqual(fs.readFileSync(file.path), file.bytes);
});
