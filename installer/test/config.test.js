import { test, before } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { syncPayload } from "../scripts/sync-payload.js";
import { targets } from "../lib/paths.js";
import { install } from "../lib/install.js";
import { requireFork } from "../scripts/build-vendor.js";
import { tempDir } from "../test-support/temp-dir.js";

const here = path.dirname(fileURLToPath(import.meta.url));
const bin = path.resolve(here, "..", "bin", "symphysis.js");
const FORK = path.resolve(here, "..", "..", "upstream", "openspec", "bin", "openspec.js");
const tmp = () => tempDir("symphysis-config-");
let payloadDir;

before(() => {
  requireFork(FORK);
  payloadDir = tmp();
  syncPayload(payloadDir);
});

// Проект с установленной копией скрипта; глобальный конфиг форка — временный каталог только для install.
function installed(yamlText) {
  const p = tmp();
  const prev = { xdg: process.env.XDG_CONFIG_HOME, openspec: process.env.SYMPHYSIS_OPENSPEC };
  process.env.XDG_CONFIG_HOME = tmp();
  process.env.SYMPHYSIS_OPENSPEC = FORK;
  try {
    install(p, { payloadDir });
  } finally {
    for (const [k, v] of [["XDG_CONFIG_HOME", prev.xdg], ["SYMPHYSIS_OPENSPEC", prev.openspec]]) {
      if (v === undefined) delete process.env[k];
      else process.env[k] = v;
    }
  }
  if (yamlText !== undefined) fs.writeFileSync(path.join(p, "symphysis.yaml"), yamlText);
  return p;
}
const script = (p) => path.join(targets(p).toolsDir, "tools", "symphysis_config.py");
const cli = (args, opts = {}) => spawnSync(process.execPath, [bin, ...args], { encoding: "utf8", ...opts });
const direct = (p) => spawnSync("python", ["-X", "utf8", script(p), "--project", p], { encoding: "utf8" });

for (const [name, text] of [["годный файл", "edge_probe:\n  enabled: false\n"], ["файл с сигналом", "edge_probe:\n  enabled: no\nconsequences: false\n"]]) {
  test(`symphysis config: ${name} — вывод дословно как у скрипта, код 0`, () => {
    const p = installed(text);
    const want = direct(p);
    assert.equal(want.status, 0, want.stderr);
    const r = cli(["config", "--project", p]);
    assert.equal(r.status, 0, r.stderr);
    assert.equal(r.stdout, want.stdout);
  });
}

test("symphysis config без --project читает текущий каталог", () => {
  const p = installed("edge_probe:\n  enabled: false\n");
  const r = cli(["config"], { cwd: p });
  assert.equal(r.status, 0, r.stderr);
  assert.equal(r.stdout, direct(p).stdout);
});

test("symphysis config: --project не каталог — неверный вызов, код 2", () => {
  const r = cli(["config", "--project", path.join(tmp(), "нет такого")]);
  assert.equal(r.status, 2);
  assert.match(r.stderr, /нет такого/);
  assert.equal(r.stdout, "");
});

test("symphysis config: Python не отвечает — [!!] и код 2", () => {
  const p = installed("");
  const empty = tmp();
  const r = cli(["config", "--project", p], { env: { ...process.env, PATH: empty, Path: empty } });
  assert.equal(r.status, 2);
  assert.equal(r.stdout, "[!!] python: python или python3 не отвечает\n");
});

test("symphysis config: нет копии скрипта — [!!] с командой установки, код 2", () => {
  const p = installed("");
  fs.rmSync(script(p));
  const r = cli(["config", "--project", p]);
  assert.equal(r.status, 2);
  assert.equal(r.stdout, "[!!] symphysis_config.py: нет файла — выполнить: symphysis install\n");
});

test("symphysis config: скрипт упал — [!!] с первой строкой stderr, код 2", () => {
  const p = installed("");
  fs.writeFileSync(script(p), 'raise SystemExit("сломан")\n');
  const r = cli(["config", "--project", p]);
  assert.equal(r.status, 2);
  assert.equal(r.stdout, "[!!] symphysis_config.py: не отработал (сломан)\n");
});

test("справка называет команду и строку «Звать, когда» у каждой команды", () => {
  const r = cli(["--help"]);
  assert.equal(r.status, 0);
  assert.match(r.stdout, /symphysis config +\[--project <dir>\]/);
  for (const name of ["install", "check", "config"]) {
    const entry = new RegExp(`^  ${name} +[^\n]*(?:\n {12}[^\n]*)*`, "m").exec(r.stdout);
    assert.ok(entry, name);
    assert.match(entry[0].replace(/\s+/g, " "), /Звать, когда/, name);
  }
});
