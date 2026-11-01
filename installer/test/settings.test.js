import { test } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { readSettings, compositionLine } from "../lib/settings.js";

const here = path.dirname(fileURLToPath(import.meta.url));
const bin = path.resolve(here, "..", "bin", "symphysis.js");
const CASES = JSON.parse(fs.readFileSync(path.resolve(here, "..", "..", "tests", "fixtures", "settings-cases.json"), "utf8"));
const tmp = () => fs.mkdtempSync(path.join(os.tmpdir(), "symphysis-settings-"));
const cli = (...args) => spawnSync(process.execPath, [bin, ...args], { encoding: "utf8" });

function projectWith(bytes) {
  const p = tmp();
  if (bytes !== null) fs.writeFileSync(path.join(p, "symphysis.yaml"), Buffer.from(bytes, "base64"));
  return p;
}
const yamlProject = (text) => projectWith(Buffer.from(text, "utf8").toString("base64"));

for (const c of CASES) {
  // Сценарий «Один файл случаев на обоих языках», сторона JS; Backstop F-50.
  test(`общий случай: ${c.name}`, () => {
    const got = readSettings(projectWith(c.bytes_b64));
    assert.deepEqual(
      { failure_branches: got.failure_branches, assumptions: got.assumptions, edge_probe: got.edge_probe },
      { failure_branches: c.failure_branches, assumptions: c.assumptions, edge_probe: c.edge_probe },
    );
    assert.deepEqual(got.signals, c.signals);
  });
}

const on = (v) => (v ? "вкл" : "выкл");

for (const c of CASES) {
  // Сценарий «Человек смотрит состав»: тот же состав и те же сигналы, что у скрипта.
  test(`symphysis config: ${c.name}`, () => {
    const r = cli("config", "--project", projectWith(c.bytes_b64));
    assert.equal(r.status, 0, r.stderr);
    assert.deepEqual(r.stdout.split(/\r?\n/).filter(Boolean), [
      `[..] symphysis.yaml: ветки отказа ${on(c.failure_branches)}, допущения ${on(c.assumptions)}, проба краёв ${on(c.edge_probe)}`,
      ...c.signals.map((s) => `[!!] ${s}`),
    ]);
  });
}

test("no и off не выключают выбор: значения приходят текстом", () => {
  for (const value of ["no", "off", "No", "OFF", "n", "False"]) {
    const got = readSettings(yamlProject(`edge_probe:\n  enabled: ${value}\n`));
    assert.equal(got.edge_probe, true, value);
    assert.deepEqual(got.signals, [`symphysis.yaml: недопустимое значение ${value}`]);
  }
});

test("значение с тегом не исполняется и не выключает выбор", () => {
  const marker = path.join(tmp(), "взлом");
  const got = readSettings(yamlProject(`edge_probe:\n  enabled: !!js/function 'require("fs").writeFileSync("${marker.replaceAll("\\", "/")}", "x")'\n`));
  assert.equal(got.edge_probe, true);
  assert.equal(fs.existsSync(marker), false);
  assert.equal(got.signals.length, 1);
});

// Сценарий «Плоская запись вместо вложенной»: строка `check` и код 2 добавляет задача 6.5 из этого же `signals`.
test("плоская запись: выбор включён, сигнал называет ключ", () => {
  for (const key of ["edge_probe", "consequences"]) {
    const got = readSettings(yamlProject(`${key}: false\n`));
    assert.deepEqual([got.failure_branches, got.assumptions, got.edge_probe], [true, true, true]);
    assert.deepEqual(got.signals, [`symphysis.yaml: ${key} — нужен вложенный ключ`]);
  }
});

test("строка состава называет выключенное", () => {
  const line = compositionLine(readSettings(yamlProject("consequences:\n  assumptions: false\n")));
  assert.equal(line, "symphysis.yaml: ветки отказа вкл, допущения выкл, проба краёв вкл");
});

test("symphysis config без --project читает текущий каталог", () => {
  const p = yamlProject("edge_probe:\n  enabled: false\n");
  const r = spawnSync(process.execPath, [bin, "config"], { encoding: "utf8", cwd: p });
  assert.equal(r.status, 0, r.stderr);
  assert.match(r.stdout, /проба краёв выкл/);
});

test("symphysis config: сигнал код не меняет", () => {
  const r = cli("config", "--project", yamlProject("edge_probe:\n  enabled: no\n"));
  assert.equal(r.status, 0);
  assert.match(r.stdout, /\[!!\] symphysis\.yaml: недопустимое значение no/);
});

test("symphysis config: --project не каталог — неверный вызов, код 2", () => {
  const r = cli("config", "--project", path.join(tmp(), "нет такого"));
  assert.equal(r.status, 2);
  assert.match(r.stderr, /нет такого/);
  assert.equal(r.stdout, "");
});

test("справка называет команду и строку «Звать, когда»", () => {
  const r = cli("--help");
  assert.equal(r.status, 0);
  assert.match(r.stdout, /symphysis config +\[--project <dir>\]/);
  assert.match(r.stdout, /config .*Звать, когда/s);
});
