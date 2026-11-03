import { test, afterEach } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { describeFailure, runOpenspec } from "../lib/openspec-bin.js";
import { requireFork } from "../scripts/build-vendor.js";
import { tempDir } from "../test-support/temp-dir.js";

const here = path.dirname(fileURLToPath(import.meta.url));
const bin = path.resolve(here, "..", "bin", "symphysis.js");
const FORK = path.resolve(here, "..", "..", "upstream", "openspec", "bin", "openspec.js");
const win = process.platform === "win32";
const saved = { openspec: process.env.SYMPHYSIS_OPENSPEC, path: process.env.PATH, Path: process.env.Path };
const nodeDir = path.dirname(process.execPath);

afterEach(() => {
  for (const [k, v] of [["SYMPHYSIS_OPENSPEC", saved.openspec], ["PATH", saved.path], ["Path", saved.Path]]) {
    if (v === undefined) delete process.env[k];
    else process.env[k] = v;
  }
});

const tmp = (prefix = "symphysis-bin-") => tempDir(prefix);

/** Настоящий `.cmd` той же формы, что шим npm: `%*` разбирается второй раз. */
function printingCmd(dir) {
  fs.writeFileSync(path.join(dir, "print-args.js"), "console.log(JSON.stringify(process.argv.slice(2)));\n");
  const cmd = path.join(dir, "openspec.cmd");
  fs.writeFileSync(cmd, `@echo off\r\n"${process.execPath}" "%~dp0print-args.js" %*\r\n`);
  return cmd;
}

const onlyOnPath = (...dirs) => {
  delete process.env.SYMPHYSIS_OPENSPEC;
  process.env.PATH = dirs.join(path.delimiter);
  process.env.Path = process.env.PATH;
};

const ARGS = ["update", "C:\\a b\\проект", "x&y", "(скобки)", "100%", "%PATH%", "a^b", "a;b,c", "!x!", "хвост\\", 'внутри"кавычка'];

test("Вызов форка через openspec.cmd: аргументы из PATH доходят как есть", { skip: !win }, () => {
  const dir = tmp();
  printingCmd(dir);
  onlyOnPath(dir, nodeDir);
  const r = runOpenspec(ARGS);
  assert.equal(r.status, 0, r.stderr);
  assert.deepEqual(JSON.parse(r.stdout), ARGS);
});

test("Вызов форка через openspec.cmd: путь к .cmd с пробелом и скобками в SYMPHYSIS_OPENSPEC", { skip: !win }, () => {
  const dir = tempDir("symphysis bin (тест) ");
  process.env.SYMPHYSIS_OPENSPEC = printingCmd(dir);
  const r = runOpenspec(ARGS);
  assert.equal(r.status, 0, r.stderr);
  assert.deepEqual(JSON.parse(r.stdout), ARGS);
});

test("отказ форка отличается от «не найден»", { skip: !win }, () => {
  const dir = tmp();
  fs.writeFileSync(path.join(dir, "openspec.cmd"), "@echo off\r\necho boom 1>&2\r\nexit /b 3\r\n");
  onlyOnPath(dir);
  const r = runOpenspec(["update"]);
  assert.equal(r.notFound, false);
  assert.equal(r.status, 3);
  assert.equal(describeFailure(r), "openspec не отработал (код 3: boom)");
});

test("форка нет в PATH: notFound, текст «не найден», оболочка не зовётся", () => {
  onlyOnPath(tmp());
  const r = runOpenspec(["--version"]);
  assert.equal(r.notFound, true);
  assert.equal(describeFailure(r), "openspec не найден");
});

test("SYMPHYSIS_OPENSPEC указывает на файл, которого нет: notFound", () => {
  process.env.SYMPHYSIS_OPENSPEC = path.join(tmp(), "нет.js");
  assert.equal(runOpenspec(["--version"]).notFound, true);
});

test("каждый вызов идёт с OPENSPEC_TELEMETRY=0", () => {
  const js = path.join(tmp(), "env.js");
  fs.writeFileSync(js, "console.log(process.env.OPENSPEC_TELEMETRY);\n");
  process.env.SYMPHYSIS_OPENSPEC = js;
  assert.equal(runOpenspec([]).stdout.trim(), "0");
});

test("cwd доходит до дочернего процесса", () => {
  const js = path.join(tmp(), "cwd.js");
  fs.writeFileSync(js, "console.log(process.cwd());\n");
  process.env.SYMPHYSIS_OPENSPEC = js;
  const dir = tmp();
  assert.equal(fs.realpathSync(runOpenspec([], { cwd: dir }).stdout.trim()), fs.realpathSync(dir));
});

// Сценарий целиком: `install` на настоящем `.cmd`, путь проекта с пробелом, конфиг — временный на одну команду.
test("Вызов форка через openspec.cmd: install обновляет проект с пробелом в пути", { skip: !win }, () => {
  requireFork(FORK);
  const shim = tmp();
  fs.writeFileSync(path.join(shim, "openspec.cmd"), `@echo off\r\n"${process.execPath}" "${FORK}" %*\r\n`);
  const project = tempDir("symphysis проект ");
  const env = { ...process.env, XDG_CONFIG_HOME: tmp(), OPENSPEC_TELEMETRY: "0" };
  delete env.SYMPHYSIS_OPENSPEC;
  for (const k of Object.keys(env)) if (k.toLowerCase() === "path") delete env[k];
  env.Path = [shim, nodeDir, process.env.SystemRoot ? path.join(process.env.SystemRoot, "System32") : ""].join(path.delimiter);
  const init = spawnSync(process.execPath, [FORK, "init", "--tools", "claude"], { cwd: project, encoding: "utf8", env });
  assert.equal(init.status, 0, init.stdout + init.stderr);
  const cmdFile = path.join(project, ".claude", "commands", "opsx", "continue.md");
  fs.rmSync(cmdFile);
  fs.rmSync(path.join(project, ".claude", "skills", "openspec-continue-change"), { recursive: true });
  const r = spawnSync(process.execPath, [bin, "install", "--project", project], { encoding: "utf8", env });
  assert.equal(r.status, 0, r.stdout + r.stderr);
  assert.ok(fs.existsSync(cmdFile), r.stdout);
  assert.doesNotMatch(r.stdout, /не найден/);
});

test("Вызов форка через openspec.cmd: отказ форка в install назван своим текстом, код 0", { skip: !win }, () => {
  const shim = tmp();
  fs.writeFileSync(path.join(shim, "openspec.cmd"), "@echo off\r\necho boom 1>&2\r\nexit /b 3\r\n");
  const project = tmp();
  fs.mkdirSync(path.join(project, ".claude", "commands", "opsx"), { recursive: true });
  const env = { ...process.env, XDG_CONFIG_HOME: tmp() };
  delete env.SYMPHYSIS_OPENSPEC;
  for (const k of Object.keys(env)) if (k.toLowerCase() === "path") delete env[k];
  env.Path = [shim, nodeDir, process.env.SystemRoot ? path.join(process.env.SystemRoot, "System32") : ""].join(path.delimiter);
  const r = spawnSync(process.execPath, [bin, "install", "--project", project], { encoding: "utf8", env });
  assert.equal(r.status, 0, r.stdout + r.stderr);
  assert.match(r.stdout, /^continue: openspec не отработал \(код 3: boom\) — выполнить потом: openspec update$/m);
  assert.match(r.stdout, /^telemetry: openspec не отработал \(код 3: boom\) — выключить после установки: /m);
  assert.doesNotMatch(r.stdout, /не найден/);
});

// --- каталог вызова не участвует в поиске программы (только Windows) ---------------------------------------------------
// Среда агента или человека может сама задавать NoDefaultCurrentDirectoryInExePath: без снятия ключа из окружения (без учёта
// регистра) тесты ниже зелёны и без правки. Контрольный тест первым подтверждает, что в окружении проверки ключа нет.

const GUARD = "nodefaultcurrentdirectoryinexepath";
const WIN_ONLY = "поиск программы в каталоге вызова есть только на Windows";
const openspecBinUrl = new URL("../lib/openspec-bin.js", import.meta.url).href;

function envWithoutGuard() {
  return Object.fromEntries(Object.entries(process.env).filter(([key]) => key.toLowerCase() !== GUARD));
}

/** Код `script` исполняется отдельным node с `cwd` проекта и окружением без охранной переменной; печатает JSON. */
function inProject(project, script, env = envWithoutGuard()) {
  const r = spawnSync(process.execPath, ["--input-type=module", "-e", `import * as bin from ${JSON.stringify(openspecBinUrl)};\n${script}`], {
    cwd: project, env, encoding: "utf8",
  });
  assert.equal(r.status, 0, r.stderr);
  return JSON.parse(r.stdout);
}

/** Проект с `node.cmd`, пишущим маркер, и форк под настоящим `.cmd`-шимом, что зовёт голое `node`, как шим npm без `node.exe` рядом. */
function hostileNodeProject() {
  const dir = tmp();
  const project = path.join(dir, "proj");
  const bindir = path.join(dir, "bin");
  fs.mkdirSync(project);
  fs.mkdirSync(bindir);
  fs.writeFileSync(path.join(project, "node.cmd"), "@echo hostile> marker.txt\r\n@exit /b 0\r\n");
  fs.writeFileSync(path.join(bindir, "openspec.cmd"), "@node %*\r\n");
  return { project, shim: path.join(bindir, "openspec.cmd") };
}

test("Каталог вызова: в окружении проверки нет охранной переменной, и cmd.exe берёт node.cmd из cwd", { skip: !win && WIN_ONLY }, () => {
  const { project } = hostileNodeProject();
  assert.ok(!Object.keys(envWithoutGuard()).some((key) => key.toLowerCase() === GUARD));
  spawnSync("node", { cwd: project, env: envWithoutGuard(), shell: true });
  assert.ok(fs.existsSync(path.join(project, "marker.txt")));
});

test("Каталог вызова: runOpenspec не исполняет node.cmd из корня проекта", { skip: !win && WIN_ONLY }, () => {
  const { project, shim } = hostileNodeProject();
  inProject(project, `process.env.SYMPHYSIS_OPENSPEC = ${JSON.stringify(shim)};\nbin.runOpenspec(["--version"], { cwd: process.cwd() });\nconsole.log("{}");`);
  assert.ok(!fs.existsSync(path.join(project, "marker.txt")));
});

/** Копия node.exe под чужим именем: печатает версию node, а не версию настоящей программы. */
function hostileExe(project, name) {
  fs.copyFileSync(process.execPath, path.join(project, `${name}.exe`));
}

for (const [name, real] of [["python", /^Python \d/], ["git", /^git version/]]) {
  test(`Каталог вызова: spawnTool не берёт ${name}.exe из корня проекта`, { skip: !win && WIN_ONLY }, (t) => {
    if (spawnSync(name, ["--version"], { encoding: "utf8" }).status !== 0) return t.skip(`${name} не отвечает в этой среде`);
    const { project } = hostileNodeProject();
    hostileExe(project, name);
    const [out] = inProject(project, `console.log(JSON.stringify([bin.spawnTool(${JSON.stringify(name)}, ["--version"], { encoding: "utf8" }).stdout]));`);
    assert.match(out, real);
  });
}
