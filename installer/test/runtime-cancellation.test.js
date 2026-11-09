import { test } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { spawn } from "node:child_process";
import { randomBytes, randomUUID } from "node:crypto";
import { once } from "node:events";
import { setTimeout as delay } from "node:timers/promises";
import { createRuntimeFixture } from "../test-support/runtime-fixture.js";
import { acquireWriter, managementRoot } from "../lib/runtime-leases.js";
import { CancellationError, watchCancellation } from "../lib/runtime-cancellation.js";

function fixture(t) {
  const f = createRuntimeFixture(path.join(os.tmpdir(), "symphysis-cancellation-tests"));
  const file = f.at("host", "cancel.json");
  const record = { format: 1, id: randomUUID(), token: randomBytes(32).toString("hex"), cancel: false };
  f.json(file, record);
  t.after(() => f.cleanup());
  return { f, file, record };
}
function replace(f, file, record) {
  const temporary = `${file}.next`;
  f.json(temporary, record);
  fs.renameSync(temporary, file);
}
function observe(file) {
  let dispose;
  let calls = 0;
  const result = new Promise((resolve, reject) => {
    const timeout = setTimeout(() => { dispose?.(); reject(new Error("Cancellation callback timed out")); }, 2500);
    try {
      dispose = watchCancellation({ SYMPHYSIS_CANCEL_FILE: file }, (error) => { calls++; clearTimeout(timeout); resolve(error); });
    } catch (error) { clearTimeout(timeout); reject(error); }
  });
  return { result, dispose: () => dispose?.(), calls: () => calls };
}

test("no control environment is a no-op; disposal never changes the host file", async (t) => {
  const { file } = fixture(t);
  const original = fs.readFileSync(file);
  let calls = 0;
  watchCancellation({}, () => { calls++; })();
  const dispose = watchCancellation({ SYMPHYSIS_CANCEL_FILE: file }, () => { calls++; });
  dispose(); dispose();
  await delay(130);
  assert.equal(calls, 0);
  assert.deepEqual(fs.readFileSync(file), original);
});

test("initial cancellation runs asynchronously once and can be disposed before notification", async (t) => {
  const { f, file, record } = fixture(t);
  f.json(file, { ...record, cancel: true });
  let calls = 0;
  const dispose = watchCancellation({ SYMPHYSIS_CANCEL_FILE: file }, () => { calls++; });
  assert.equal(calls, 0);
  dispose();
  await Promise.resolve();
  assert.equal(calls, 0);
  const watched = observe(file);
  assert.equal(await watched.result, null);
  assert.equal(watched.calls(), 1);
  watched.dispose();
});

test("a host may atomically replace its file with the same identity to cancel", async (t) => {
  const { f, file, record } = fixture(t);
  const watched = observe(file);
  replace(f, file, { ...record, cancel: true });
  assert.equal(await watched.result, null);
  await delay(130);
  assert.equal(watched.calls(), 1);
  assert.equal(JSON.parse(fs.readFileSync(file, "utf8")).cancel, true);
  watched.dispose();
});

test("malformed, absent and relative initial control files fail closed", (t) => {
  const { f, file, record } = fixture(t);
  const invalid = (error) => error instanceof CancellationError && error.exitCode === 2 && error.code === "cancellation-invalid";
  for (const chosen of ["relative.json", "", f.at("missing.json")]) assert.throws(() => watchCancellation({ SYMPHYSIS_CANCEL_FILE: chosen }, () => {}), invalid);
  if (process.platform === "win32") for (const chosen of ["\\control.json", "/control.json", "X:control.json"]) assert.throws(() => watchCancellation({ SYMPHYSIS_CANCEL_FILE: chosen }, () => {}), invalid);
  const malformedRecords = [
    {},
    { ...record, format: 2 },
    { ...record, token: "!" },
    { ...record, token: "a".repeat(33) },
    { ...record, cancel: "true" },
    { ...record, id: "" },
  ];
  for (const value of malformedRecords) {
    f.json(file, value);
    assert.throws(() => watchCancellation({ SYMPHYSIS_CANCEL_FILE: file }, () => {}), invalid);
  }
  fs.writeFileSync(file, Buffer.from([255]));
  assert.throws(() => watchCancellation({ SYMPHYSIS_CANCEL_FILE: file }, () => {}), invalid);
});

for (const failure of ["token", "id", "deleted", "malformed", "utf8"]) {
  test(`control ${failure} during execution reports one error and preserves foreign state`, async (t) => {
    const { f, file, record } = fixture(t);
    const watched = observe(file);
    if (failure === "token") replace(f, file, { ...record, token: randomBytes(32).toString("hex"), cancel: true });
    if (failure === "id") replace(f, file, { ...record, id: randomUUID(), cancel: true });
    if (failure === "deleted") fs.unlinkSync(file);
    if (failure === "malformed") fs.writeFileSync(file, "{");
    if (failure === "utf8") fs.writeFileSync(file, Buffer.from([255]));
    const before = failure === "deleted" ? null : fs.readFileSync(file);
    const error = await watched.result;
    assert.ok(error instanceof CancellationError);
    assert.equal(error.exitCode, 2);
    assert.equal(watched.calls(), 1);
    if (before) assert.deepEqual(fs.readFileSync(file), before);
    else assert.equal(fs.existsSync(file), false);
    watched.dispose();
  });
}

test("junction target and parent paths are refused without following the target", async (t) => {
  const { f, file } = fixture(t);
  const foreign = f.at("foreign");
  fs.mkdirSync(foreign);
  const linked = f.at("linked-parent");
  fs.symlinkSync(foreign, linked, "junction");
  try { assert.throws(() => watchCancellation({ SYMPHYSIS_CANCEL_FILE: path.join(linked, "cancel.json") }, () => {}), /reparse/); }
  finally { fs.rmdirSync(linked); }
  const watched = observe(file);
  fs.unlinkSync(file);
  fs.symlinkSync(foreign, file, "junction");
  try {
    assert.ok((await watched.result) instanceof CancellationError);
    assert.deepEqual(fs.readdirSync(foreign), []);
  } finally { watched.dispose(); fs.rmdirSync(file); }
});

const workerCode = `
import { spawn } from "node:child_process";
import { acquireReader } from ${JSON.stringify(new URL("../lib/runtime-leases.js", import.meta.url).href)};
import { watchCancellation } from ${JSON.stringify(new URL("../lib/runtime-cancellation.js", import.meta.url).href)};
const lease = acquireReader(JSON.parse(process.argv[1]));
const child = spawn(process.execPath, ["-e", "setInterval(() => {}, 1000);"], { stdio: "ignore" });
let outcome = null;
const dispose = watchCancellation(process.env, (error) => { outcome = error ? 2 : 130; child.kill(); });
process.on("SIGTERM", () => { outcome = 130; child.kill(); });
child.once("spawn", () => process.send({ ready: true }));
child.once("exit", (code) => { dispose(); lease.release(); process.exit(outcome ?? code ?? 1); });
`;

for (const broken of [false, true]) {
  test(`file cancellation ${broken ? "identity failure" : "request"} stops a real child and releases its lease`, { timeout: 10000 }, async (t) => {
    const { f, file, record } = fixture(t);
    const store = f.store("store-a");
    const payload = f.payload("global");
    const context = { status: "ready", scope: "global", store, runtime: { ...payload, generation: payload.manifest.generation, legacy: false } };
    const root = managementRoot(context);
    const worker = spawn(process.execPath, ["--input-type=module", "-e", workerCode, JSON.stringify(context)], { env: { ...f.env, SYMPHYSIS_CANCEL_FILE: file }, stdio: ["ignore", "ignore", "pipe", "ipc"] });
    t.after(() => { if (worker.exitCode === null) worker.kill(); });
    let stderr = "";
    worker.stderr.on("data", (chunk) => { stderr += chunk; });
    const ready = await Promise.race([
      once(worker, "message").then(([message]) => message),
      once(worker, "exit").then(([code]) => { throw new Error(`Worker exited ${code}: ${stderr}`); }),
    ]);
    assert.equal(ready.ready, true);
    assert.throws(() => acquireWriter({ root }), (error) => error.code === "installation-busy");
    const exited = once(worker, "exit");
    replace(f, file, { ...record, ...(broken ? { token: randomBytes(32).toString("hex") } : {}), cancel: true });
    const [code] = await exited;
    assert.equal(code, broken ? 2 : 130, stderr);
    assert.deepEqual(fs.readdirSync(path.join(root, ".leases")), []);
    acquireWriter({ root }).release();
  });
}
