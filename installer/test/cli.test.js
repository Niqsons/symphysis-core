import { test } from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";

const bin = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "bin", "symphysis.js");
const run = (...args) => spawnSync(process.execPath, [bin, ...args], { encoding: "utf8" });

test("--help печатает обе команды, код 0", () => {
  const r = run("--help");
  assert.equal(r.status, 0);
  assert.match(r.stdout, /install/);
  assert.match(r.stdout, /check/);
  assert.match(r.stdout, /--skills-dir/);
});

test("-h равен --help", () => {
  assert.equal(run("-h").status, 0);
});

test("неизвестная команда — код 2, usage в stderr", () => {
  const r = run("bogus");
  assert.equal(r.status, 2);
  assert.match(r.stderr, /install/);
});

test("лишние позиционные аргументы — usage в stderr, код 2", () => {
  const r = run("install", "extra");
  assert.equal(r.status, 2);
  assert.match(r.stderr, /Использование/);
});

test("--help перед лишним аргументом — usage в stdout, код 0", () => {
  const r = run("--help", "foo");
  assert.equal(r.status, 0);
  assert.match(r.stdout, /Использование/);
});
