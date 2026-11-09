import { test } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { spawn } from "node:child_process";
import { once } from "node:events";
import { createRuntimeFixture } from "../test-support/runtime-fixture.js";
import { acquireReader, acquireWriter, managementRoot, pendingManagementState, LeaseError } from "../lib/runtime-leases.js";

function fixture(t, scope = "global", legacy = false) {
  const f = createRuntimeFixture(path.join(os.tmpdir(), "symphysis-lease-tests"));
  const store = f.store("store-a");
  const payload = f.payload(scope, { store, legacy });
  const context = { status: "ready", scope, store, runtime: { ...payload, generation: payload.manifest?.generation ?? "legacy-local", legacy } };
  t.after(() => f.cleanup());
  return { f, store, payload, context, root: managementRoot(context) };
}
const leaseFiles = (root) => fs.readdirSync(path.join(root, ".leases"));
const isBusy = (error) => error instanceof LeaseError && error.code === "installation-busy" && error.exitCode === 2;

for (const name of [".migration-transaction.json", ".migration-recovery.json", ".migration-record-unknown.tmp", ".migration-recovery-unknown.tmp"]) {
  test(`incomplete migration state ${name} blocks new execution and management without pruning`, (t) => {
    const { f, context, root } = fixture(t, "local");
    const pending = f.write(path.join(root, name), "unknown partial state\n");
    assert.equal(pendingManagementState(root), true);
    assert.throws(() => acquireReader(context), isBusy);
    assert.throws(() => acquireWriter({ root }), isBusy);
    assert.equal(fs.readFileSync(pending, "utf8"), "unknown partial state\n");
  });
}

test("reader descriptors identify their exact record and release is idempotent", (t) => {
  const { context, root } = fixture(t);
  const reader = acquireReader(context);
  const record = JSON.parse(fs.readFileSync(reader.file, "utf8"));
  assert.equal(path.basename(reader.file), `${reader.id}.json`);
  assert.equal(record.kind, "reader");
  assert.equal(record.pid, process.pid);
  assert.equal(record.generation, context.runtime.generation);
  assert.ok(Number.isSafeInteger(record.startedAt));
  assert.match(record.instance, /^[a-f0-9-]+$/);
  assert.match(record.token, /^[a-f0-9]{64}$/);
  assert.deepEqual(reader.descriptor, { file: reader.file, id: reader.id, generation: record.generation, token: record.token, pid: record.pid, startedAt: record.startedAt, instance: record.instance });
  assert.throws(() => acquireWriter({ root }), isBusy);
  assert.equal(fs.existsSync(path.join(root, ".install-lock")), false);
  assert.equal(reader.release(), true);
  assert.equal(reader.release(), false);
  assert.deepEqual(leaseFiles(root), []);
});

test("two stores share a generation while a writer excludes both readers", (t) => {
  const { f, context, root } = fixture(t);
  const other = { ...context, store: f.store("store-b") };
  const first = acquireReader(context);
  const second = acquireReader(other);
  assert.equal(leaseFiles(root).length, 2);
  first.release();
  assert.throws(() => acquireWriter({ root }), isBusy);
  second.release();
  const writer = acquireWriter({ root, generation: context.runtime.generation });
  assert.throws(() => acquireReader(context), isBusy);
  assert.throws(() => acquireWriter({ root }), isBusy);
  assert.deepEqual(leaseFiles(root), []);
  writer.release();
  acquireReader(other).release();
});

test("a changed generation refuses entry before creating a reader", (t) => {
  const { f, context, payload, root } = fixture(t);
  f.json(payload.manifestPath, { ...payload.manifest, generation: "next-generation" });
  assert.throws(() => acquireReader(context), /Поколение/);
  assert.equal(fs.existsSync(path.join(root, ".leases")), false);
  assert.throws(() => acquireReader({ ...context, status: "blocked" }), /preflight/);
});

test("a writer appearing during registration refuses the reader and cleans only its own record", (t) => {
  const { context, root } = fixture(t);
  const write = fs.writeFileSync;
  const lock = path.join(root, ".install-lock");
  fs.writeFileSync = (target, bytes, ...args) => {
    write(target, bytes, ...args);
    if (typeof target === "number" && String(bytes).includes('"kind":"reader"')) write(lock, "writer entered during reader registration\n");
  };
  try { assert.throws(() => acquireReader(context), isBusy); }
  finally { fs.writeFileSync = write; }
  assert.deepEqual(leaseFiles(root), []);
  assert.equal(fs.readFileSync(lock, "utf8"), "writer entered during reader registration\n");
});

test("an update completed during registration invalidates the old generation without a leaked reader", (t) => {
  const { context, payload, root } = fixture(t);
  const write = fs.writeFileSync;
  fs.writeFileSync = (target, bytes, ...args) => {
    write(target, bytes, ...args);
    if (typeof target === "number" && String(bytes).includes('"kind":"reader"')) {
      write(payload.manifestPath, JSON.stringify({ ...payload.manifest, generation: "updated-during-registration" }));
    }
  };
  try { assert.throws(() => acquireReader(context), /Поколение/); }
  finally { fs.writeFileSync = write; }
  assert.deepEqual(leaseFiles(root), []);
});

test("unrecognized and apparently dead leases are preserved rather than pruned", (t) => {
  const { f, root } = fixture(t);
  const foreign = f.write(path.join(root, ".leases", "foreign.json"), "unrecognized record\n");
  const before = fs.readFileSync(foreign);
  assert.throws(() => acquireWriter({ root }), isBusy);
  assert.deepEqual(fs.readFileSync(foreign), before);
  f.json(foreign, { format: 1, kind: "reader", pid: 2147483647, startedAt: 0, instance: "previous-process", token: "foreign", generation: "old-generation" });
  assert.throws(() => acquireWriter({ root }), isBusy);
  assert.equal(fs.existsSync(foreign), true);
  assert.equal(fs.existsSync(path.join(root, ".install-lock")), false);
});

test("existing foreign writer locks survive acquisition attempts", (t) => {
  const { f, root, context } = fixture(t);
  const file = f.write(path.join(root, ".install-lock"), "foreign lock\n");
  assert.throws(() => acquireWriter({ root }), isBusy);
  assert.throws(() => acquireReader(context), isBusy);
  assert.equal(fs.readFileSync(file, "utf8"), "foreign lock\n");
});

test("release refuses changed owner bytes even if the PID and inode still match", (t) => {
  const { root, context } = fixture(t);
  const reader = acquireReader(context);
  const record = JSON.parse(fs.readFileSync(reader.file, "utf8"));
  record.instance = "a-different-process-with-the-same-pid";
  fs.writeFileSync(reader.file, `${JSON.stringify(record)}\n`);
  assert.throws(() => reader.release(), /изменились/);
  assert.equal(fs.existsSync(reader.file), true);
  assert.throws(() => acquireWriter({ root }), isBusy);
});

test("release refuses a replacement file, and preserves a replaced writer", (t) => {
  const { root, context } = fixture(t);
  const reader = acquireReader(context);
  fs.renameSync(reader.file, `${reader.file}.original`);
  fs.writeFileSync(reader.file, "replacement\n");
  assert.throws(() => reader.release(), /заменена/);
  assert.equal(fs.readFileSync(reader.file, "utf8"), "replacement\n");
  fs.unlinkSync(reader.file);
  fs.unlinkSync(`${reader.file}.original`);
  const writer = acquireWriter({ root });
  fs.writeFileSync(writer.file, "replacement writer\n");
  assert.throws(() => writer.release(), /изменились/);
  assert.equal(fs.readFileSync(writer.file, "utf8"), "replacement writer\n");
});

test("local and legacy management roots are separate from store data", (t) => {
  const managed = fixture(t, "local");
  assert.equal(managed.root, managed.payload.runtimeRoot);
  acquireReader(managed.context).release();
  const legacy = fixture(t, "local", true);
  assert.equal(legacy.root, legacy.payload.runtimeRoot);
  acquireReader(legacy.context).release();
  const flat = { ...legacy.context, runtime: { ...legacy.context.runtime, root: legacy.store.root } };
  assert.equal(managementRoot(flat), path.join(legacy.store.root, ".symphysis"));
  acquireReader(flat).release();
});

test("Windows lease roots and descriptors reject paths dependent on the current drive", { skip: process.platform !== "win32" }, (t) => {
  const { context } = fixture(t);
  for (const file of ["\\fixture", "/fixture", "X:fixture"]) {
    assert.throws(() => acquireWriter({ root: file }), /абсолютный/);
    assert.throws(() => managementRoot({ ...context, runtime: { ...context.runtime, root: file } }), /runtime/);
    assert.throws(() => acquireReader({ ...context, runtime: { ...context.runtime, manifestPath: `${file}\\install-manifest.json` } }), /manifest/);
  }
});

test("junctions in management parents, lease directories and record paths are refused", (t) => {
  const { f, root, context } = fixture(t);
  const destination = f.at("foreign");
  fs.mkdirSync(destination);
  const link = path.join(root, ".leases");
  fs.symlinkSync(destination, link, "junction");
  try {
    assert.throws(() => acquireReader(context), /reparse/);
    assert.throws(() => acquireWriter({ root }), /reparse/);
    assert.deepEqual(fs.readdirSync(destination), []);
    assert.equal(fs.existsSync(path.join(root, ".install-lock")), false);
  } finally { fs.rmdirSync(link); }
  const parent = f.at("linked-parent");
  fs.symlinkSync(destination, parent, "junction");
  try { assert.throws(() => acquireWriter({ root: path.join(parent, "child") }), /reparse/); }
  finally { fs.rmdirSync(parent); }
  const reader = acquireReader(context);
  const original = `${reader.file}.original`;
  fs.renameSync(reader.file, original);
  fs.symlinkSync(destination, reader.file, "junction");
  try { assert.throws(() => reader.release(), /reparse/); }
  finally { fs.rmdirSync(reader.file); fs.unlinkSync(original); }
});

const workerCode = `
import { spawn } from "node:child_process";
import { acquireReader } from ${JSON.stringify(new URL("../lib/runtime-leases.js", import.meta.url).href)};
const lease = acquireReader(JSON.parse(process.argv[1]));
const child = spawn(process.execPath, ["-e", "setInterval(() => {}, 1000); process.on('message', (m) => process.exit(m === 'finish' ? 0 : 73));"], { stdio: ["ignore", "ignore", "ignore", "ipc"] });
child.once("spawn", () => process.send({ ready: true, descriptor: lease.descriptor }));
process.on("message", (message) => child.send(message));
process.on("SIGTERM", () => child.kill());
child.once("exit", (code) => { lease.release(); process.exit(code ?? 1); });
`;

for (const outcome of ["finish", "cancel"]) {
  test(`a running child prevents update until ${outcome} and lease release`, { timeout: 15000 }, async (t) => {
    const { f, context, root } = fixture(t);
    const worker = spawn(process.execPath, ["--input-type=module", "-e", workerCode, JSON.stringify(context)], { env: f.env, stdio: ["ignore", "ignore", "pipe", "ipc"] });
    t.after(() => { if (worker.exitCode === null) worker.kill(); });
    let stderr = "";
    worker.stderr.on("data", (chunk) => { stderr += chunk; });
    const ready = await Promise.race([
      once(worker, "message").then(([message]) => message),
      once(worker, "exit").then(([code]) => { throw new Error(`Worker exited ${code}: ${stderr}`); }),
    ]);
    assert.equal(ready.ready, true);
    assert.notEqual(ready.descriptor.pid, process.pid);
    assert.throws(() => acquireWriter({ root }), isBusy);
    assert.equal(leaseFiles(root).length, 1);
    const exited = once(worker, "exit");
    worker.send(outcome);
    const [code] = await exited;
    assert.equal(code, outcome === "finish" ? 0 : 73, stderr);
    assert.deepEqual(leaseFiles(root), []);
    acquireWriter({ root }).release();
  });
}
