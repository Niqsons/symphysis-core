// Проба F-53: `step_help.py` из настоящего процесса расширения VS Code с чистым профилем, на журнале этого изменения.
// PATH из реестра: такой получает процесс, запущенный из меню «Пуск» (сам запуск из меню не воспроизводится). След — probe.log рядом.
import { execFileSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { runTests } from "file:///X:/symphysis-vscode/node_modules/@vscode/test-electron/out/index.js";

const here = path.dirname(fileURLToPath(import.meta.url));
const project = path.resolve(here, "..", "..", "..", "..", "..");
const CODE = path.join(process.env.LOCALAPPDATA, "Programs", "Microsoft VS Code", "Code.exe");
const work = fs.mkdtempSync(path.join(os.tmpdir(), "symphysis-f53-"));
const out = path.join(work, "rows.json");
const ext = path.join(work, "ext");
fs.mkdirSync(ext);
fs.writeFileSync(path.join(ext, "package.json"), JSON.stringify({ name: "probe", publisher: "probe", version: "0.0.1", engines: { vscode: "^1.100.0" }, main: "./main.js" }));
fs.writeFileSync(path.join(ext, "main.js"), "exports.activate = () => {};");
fs.writeFileSync(path.join(ext, "test.js"), `
const { execFile } = require("node:child_process");
const fs = require("node:fs");
exports.run = async () => {
  const once = (env) => new Promise((resolve) => {
    const t0 = performance.now();
    execFile(process.env.PROBE_PYTHON, ["-X", "utf8", "tools/step_help.py", "--change", "step-help-tab"], { cwd: process.env.PROBE_PROJECT, env, encoding: "utf8", windowsHide: true, timeout: 30000, maxBuffer: 64 * 1024 * 1024 }, (err, stdout, stderr) => {
      let d = null;
      try { d = JSON.parse(stdout); } catch {}
      resolve({ ms: Math.round(performance.now() - t0), code: err ? err.code ?? "сбой" : 0, current: d && d.current_step, turn: d && d.turn, openspec: d && d.versions.openspec, tasks: d && d.tasks, error: d && d.error, kb: Math.round(stdout.length / 1024), stderr: stderr.slice(0, 200) });
    });
  });
  const rows = [{ case: "окружение хоста", vars: Object.keys(process.env).filter((k) => /^(VSCODE_|ELECTRON_|PYTHON|SYMPHYSIS|NoDefault)/i.test(k)).sort() }];
  for (let i = 0; i < 5; i++) rows.push({ case: "PATH процесса", ...(await once(process.env)) });
  const key = Object.keys(process.env).find((k) => /^path$/i.test(k));
  const noNpm = { ...process.env, [key]: process.env[key].split(";").filter((d) => !/[\\\\/]npm[\\\\/]?$/i.test(d)).join(";") };
  rows.push({ case: "PATH без каталога npm: форка нет", ...(await once(noNpm)) });
  fs.writeFileSync(process.env.PROBE_OUT, JSON.stringify(rows), "utf8");
};
`);

const registry = (scope) => execFileSync("powershell", ["-NoProfile", "-Command", `[Environment]::GetEnvironmentVariable('Path','${scope}')`], { encoding: "utf8" }).trim();
const python = execFileSync("python", ["-c", "import sys; print(sys.executable)"], { encoding: "utf8" }).trim();
const envPath = `${registry("Machine")};${registry("User")}`;
for (const k of Object.keys(process.env)) if (/^(VSCODE_|ELECTRON_|CLAUDE|NoDefaultCurrentDirectoryInExePath$|PYTHONIOENCODING$|SYMPHYSIS_|OPENSPEC_)/i.test(k)) delete process.env[k];
for (const k of Object.keys(process.env)) if (/^path$/i.test(k)) delete process.env[k];
process.env.Path = envPath;

let code = 0;
const log = [];
try {
  await runTests({
    vscodeExecutablePath: CODE,
    extensionDevelopmentPath: ext,
    extensionTestsPath: path.join(ext, "test.js"),
    extensionTestsEnv: { PROBE_PYTHON: python, PROBE_PROJECT: project, PROBE_OUT: out },
    launchArgs: [project, "--disable-extensions", "--user-data-dir", path.join(work, "profile"), "--extensions-dir", path.join(work, "extensions"), "--skip-welcome", "--skip-release-notes", "--disable-workspace-trust"],
  });
  for (const row of JSON.parse(fs.readFileSync(out, "utf8"))) log.push(JSON.stringify(row));
} catch (e) {
  log.push(JSON.stringify({ case: "сбой запуска", error: String(e) }));
  code = 1;
}
fs.writeFileSync(path.join(here, "probe.log"), log.join("\n") + "\n", "utf8");
console.log(log.join("\n"));
fs.rmSync(work, { recursive: true, force: true, maxRetries: 5, retryDelay: 500 });
process.exit(code);
