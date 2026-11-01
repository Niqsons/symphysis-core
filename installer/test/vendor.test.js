import { test } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { check } from "../lib/check.js";
import { forkMissingMessage, requireFork } from "../scripts/build-vendor.js";
import { syncPayload } from "../scripts/sync-payload.js";

const here = path.dirname(fileURLToPath(import.meta.url));
const script = path.resolve(here, "..", "scripts", "build-vendor.js");
const pkg = JSON.parse(fs.readFileSync(path.resolve(here, "..", "package.json"), "utf8"));
const tmp = () => fs.mkdtempSync(path.join(os.tmpdir(), "symphysis-vendor-"));
const noGitConfig = path.join(tmp(), "gitconfig");
fs.writeFileSync(noGitConfig, "");
const gitEnv = { ...process.env, GIT_CONFIG_GLOBAL: noGitConfig, GIT_CONFIG_NOSYSTEM: "1" };
const git = (cwd, ...args) => {
  const r = spawnSync("git", ["-c", "user.name=t", "-c", "user.email=t@t", "-c", "core.autocrlf=false", ...args], { cwd, encoding: "utf8", env: gitEnv });
  assert.equal(r.status, 0, r.stdout + r.stderr);
  return r.stdout.trim();
};
const VERSION = "9.9.9-symphysis.1";

/** Корень репозитория с поддельным форком: своя версия, свой коммит; `npm pack` на нём сети не требует. */
function repoWithFork({ version = VERSION, pin = VERSION } = {}) {
  const root = tmp();
  fs.mkdirSync(path.join(root, "installer"));
  fs.writeFileSync(path.join(root, "installer", "package.json"), JSON.stringify({ symphysis: { openspecPin: pin } }));
  const fork = path.join(root, "upstream", "openspec");
  fs.mkdirSync(path.join(fork, "bin"), { recursive: true });
  fs.writeFileSync(path.join(fork, "package.json"), JSON.stringify({ name: "fake-fork", version, files: ["bin"] }));
  fs.writeFileSync(path.join(fork, "bin", "x.js"), "console.log(1);\n");
  git(fork, "init", "-q");
  git(fork, "add", ".");
  git(fork, "commit", "-qm", "первый");
  return { root, fork };
}
const run = (root, ...extra) => spawnSync(process.execPath, [script, "--root", root, ...extra], { encoding: "utf8", timeout: 120_000 });
const vendorFiles = (root) => (fs.existsSync(path.join(root, "vendor")) ? fs.readdirSync(path.join(root, "vendor")).sort() : []);

test("Скрипт на клоне без форка: код 1, ветка и команда в stderr, vendor/ не меняется", () => {
  const root = tmp();
  fs.mkdirSync(path.join(root, "installer"));
  fs.writeFileSync(path.join(root, "installer", "package.json"), JSON.stringify({ symphysis: { openspecPin: VERSION } }));
  fs.mkdirSync(path.join(root, "vendor"));
  fs.writeFileSync(path.join(root, "vendor", "old.tgz"), "старый");
  const r = run(root);
  assert.equal(r.status, 1, r.stdout + r.stderr);
  assert.match(r.stderr, /openspec-fork/);
  assert.match(r.stderr, /git fetch origin openspec-fork/);
  assert.equal(r.stdout, "");
  assert.deepEqual(vendorFiles(root), ["old.tgz"]);
  assert.equal(fs.readFileSync(path.join(root, "vendor", "old.tgz"), "utf8"), "старый");
});

test("Старый тарбол заменяется: в каталоге один *.tgz", () => {
  const { root } = repoWithFork();
  fs.mkdirSync(path.join(root, "vendor"));
  fs.writeFileSync(path.join(root, "vendor", "fake-fork-1.0.0.tgz"), "старый");
  const r = run(root);
  assert.equal(r.status, 0, r.stdout + r.stderr);
  assert.deepEqual(vendorFiles(root), [`fake-fork-${VERSION}.tgz`]);
});

test("Версия форка расходится с пином: код 1, обе версии в stderr, тарбол не кладётся", () => {
  const { root } = repoWithFork({ pin: "1.0.0-pin" });
  const r = run(root);
  assert.equal(r.status, 1, r.stdout + r.stderr);
  assert.match(r.stderr, new RegExp(VERSION.replace(/\./g, "\\.")));
  assert.match(r.stderr, /1\.0\.0-pin/);
  assert.deepEqual(vendorFiles(root), []);
});

test("Грязное дерево форка: код 1, тарбол не кладётся", () => {
  const { root, fork } = repoWithFork();
  fs.appendFileSync(path.join(fork, "bin", "x.js"), "// правка\n");
  const r = run(root);
  assert.equal(r.status, 1, r.stdout + r.stderr);
  assert.match(r.stderr, /незакоммичен/);
  assert.deepEqual(vendorFiles(root), []);
});

test("Грязное дерево форка: неотслеживаемый файл тоже считается", () => {
  const { root, fork } = repoWithFork();
  fs.writeFileSync(path.join(fork, "новый.txt"), "x");
  assert.equal(run(root).status, 1);
  assert.deepEqual(vendorFiles(root), []);
});

test("Хеш форка в выводе", () => {
  const { root, fork } = repoWithFork();
  const r = run(root);
  assert.equal(r.status, 0, r.stdout + r.stderr);
  assert.ok(r.stdout.includes(git(fork, "rev-parse", "HEAD")), r.stdout);
  assert.match(r.stdout, new RegExp(`vendor/fake-fork-${VERSION.replace(/\./g, "\\.")}\\.tgz`));
});

test("--help: предмет, «Звать, когда», исходы и коды", () => {
  const r = spawnSync(process.execPath, [script, "--help"], { encoding: "utf8" });
  assert.equal(r.status, 0);
  assert.match(r.stdout, /Звать, когда/);
  assert.match(r.stdout, /--root/);
  assert.match(r.stdout, /Коды:/);
  assert.match(r.stdout, /openspec-fork/);
});

test("неизвестный флаг: код 2", () => {
  const r = spawnSync(process.execPath, [script, "--нет"], { encoding: "utf8" });
  assert.equal(r.status, 2);
});

test("Строка о форке называет тарбол: openspecSource — путь в vendor/ версии пина", () => {
  assert.equal(pkg.symphysis.openspecSource, `vendor/fission-ai-openspec-${pkg.symphysis.openspecPin}.tgz`);
  const payloadDir = tmp();
  syncPayload(payloadDir);
  const saved = { openspec: process.env.SYMPHYSIS_OPENSPEC, xdg: process.env.XDG_CONFIG_HOME };
  process.env.SYMPHYSIS_OPENSPEC = path.join(tmp(), "нет.js");
  process.env.XDG_CONFIG_HOME = tmp();
  try {
    const { findings } = check(tmp(), { payloadDir });
    const line = findings.find((f) => f.startsWith("openspec: не найден"));
    assert.ok(line, JSON.stringify(findings));
    assert.ok(line.includes(`npm i -g ./${pkg.symphysis.openspecSource}`), line);
  } finally {
    for (const [k, v] of [["SYMPHYSIS_OPENSPEC", saved.openspec], ["XDG_CONFIG_HOME", saved.xdg]]) {
      if (v === undefined) delete process.env[k];
      else process.env[k] = v;
    }
  }
});

test("Форка нет: тесты называют причину и шаг получения", () => {
  const missing = path.join(tmp(), "bin", "openspec.js");
  const text = forkMissingMessage();
  assert.match(text, /openspec-fork/);
  assert.match(text, /npm --prefix installer ci/);
  assert.throws(() => requireFork(missing), (e) => e.message === text);
});

test("vendor/*.tgz в .gitattributes как двоичный", () => {
  const attrs = fs.readFileSync(path.resolve(here, "..", "..", ".gitattributes"), "utf8");
  assert.match(attrs, /^vendor\/\*\.tgz binary$/m);
});
