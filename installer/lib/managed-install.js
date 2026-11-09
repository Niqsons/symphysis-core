import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { clientTargets } from "./client-targets.js";
import { renderAgent } from "./agent-renderers.js";
import { createInstallationPlan, readInstallationManifest, normalizeInstallationRequest, installationKey, installationHash, installationPath, InstallationError } from "./installation-plan.js";
import { applyInstallationPlan } from "./installation-transaction.js";
import { userDirectory, resolvePlanningContext, resolveRuntime } from "./runtime-resolver.js";
import { userSchemaDirectory } from "./runtime-compatibility.js";
import { forkPin, runOpenspec, spawnTool } from "./openspec-bin.js";
import { planPlanningConfig } from "./planning-config.js";
import { globalConfigPath, otherConfigPath, readGlobalConfig } from "./global-config.js";
import { disableTelemetryIfUnset } from "./telemetry.js";
import { parseDocument } from "yaml";
import { validateWorkflowBundle, selectWorkflowCarriers } from "../scripts/build-workflow-carriers.js";
import { createPredecessorAdoptionProof } from "./predecessor-adoption.js";
import { ROOT, hasSources, payloadMatches } from "../scripts/sync-payload.js";

const here = path.dirname(fileURLToPath(import.meta.url));
export const DEFAULT_PAYLOAD = path.resolve(here, "..", "payload");
const packageInfo = () => JSON.parse(fs.readFileSync(path.resolve(here, "..", "package.json"), "utf8"));
const fail = (message) => { throw new InstallationError("installation-usage", message); };
export function payloadFiles(directory, prefix = "") {
  const stat = fs.lstatSync(directory, { throwIfNoEntry: false });
  if (!stat) return [];
  if (stat.isSymbolicLink() || !stat.isDirectory()) fail("Каталог ресурсов проходит через ссылку либо имеет неподходящий тип");
  return fs.readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    if (entry.isSymbolicLink()) fail("Payload не должен содержать ссылки");
    const relative = prefix ? `${prefix}/${entry.name}` : entry.name;
    return entry.isDirectory() ? payloadFiles(path.join(directory, entry.name), relative) : [relative];
  }).sort();
}
function versionText(payloadDir, sourceRoot, env) {
  let hash = null;
  if (fs.existsSync(sourceRoot) && hasSources(sourceRoot) && payloadMatches(payloadDir, sourceRoot)) {
    const top = spawnTool("git", ["-C", sourceRoot, "rev-parse", "--show-cdup"], { encoding: "utf8", env });
    if (!top.error && top.status === 0 && !top.stdout.trim()) {
      const result = spawnTool("git", ["-C", sourceRoot, "rev-parse", "--short", "HEAD"], { encoding: "utf8", env });
      if (!result.error && result.status === 0) hash = result.stdout.trim();
    }
  }
  return `${packageInfo().version}${hash ? `+${hash}` : ""}\n`;
}
function mergeTargets(previous, selected) {
  const clients = new Map(previous.map((client) => [client.id, client]));
  for (const selectedClient of selected) {
    const before = clients.get(selectedClient.id);
    if (!before) { clients.set(selectedClient.id, selectedClient); continue; }
    const merged = { ...before, ...selectedClient };
    for (const kind of ["skills", "agents", "commands"]) {
      const roots = [...(before[`${kind}Roots`] ?? []), ...(before[`${kind}Root`] ? [before[`${kind}Root`]] : []), ...(selectedClient[`${kind}Roots`] ?? []), ...(selectedClient[`${kind}Root`] ? [selectedClient[`${kind}Root`]] : [])];
      merged[`${kind}Roots`] = [...new Map(roots.map((root) => [installationKey(root), root])).values()];
      delete merged[`${kind}Root`];
    }
    clients.set(selectedClient.id, merged);
  }
  return [...clients.values()];
}

/** The complete plan is validated before any installation write. No store is selected for global. */
export function planManagedInstall(project, options = {}) {
  const { scope = "local", env = process.env, payloadDir = DEFAULT_PAYLOAD, sourceRoot = ROOT, skillsDirs = [], agentsDirs = [], clients = [], run = runOpenspec } = options;
  if (!["local", "global"].includes(scope)) fail("--scope: допустимы local либо global");
  if (scope === "global" && (project !== undefined && project !== null || options.project !== undefined || options.store !== undefined)) fail("Global install не выбирает --project или --store; для store выполни symphysis init");
  if (scope === "local" && options.store !== undefined) fail("Local install использует --project; --store применяется при symphysis init");
  const storeRoot = scope === "local" ? path.resolve(project ?? process.cwd()) : null;
  if (storeRoot && !fs.statSync(storeRoot, { throwIfNoEntry: false })?.isDirectory()) fail(`--project: каталога нет: ${storeRoot}`);
  const root = scope === "global" ? userDirectory(env) : path.join(storeRoot, ".symphysis");
  const runtimeRoot = scope === "global" ? path.join(root, "runtime") : root;
  const pin = forkPin().openspecPin;
  const request = { scope, root, runtimeRoot, storeRoot, schemaDirectory: scope === "global" ? userSchemaDirectory(env) : path.join(storeRoot, "openspec", "schemas"), sourceVersion: packageInfo().version, openspecPin: pin, bootstrap: { command: process.execPath, args: [path.resolve(here, "..", "bin", "symphysis.js")] } };
  const manifestPath = path.join(root, "install-manifest.json");
  const previous = fs.existsSync(manifestPath) ? readInstallationManifest(manifestPath, normalizeInstallationRequest(request)) : null;
  const explicitTargets = clients.length || skillsDirs.length || agentsDirs.length;
  const selected = previous && !explicitTargets ? previous.clients : mergeTargets(previous?.clients ?? [], clientTargets({ scope, project: storeRoot, clients, skillsDirs, agentsDirs, env, home: options.home }));
  request.clients = selected;
  if (!fs.statSync(path.join(payloadDir, "skills"), { throwIfNoEntry: false })?.isDirectory()) fail(`payload не найден: ${payloadDir}`);
  const messages = [];
  const configPath = globalConfigPath(env);
  otherConfigPath(env);
  const fork = run(["--version"], { cwd: scope === "local" ? storeRoot : undefined, env });
  if (fork.error?.code === "fork-path-invalid") fail(fork.error.message);
  if (fork.notFound || fork.error || fork.status !== 0 || String(fork.stdout).trim() !== pin) {
    const message = `openspec: нужен закреплённый форк ${pin}; установи системную зависимость или задай SYMPHYSIS_OPENSPEC`;
    if (scope === "global") fail(message);
    messages.push(message);
  }
  if (scope === "local") {
    if (!fork.notFound && !fork.error && fork.status === 0 && String(fork.stdout).trim() === pin) {
      try {
        const planning = resolvePlanningContext({ project: storeRoot, env, run });
        if (installationKey(planning.root) !== installationKey(fs.realpathSync(storeRoot))) fail(`OpenSpec выбрал другой planning root: ${planning.root}. Открой сам store и выполни symphysis install --scope local --project "${planning.root}"`);
        const selected = resolveRuntime({ project: storeRoot, env, run });
        if (!selected.store || installationKey(selected.store.root) !== installationKey(planning.root)) fail("Planning root изменился при проверке local install; повтори действие после проверки native context");
        if (selected.scope === "global" && selected.runtime?.manifestPath && fs.existsSync(path.join(storeRoot, "openspec", "symphysis.json"))) {
          const transition = options.migrationContext;
          const source = transition?.sourceContext;
          if (!transition?.managementOnly || !transition.operationReady || source?.scope !== "global" || !source.store?.root || source.runtime?.generation !== selected.runtime.generation || selected.status !== "ready" || installationKey(source.store.root) !== installationKey(storeRoot)) throw new InstallationError("migration-required", "Store использует global-поставку; сначала просмотри symphysis migrate --to local --out <plan> и подтверди явную смену режима");
        }
      } catch (error) {
        if (error.code !== "no_openspec_root") throw error.exitCode ? error : new InstallationError(error.code ?? "planning-root-invalid", error.message);
      }
    } else {
      // This inspects only the explicitly addressed config to refuse a pointer;
      // it never searches for, or invents, another native planning root.
      for (const name of ["config.yaml", "config.yml"]) {
        const file = path.join(storeRoot, "openspec", name);
        if (!fs.existsSync(file)) continue;
        const doc = parseDocument(fs.readFileSync(file, "utf8"));
        if (doc.errors.length || doc.has("store")) fail("Нельзя подтвердить store pointer без закреплённого форка; восстанови OpenSpec и повтори local install без записи в source");
      }
    }
  }
  const python = ["python", "python3"].some((command) => {
    const result = spawnTool(command, ["--version"], { env, encoding: "utf8", timeout: 10000 });
    return !result.error && result.status === 0 && /^Python \d+\./.test(`${result.stdout ?? ""}${result.stderr ?? ""}`.trim());
  });
  if (!python) {
    const message = "python: python или python3 не отвечает; установи системную зависимость";
    if (scope === "global") fail(message);
    messages.push(message);
  }
  const files = [];
  const add = (source, target, bytes, purpose, clientId, projection = false) => files.push({ source, path: target, bytes: Buffer.from(bytes), purpose, ...(clientId ? { clientId } : {}), ...(projection ? { projection: true } : {}) });
  const canonical = (source) => add(source, path.join(runtimeRoot, source), fs.readFileSync(path.join(payloadDir, source)), source.split("/")[0]);
  for (const source of payloadFiles(payloadDir)) {
    if (/^(tools|docs)\//.test(source) && source !== "tools/journal-roots.json") canonical(source);
    else if (scope === "global" && /^(skills|agents)\//.test(source)) canonical(source);
    else if (source.startsWith("openspec/schemas/symphysis/")) {
      if (scope === "global") canonical(source);
      add(source, path.join(request.schemaDirectory, "symphysis", source.slice("openspec/schemas/symphysis/".length)), fs.readFileSync(path.join(payloadDir, source)), "schema", null, scope === "global");
    } else if (scope === "global" && source === "openspec/config.symphysis.yaml") canonical(source);
  }
  add("tools/symphysis-version.txt", path.join(runtimeRoot, "tools", "symphysis-version.txt"), versionText(payloadDir, sourceRoot, env), "version");
  const carriersPath = path.join(payloadDir, "docs", "workflow-carriers.json");
  let carriers = null;
  if (fs.existsSync(carriersPath)) {
    carriers = JSON.parse(fs.readFileSync(carriersPath, "utf8"));
    try { validateWorkflowBundle(carriers, { pin }); }
    catch (error) { fail(`Workflow carriers не соответствуют закреплённому форку: ${error.message}`); }
  } else fail("В payload нет guarded workflow-carriers.json; выполни сборку поставки");
  const configured = readGlobalConfig(env);
  let workflowSelection;
  try { workflowSelection = selectWorkflowCarriers(carriers, { profile: options.profile ?? (configured.state === "ok" ? configured.config.profile ?? "core" : "core"), workflows: configured.state === "ok" ? configured.config.workflows : undefined }); }
  catch (error) { fail(`Workflow profile: ${error.message}`); }
  for (const client of selected) {
    for (const relative of payloadFiles(path.join(payloadDir, "skills"))) {
      if (!relative.startsWith("symphysis-")) continue;
      for (const target of client.skillsRoots ?? []) add(`skills/${relative}`, path.join(target, relative), fs.readFileSync(path.join(payloadDir, "skills", relative)), "skill", client.id, scope === "global");
    }
    for (const name of payloadFiles(path.join(payloadDir, "agents")).filter((file) => /^symphysis-.*-driver\.md$/.test(file))) {
      const agent = renderAgent({ clientId: client.id, name: name.slice(0, -3), source: fs.readFileSync(path.join(payloadDir, "agents", name), "utf8") });
      for (const target of client.agentsRoots ?? []) add(`agents/${agent.fileName}`, path.join(target, agent.fileName), agent.content, "agent", client.id, scope === "global");
    }
    const selectedCarriers = workflowSelection.files.filter((file) => file.clientId === client.id);
    for (const id of ["new", "continue", "apply", "sync", "archive"]) if (!selectedCarriers.some((file) => file.id === id)) fail(`Workflow ${id} отсутствует для ${client.id}`);
    for (const carrier of selectedCarriers) {
      if (!["skill", "command"].includes(carrier.kind) || typeof carrier.relativePath !== "string" || path.isAbsolute(carrier.relativePath) || carrier.relativePath.split(/[\\/]/).some((part) => !part || part === "." || part === "..")) fail("Неверный путь workflow carrier");
      const kind = carrier.kind === "skill" ? "skills" : "commands";
      const targets = client[`${kind}Roots`] ?? (client[`${kind}Root`] ? [client[`${kind}Root`]] : []);
      const relative = kind === "commands" && client.id === "claude" ? carrier.relativePath.replace(/^opsx\//, "") : carrier.relativePath;
      for (const target of targets) add(`${kind}/${relative}`, path.join(target, relative), carrier.content, "workflow", client.id, scope === "global");
    }
  }
  const nonOwned = scope === "local" ? planPlanningConfig({ storeRoot, sourceConfig: fs.readFileSync(path.join(payloadDir, "openspec", "config.symphysis.yaml"), "utf8") }) : [];
  messages.push(...nonOwned.flatMap((operation) => operation.message ? [operation.message] : []));
  const ignored = nonOwned.find((operation) => operation.kind === "gitignore-merge");
  if (ignored?.addedEntries.includes("symphysis.yaml")) messages.push(".gitignore: добавлена строка symphysis.yaml — правка уйдёт в git вместе с работой");
  if (ignored?.addedEntries.some((entry) => entry !== "symphysis.yaml")) messages.push(".gitignore: добавлены личная карта корней и служебные файлы установки");
  const desired = new Set(files.map((file) => installationKey(file.path)));
  const adoptionProof = options.reviewKnownPredecessors ? createPredecessorAdoptionProof({ request, files, bundle: carriers }) : undefined;
  const retired = new Set((adoptionProof?.retiredFiles ?? []).map((file) => installationKey(file.path)));
  const previousTargets = new Set((previous?.files ?? []).map((file) => installationKey(file.path)));
  const schemaRoots = [path.join(request.schemaDirectory, "symphysis"), ...(scope === "global" ? [path.join(runtimeRoot, "openspec", "schemas", "symphysis")] : [])];
  for (const schemaRoot of schemaRoots) for (const relative of payloadFiles(installationPath(schemaRoot, { directory: true }))) {
    const target = path.join(schemaRoot, relative);
    if (!desired.has(installationKey(target)) && !previousTargets.has(installationKey(target)) && !retired.has(installationKey(target))) throw new InstallationError("installation-conflict", `${target}: неизвестный файл схемы сохранён; native схема не совпадёт с управляемой поставкой. Требуется явное разрешение конфликта, --force его не отменяет.`);
  }
  const removeFiles = (previous?.files ?? []).filter((file) => file.source !== ".symphysis-runtime.json" && !desired.has(installationKey(file.path))).map((file) => file.path);
  const plan = createInstallationPlan({ ...request, files, nonOwned, removeFiles: [...new Set([...removeFiles, ...(adoptionProof?.retiredFiles ?? []).map((file) => file.path)])], adoptionProof });
  const merged = nonOwned.filter((operation) => operation.kind === "planning-config" && operation.beforeHash !== null && operation.beforeHash !== installationHash(operation.bytes)).map((operation) => operation.path);
  return { plan, messages, root, runtimeRoot, scope, storeRoot, clients: selected, merged, configPath, adoptions: adoptionProof?.files ?? [], retiredPredecessors: adoptionProof?.retiredFiles ?? [] };
}

export function installManaged(project, options = {}) {
  if (options.migrationContext) fail("Migration candidate можно применить только подтверждённой migration transaction");
  if (options.reviewKnownPredecessors) fail("Принятие известного предшественника требует preview и подтверждённого apply-plan");
  const prepared = planManagedInstall(project, options);
  if (!prepared.plan.ready) {
    const text = prepared.plan.conflicts.map((conflict) => `${conflict.path}: ${conflict.message}`).join("\n");
    throw new InstallationError("installation-conflict", `${text}\nЧужие и изменённые файлы сохранены; --force не отменяет ownership. Для известных прежних носителей используй install --preview, затем --apply-plan --confirm; неизвестные требуют ручного разрешения.`);
  }
  const applied = applyInstallationPlan(prepared.plan);
  return finishManagedInstallation(prepared, applied, options);
}

export function finishManagedInstallation(prepared, applied, options = {}) {
  const telemetry = disableTelemetryIfUnset({ env: options.env ?? process.env, ...(options.run ? { run: options.run } : {}) });
  return { ...applied, merged: prepared.merged, skipped: [], messages: [...prepared.messages, ...(telemetry ? [telemetry] : []), `openspec: глобальный конфиг ${prepared.configPath}`, ...prepared.clients.map((client) => `${client.id}: файлы установлены; native discovery и session verification: unconfirmed`)] };
}
