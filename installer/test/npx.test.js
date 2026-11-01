// Медленный (сеть: npx тянет `yaml` из реестра, около минуты) — файл последний по имени.
import { test, before, after } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { requireFork } from "../scripts/build-vendor.js";

const here = path.dirname(fileURLToPath(import.meta.url));
const installerDir = path.resolve(here, "..");
const FORK = path.resolve(installerDir, "..", "upstream", "openspec", "bin", "openspec.js");
const win = process.platform === "win32";
const TIMEOUT = 240_000;

const probe = spawnSync(win ? "npm --version" : "npm", win ? [] : ["--version"], { encoding: "utf8", shell: win });
const hasNpm = !probe.error && probe.status === 0;

const tmpRoot = fs.mkdtempSync(path.join(os.tmpdir(), "symphysis-npx-"));
const mk = (name) => fs.mkdirSync(path.join(tmpRoot, name), { recursive: true }) && path.join(tmpRoot, name);
let tgz;

/** Копия окружения с заменой PATH (на Windows ключ может быть Path). */
function envWith(extra, pathValue) {
  // глобальный конфиг форка — временный: настоящий конфиг пользователя тесты не трогают
  const env = { ...process.env, XDG_CONFIG_HOME: fs.mkdtempSync(path.join(os.tmpdir(), "symphysis-npx-xdg-")), ...extra };
  if (pathValue !== undefined) {
    for (const k of Object.keys(env)) if (k.toLowerCase() === "path") delete env[k];
    env[win ? "Path" : "PATH"] = pathValue;
  }
  for (const [k, v] of Object.entries(extra)) if (v === undefined) delete env[k];
  return env;
}

function npx(args, env) {
  // Абсолютный путь Windows npx принимает за имя команды и молча выходит с 0 — нужен префикс file:
  const spec = `file:${tgz.split(path.sep).join("/")}`;
  const q = (s) => `"${s}"`;
  const line = `npx --yes ${q(spec)} ${args.map((a) => (/\s/.test(a) ? q(a) : a)).join(" ")}`;
  return win
    ? spawnSync(line, { encoding: "utf8", shell: true, env, timeout: TIMEOUT })
    : spawnSync("npx", ["--yes", spec, ...args], { encoding: "utf8", env, timeout: TIMEOUT });
}

const opts = { skip: hasNpm ? false : "npm нет в PATH" };
let cache;

before(() => {
  if (!hasNpm) return;
  cache = mk("npm-cache");
});

after(() => {
  fs.rmSync(tmpRoot, { recursive: true, force: true });
});

test("npm pack: tarball с payload и скриптом, без test/ и node_modules/", opts, () => {
  const dest = mk("pack");
  const r = spawnSync(`npm pack --pack-destination "${dest}"`, { encoding: "utf8", shell: true, cwd: installerDir, timeout: TIMEOUT });
  assert.equal(r.status, 0, r.stdout + r.stderr);
  const name = r.stdout.trim().split(/\r?\n/).filter(Boolean).pop().trim();
  tgz = path.join(dest, name);
  assert.ok(fs.existsSync(tgz), `нет ${tgz}`);
  const t = spawnSync("tar", ["-tf", name], { cwd: dest, encoding: "utf8", maxBuffer: 64 * 1024 * 1024 });
  assert.equal(t.status, 0, t.stderr);
  const files = t.stdout.split(/\r?\n/).filter(Boolean);
  assert.ok(files.includes("package/payload/openspec/schemas/symphysis/schema.yaml"), "нет payload схемы");
  assert.ok(files.includes("package/scripts/sync-payload.js"), "нет sync-payload.js");
  assert.ok(!files.some((f) => f.startsWith("package/test/")), "test/ попал в пакет");
  assert.ok(!files.some((f) => f.startsWith("package/node_modules/")), "node_modules/ попал в пакет");
});

test("npx install в чистый проект: записано, файлы на местах", opts, () => {
  assert.ok(tgz, "нужен tarball из предыдущего теста");
  requireFork(FORK);
  const project = mk("project");
  // Клиент настроен форком до установки, как в руководстве; конфиг — временный на эту команду.
  const init = spawnSync(process.execPath, [FORK, "init", "--tools", "claude"], { cwd: project, encoding: "utf8", env: envWith({ OPENSPEC_TELEMETRY: "0" }) });
  assert.equal(init.status, 0, init.stdout + init.stderr);
  const r = npx(["install", "--project", project], envWith({ NPM_CONFIG_CACHE: cache, npm_config_cache: cache, SYMPHYSIS_OPENSPEC: FORK }));
  assert.equal(r.status, 0, r.stdout + r.stderr);
  assert.match(r.stdout, /записано/);
  for (const f of [
    "openspec/schemas/symphysis/schema.yaml",
    "openspec/config.yaml",
    ".claude/skills/symphysis-brainstorm/SKILL.md",
    ".symphysis/tools/journal.py",
  ]) assert.ok(fs.existsSync(path.join(project, f)), `нет ${f}`);
});

test("npx check с форком из SYMPHYSIS_OPENSPEC: код 0, check: ok", opts, () => {
  requireFork(FORK);
  const project = path.join(tmpRoot, "project");
  // PyYAML у python на машине этому тесту ни к чему: о настройках — check.test.js.
  fs.rmSync(path.join(project, "symphysis.yaml"));
  const r = npx(["check", "--project", project], envWith({ NPM_CONFIG_CACHE: cache, npm_config_cache: cache, SYMPHYSIS_OPENSPEC: FORK }));
  assert.equal(r.status, 0, r.stdout + r.stderr);
  assert.match(r.stdout, /^check: ok$/m);
  // Инсталлятор не из клона: исходников рядом нет, сверки payload нет.
  assert.doesNotMatch(r.stdout, /payload/);
});

test("npx check без форка (нет переменной, PATH без openspec): код 2, «не найден»", opts, () => {
  const project = path.join(tmpRoot, "project");
  const empty = mk("empty-path");
  const nodeDir = path.dirname(process.execPath);
  const r = npx(
    ["check", "--project", project],
    envWith({ NPM_CONFIG_CACHE: cache, npm_config_cache: cache, SYMPHYSIS_OPENSPEC: undefined }, [empty, nodeDir].join(path.delimiter)),
  );
  assert.equal(r.status, 2, r.stdout + r.stderr);
  assert.match(r.stdout, /не найден/);
});

