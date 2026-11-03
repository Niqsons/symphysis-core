import { test } from "node:test";
import assert from "node:assert/strict";
import { runWithLockRetry } from "../test-support/lock-retry.js";

const LOCK = { status: 1, stdout: "", stderr: "npm error code ECOMPROMISED\nnpm error Lock compromised" };
const OK = { status: 0, stdout: "ok", stderr: "" };

function fake(results) {
  const calls = [];
  const run = () => {
    calls.push(1);
    return results[calls.length - 1];
  };
  return { run, calls };
}

test("ECOMPROMISED, затем успех: два вызова, итог успех", () => {
  const f = fake([LOCK, OK]);
  const r = runWithLockRetry(f.run);
  assert.equal(f.calls.length, 2);
  assert.equal(r.status, 0);
});

test("успех с первого раза: один вызов", () => {
  const f = fake([OK]);
  assert.equal(runWithLockRetry(f.run), OK);
  assert.equal(f.calls.length, 1);
});

test("другая ошибка: один вызов, отказ без повтора", () => {
  const other = { status: 1, stdout: "", stderr: "npm error code ECONNRESET" };
  const f = fake([other, OK]);
  const r = runWithLockRetry(f.run);
  assert.equal(f.calls.length, 1);
  assert.equal(r.status, 1);
});

test("два ECOMPROMISED: два вызова, отказ", () => {
  const f = fake([LOCK, LOCK, OK]);
  const r = runWithLockRetry(f.run);
  assert.equal(f.calls.length, 2);
  assert.equal(r.status, 1);
});

test("код в stdout тоже узнаётся; слово без кода не считается", () => {
  const f1 = fake([{ status: 1, stdout: "ECOMPROMISED", stderr: "" }, OK]);
  runWithLockRetry(f1.run);
  assert.equal(f1.calls.length, 2);
  const f2 = fake([{ status: 1, stdout: "", stderr: "Lock compromised" }, OK]);
  runWithLockRetry(f2.run);
  assert.equal(f2.calls.length, 1);
});
