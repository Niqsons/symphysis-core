import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { resolveRuntime, resolveInitializationContext, diagnostic, addressInside, samePath } from "./runtime-resolver.js";
import { acquireReader } from "./runtime-leases.js";
import { watchCancellation } from "./runtime-cancellation.js";
import { executableCandidates, executableLauncher, forkPin, openspecEnvironment, openspecLauncher, runOpenspec, spawnTool, spawnToolAsync } from "./openspec-bin.js";
import { planManagedInstall } from "./managed-install.js";
import { applyInstallationPlan } from "./installation-transaction.js";
import { planProjectInitialization, initProject } from "./project-init.js";

const bin = fileURLToPath(new URL("../bin/symphysis.js", import.meta.url));
const pathFlags = new Set(["--roots", "--out", "--template", "--attack", "--render", "--install-dir"]);
const valueFlags = new Set([...pathFlags, "--date", "--format", "--capability", "--requirement", "--change", "--project"]);

const managementHelp = `symphysis openspec init/update — управляемые охраняемые носители\n\ninit [store-path] [--tools claude,codex,opencode|all] [--profile core|custom] [--force] [--no-animation]\nupdate [store-path] [--force] [--dry-run [--json]]\nОбщие --project/--store передавай перед openspec. Без --tools сохраняются прежние targets.\n--tools none не поддерживается; для настройки global-store без обновления носителей используй symphysis init.\nПрофиль берётся из native config; --profile действует только на эту операцию.\nЧужие и изменённые файлы сохраняются; --force не отменяет ownership.\n`;

/** A narrow native management adapter, never a passthrough generator command. */
export function managedNativeArguments(argv) {
  const command = argv[0];
  const result = { command, clients: [], profile: undefined, target: undefined, dryRun: false, json: false, help: false };
  const bad = (message, code = "management-arguments-invalid") => { throw Object.assign(new Error(message), { code, exitCode: 2 }); };
  if (!["init", "update"].includes(command)) bad("Нужна команда init или update");
  const seen = new Set();
  let literal = false;
  for (let index = 1; index < argv.length; index++) {
    const value = argv[index];
    if (typeof value !== "string" || value.includes("\0")) bad("Аргумент не является допустимой строкой");
    if (!literal && value === "--") { literal = true; continue; }
    if (!literal && value.startsWith("-")) {
      const equal = value.indexOf("=");
      const flag = equal < 0 ? value : value.slice(0, equal);
      if (["--project", "--store", "--store-path", "--change", "--schema"].includes(flag)) bad("Селекторы store/project задаются перед openspec; init/update не выбирают другую схему или изменение", "selector-conflict");
      if (["--help", "-h"].includes(flag)) { if (equal >= 0) bad("--help не принимает значение"); result.help = true; continue; }
      if (seen.has(flag)) bad(`Параметр ${flag} указан повторно`);
      seen.add(flag);
      if (["--tools", "--profile"].includes(flag) && command === "init") {
        const argument = equal < 0 ? argv[++index] : value.slice(equal + 1);
        if (typeof argument !== "string" || !argument || argument.startsWith("-") || argument.includes("\0")) bad(`У ${flag} нет допустимого значения`);
        if (flag === "--profile") { if (!["core", "custom"].includes(argument)) bad("--profile: допустимы core или custom"); result.profile = argument; }
        else {
          if (argument === "none") bad("--tools none не поддерживается управляемой установкой; для настройки global-store без обновления носителей используй symphysis init");
          const ids = argument === "all" ? ["claude", "codex", "opencode"] : argument.split(",");
          if (ids.some((id) => !["claude", "codex", "opencode"].includes(id))) bad("--tools: поддерживаются только claude, codex, opencode или all");
          result.clients = [...new Set(ids)];
        }
      } else if (equal < 0 && (flag === "--force" || (command === "init" && flag === "--no-animation"))) {
        // UI/force flags do not grant ownership or select another target.
      } else if (equal < 0 && command === "update" && ["--dry-run", "--json"].includes(flag)) result[flag === "--dry-run" ? "dryRun" : "json"] = true;
      else bad(`Параметр ${flag} не поддерживается управляемой командой ${command}`);
    } else {
      if (result.target !== undefined || !value) bad("Допустим один явный путь выбранного store");
      result.target = value;
    }
  }
  if (result.json && !result.dryRun) bad("--json доступен только вместе с update --dry-run");
  return result;
}

function managedNativeOperation(request, context, { env, stdout, stderr, sourceCwd }) {
  try {
    if (request.target !== undefined && !samePath(path.resolve(sourceCwd, request.target), context.store.root)) throw Object.assign(new Error("Позиционный путь выбирает другой store; убери путь либо укажи разрешённый planning root"), { code: "selector-conflict", exitCode: 2 });
    if (request.command === "init" && context.scope === "global") planProjectInitialization({ project: context.store.root, env });
    const prepared = planManagedInstall(context.scope === "global" ? undefined : context.store.root, { scope: context.scope, clients: request.clients, profile: request.profile, env });
    if (!prepared.plan.ready) throw Object.assign(new Error(prepared.plan.conflicts.map((item) => `${item.path}: ${item.message}`).join("\n")), { code: "installation-conflict", exitCode: 2 });
    if (request.dryRun) {
      const preview = { format: 1, operation: "openspec-update", scope: context.scope, storeRoot: context.store.root, ready: true, changes: prepared.plan.files.filter((operation) => operation.action !== "unchanged").map(({ path: file, action }) => ({ path: file, action })), messages: prepared.messages };
      if (request.json) stdout.write(`${JSON.stringify(preview, null, 2)}\n`);
      else { stdout.write(`План обновления ${context.scope}: ${preview.changes.length} изменений\n`); for (const item of preview.changes) stdout.write(`${item.action}: ${item.path}\n`); }
      return 0;
    }
    const installed = applyInstallationPlan(prepared.plan);
    stdout.write(`Управляемое ${request.command}: ${context.scope}, записано ${installed.written.length}\n`);
    for (const message of prepared.messages) stdout.write(`${message}\n`);
    if (request.command === "init" && context.scope === "global") {
      const initialized = initProject({ project: context.store.root, env });
      for (const message of initialized.messages) stdout.write(`${message}\n`);
    }
    return 0;
  } catch (error) { stderr.write(`${error.code ?? "management-error"}: ${error.message}\n`); return error.exitCode ?? 1; }
}

/** Normalize only the existing tools' documented path arguments; keep values as argv. */
export function toolArguments(tool, argv, sourceCwd) {
  const args = [...argv];
  const positionals = [];
  let literal = false;
  for (let index = 0; index < args.length; index++) {
    const argument = args[index];
    if (argument === "--") { literal = true; continue; }
    if (!literal && argument.startsWith("-")) {
      const equal = argument.indexOf("=");
      const flag = equal === -1 ? argument : argument.slice(0, equal);
      if (pathFlags.has(flag)) {
        if (equal !== -1) args[index] = `${flag}=${path.resolve(sourceCwd, argument.slice(equal + 1))}`;
        else if (args[index + 1] !== undefined && !args[index + 1].startsWith("-")) { args[index + 1] = path.resolve(sourceCwd, args[index + 1]); index++; }
      } else if (equal === -1 && valueFlags.has(flag)) index++;
      continue;
    }
    positionals.push(index);
  }
  let journal;
  if (tool === "journal") {
    for (const index of positionals.slice(1)) args[index] = path.resolve(sourceCwd, args[index]);
    if (args[positionals[0]] !== "import-md" && positionals.length > 1) journal = args[positionals[1]];
  } else if (tool === "trace") {
    const command = args[positionals[0]];
    if (command === "check" && positionals.length > 2) args[positionals[2]] = path.resolve(sourceCwd, args[positionals[2]]);
    if (command === "archive-gaps" && positionals.length > 1) args[positionals[1]] = path.resolve(sourceCwd, args[positionals[1]]);
  }
  return { args, journal };
}

export function namedResource(context, kind, id) {
  const maps = { skill: "skills", doc: "docs", template: "templates" };
  const map = maps[kind];
  if (!map || typeof id !== "string" || !Object.hasOwn(context.resources?.[map] ?? {}, id)) return { diagnostic: diagnostic("resource-missing", `В выбранной поставке нет ресурса ${kind}:${id}`, "Проверь идентификатор и целостность выбранной поставки; другая установка не используется") };
  return { file: context.resources[map][id] };
}

function pythonLauncher(args, env) {
  for (const name of ["python", "python3"]) {
    for (const executable of executableCandidates(name, env)) {
      // Windows Store Python can execute while denying stat of its package path.
      const probe = executableLauncher(executable, ["--version"]);
      const version = spawnTool(probe.command, probe.args, { shell: probe.shell, env, encoding: "utf8", timeout: 10000 });
      if (!version.error && version.status === 0 && /^Python \d+\./.test(`${version.stdout ?? ""}${version.stderr ?? ""}`.trim())) return executableLauncher(executable, args);
    }
  }
  return null;
}

function stopChild(child, signal) {
  if (!child.pid || child.exitCode !== null || child.signalCode !== null) return;
  if (process.platform === "win32") {
    const systemRoot = process.env.SystemRoot || process.env.WINDIR;
    if (systemRoot && path.isAbsolute(systemRoot)) spawnTool(path.join(systemRoot, "System32", "taskkill.exe"), ["/PID", String(child.pid), "/T", "/F"], { windowsHide: true, timeout: 10000, stdio: "ignore" });
    else child.kill();
  } else if (child.pid) {
    try { process.kill(-child.pid, signal); } catch { child.kill(signal); }
  }
}

async function childExit(launcher, context, env, stderr) {
  let child;
  let cancellationCode = null;
  const dispose = watchCancellation(env, (error) => {
    cancellationCode = error?.exitCode ?? 130;
    if (error) stderr.write(`${error.code}: ${error.message}\n`);
    if (child) stopChild(child, "SIGTERM");
  });
  const interrupted = (signal) => { cancellationCode = signal === "SIGINT" ? 130 : 143; if (child) stopChild(child, signal); };
  const int = () => interrupted("SIGINT");
  const term = () => interrupted("SIGTERM");
  process.once("SIGINT", int); process.once("SIGTERM", term);
  try {
    // Drain an already-requested control cancellation before launching any child.
    await Promise.resolve();
    if (cancellationCode !== null) return cancellationCode;
    child = spawnToolAsync(launcher.command, launcher.args, { cwd: context.store.root, env, shell: launcher.shell, stdio: "inherit", detached: process.platform !== "win32" });
    const code = await new Promise((resolve, reject) => {
      child.once("error", reject);
      child.once("close", (code, signal) => resolve(code ?? (signal === "SIGINT" ? 130 : 143)));
    });
    return cancellationCode ?? code;
  } finally { dispose(); process.removeListener("SIGINT", int); process.removeListener("SIGTERM", term); }
}

/** One preflight and one reader lease cover the complete operation. */
export async function dispatchTool(tool, argv, { project, store, env = process.env, stdout = process.stdout, stderr = process.stderr } = {}) {
  const sourceCwd = path.resolve(project ?? process.cwd());
  let management;
  if (tool === "openspec" && ["init", "update", "experimental"].includes(argv[0])) {
    if (argv[0] === "experimental") { stderr.write("management-arguments-invalid: Используй управляемый symphysis openspec init вместо deprecated experimental\n"); return 2; }
    try { management = managedNativeArguments(argv); }
    catch (error) { stderr.write(`${error.code}: ${error.message}\n`); return 2; }
    if (management.help) { stdout.write(managementHelp); return 0; }
  }
  // Store discovery precedes choosing a store. It reads the registry only and
  // must not need the declaration it helps the user select for initialization.
  if (tool === "openspec" && argv[0] === "store" && argv[1] === "list" && argv.slice(2).every((arg) => ["--json", "--help", "-h"].includes(arg))) {
    const version = runOpenspec(["--version"], { cwd: sourceCwd, env });
    if (version.error || version.notFound || version.status !== 0 || String(version.stdout).trim() !== forkPin().openspecPin) {
      stderr.write("fork-incompatible: Для чтения реестра нужен закреплённый форк OpenSpec\n"); return 2;
    }
    const registryEnv = openspecEnvironment(env);
    delete registryEnv.SYMPHYSIS_RUNTIME_CONTEXT;
    return childExit(openspecLauncher(argv, registryEnv), { store: { root: sourceCwd } }, registryEnv, stderr);
  }
  const prepared = tool === "openspec" ? { args: [...argv], journal: undefined } : toolArguments(tool, argv, sourceCwd);
  const initialization = management?.command === "init" ? resolveInitializationContext({ project, store, env }) : null;
  const context = initialization?.context ?? resolveRuntime({ project, store, tool, args: prepared.args, journal: prepared.journal, env });
  const refuse = (issue) => { stderr.write(`${issue.code}: ${issue.message}\n${issue.action}\n`); return 2; };
  const localInit = management?.command === "init" && context.scope === "local" && context.status === "ready";
  if (context.status !== "ready" && !(initialization?.ready || localInit)) { for (const issue of initialization?.diagnostics ?? context.diagnostics) refuse(issue); return 2; }
  if (management) return managedNativeOperation(management, context, { env, stdout, stderr, sourceCwd });
  if (!["openspec", "resource"].includes(tool) && !Object.hasOwn(context.resources.tools, tool)) return refuse(diagnostic("resource-missing", `В выбранной поставке недоступен проверенный инструмент ${tool}`, "Восстанови этот инструмент выбранной поставки; непроверенная копия не исполняется"));
  if (tool === "config") {
    const requested = prepared.args.findIndex((arg) => arg === "--project" || arg.startsWith("--project="));
    if (requested !== -1) return refuse(diagnostic("selector-conflict", "Вложенный --project не выбирает другой store", "Передай --project перед именем инструмента"));
    prepared.args.push("--project", context.store.root);
  }
  let resource;
  if (tool === "resource") {
    if (argv.length !== 2) return refuse(diagnostic("resource-missing", "Нужны вид и идентификатор ресурса", "Используй symphysis resource skill|doc|template <id>"));
    resource = namedResource(context, ...argv);
    if (resource.diagnostic) return refuse(resource.diagnostic);
  }
  // Inputs addressed to a journal cannot escape via a changed reparse component.
  if (prepared.journal && !addressInside(context.store.root, prepared.journal)) return refuse(diagnostic("store-mismatch", "Путь журнала изменился после разрешения store", "Повтори вызов с журналом выбранного store"));
  let lease;
  try {
    lease = acquireReader(context);
    if (resource) { stdout.write(new TextDecoder("utf-8", { fatal: true }).decode(fs.readFileSync(resource.file))); return 0; }
    const childEnv = openspecEnvironment(env);
    const launcher = tool === "openspec" ? openspecLauncher(prepared.args, childEnv) : pythonLauncher(["-X", "utf8", context.resources.tools[tool], ...prepared.args], childEnv);
    if (!launcher) return refuse(diagnostic("interpreter-missing", `${tool === "openspec" ? "OpenSpec" : "Python"} не найден в окружении запуска`, "Установи требуемый интерпретатор/форк и повтори вызов"));
    childEnv.SYMPHYSIS_RUNTIME_CONTEXT = JSON.stringify({ format: 1, status: "ready", store: context.store, scope: context.scope, runtime: context.runtime, resources: context.resources, lease: lease.descriptor, ...(tool === "openspec" ? {} : { launcher: { kind: "python", executable: launcher.command, dispatcherExecutable: process.execPath } }) });
    // This fixed bootstrap identity is data for child re-delegation, never a shell string.
    childEnv.SYMPHYSIS_BOOTSTRAP = JSON.stringify({ command: process.execPath, args: [bin] });
    return await childExit(launcher, context, childEnv, stderr);
  } catch (error) {
    stderr.write(`${error.code ?? "launch-error"}: ${error.message}\n`);
    return error.exitCode ?? 1;
  } finally { if (lease) lease.release(); }
}
