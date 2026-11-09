import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { createHash } from "node:crypto";
import { describeFailure, forkPin, runOpenspec } from "./openspec-bin.js";
import { BOOTSTRAP_API, RUNTIME_API, SCHEMA_API } from "./runtime-api.js";
import { checkRuntimeCompatibility, userSchemaDirectory } from "./runtime-compatibility.js";
import { pendingManagementState } from "./runtime-leases.js";
import { evaluateClientReadiness } from "./client-readiness.js";
import { isFullyAbsolute } from "./paths.js";
import { legacySourceEvidence } from "./legacy-source-proof.js";

export { BOOTSTRAP_API, RUNTIME_API, SCHEMA_API } from "./runtime-api.js";
export const TOOL_NAMES = Object.freeze({ journal: "journal.py", trace: "trace_graph.py", anchors: "anchor_refs.py", help: "step_help.py", config: "symphysis_config.py" });
export const LEGACY_TOOL_FILES = Object.freeze([...Object.values(TOOL_NAMES), "journal_cli.py", "journal_render.py", "journal_model.py", "roots.py", "openspec_run.py"]);
const LEGACY_FILES = LEGACY_TOOL_FILES;
const object = (value) => value !== null && typeof value === "object" && !Array.isArray(value);
const exists = (file) => fs.lstatSync(file, { throwIfNoEntry: false }) !== undefined;
const fileExists = (file) => fs.statSync(file, { throwIfNoEntry: false })?.isFile() === true;
const resourceKey = (file) => process.platform === "win32" ? path.resolve(file).toLowerCase() : path.resolve(file);
export const samePath = (first, second) => path.relative(fs.realpathSync(first), fs.realpathSync(second)) === "";
const within = (base, target) => {
  const relative = path.relative(base, target);
  return relative === "" || (relative !== ".." && !relative.startsWith(`..${path.sep}`) && !path.isAbsolute(relative));
};
export const readJson = (file) => JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(fs.readFileSync(file)));
export const diagnostic = (code, message, action) => ({ code, message, action });

/** The product data directory; computing it never reads a client profile. */
export function userDirectory(env = process.env, platform = process.platform, home = os.homedir()) {
  const absolute = (value, name) => {
    if (!isFullyAbsolute(value)) throw new Error(`${name}: нужен абсолютный путь`);
    return path.resolve(value);
  };
  if (env.SYMPHYSIS_HOME) return absolute(env.SYMPHYSIS_HOME, "SYMPHYSIS_HOME");
  if (env.XDG_DATA_HOME) return path.join(absolute(env.XDG_DATA_HOME, "XDG_DATA_HOME"), "symphysis");
  if (platform === "win32") return path.join(env.LOCALAPPDATA ? absolute(env.LOCALAPPDATA, "LOCALAPPDATA") : path.join(home, "AppData", "Local"), "symphysis");
  return path.join(home, ".local", "share", "symphysis");
}

/** Only a journal's documented address gives a second starting point to OpenSpec. */
function journalRoot(journal, sourceCwd) {
  const absolute = path.resolve(sourceCwd, journal);
  const normalized = absolute.split(path.sep);
  const offset = normalized.lastIndexOf("openspec");
  if (offset < 0 || normalized[offset + 1] !== "changes" || normalized.length <= offset + 3) throw new Error("журнал должен лежать в openspec/changes/<имя>/");
  return { root: path.resolve(`${normalized.slice(0, offset).join(path.sep)}${path.sep}`), absolute };
}

/** Missing files still inherit their nearest existing parent's real boundary. */
export function addressInside(root, address) {
  if (!within(path.resolve(root), path.resolve(address))) return false;
  let parent = path.resolve(address);
  while (!exists(parent)) {
    const next = path.dirname(parent);
    if (parent === next) return false;
    parent = next;
  }
  return within(fs.realpathSync(root), fs.realpathSync(parent));
}

function planningRoot(sourceCwd, store, run, env) {
  const result = run(["context", "--json", ...(store === undefined ? [] : ["--store", store])], { cwd: sourceCwd, env });
  if (result.notFound || result.error) throw Object.assign(new Error(describeFailure(result)), { code: result.notFound ? "fork-missing" : "fork-launch-error" });
  let data;
  try { data = JSON.parse(result.stdout); } catch { throw new Error("openspec context: неверный JSON"); }
  if (result.status !== 0 || !object(data.root)) {
    const problem = data.status?.[0];
    throw Object.assign(new Error(problem?.message ? `${problem.message}${problem.fix ? ` ${problem.fix}` : ""}` : describeFailure(result)), { code: problem?.code ?? "planning-root-invalid" });
  }
  if (!isFullyAbsolute(data.root.path) || data.root.role !== "openspec_root" || data.root.source === "implicit" || !fs.statSync(path.join(data.root.path, "openspec"), { throwIfNoEntry: false })?.isDirectory()) throw new Error("openspec context: нет действительного planning root");
  return { root: fs.realpathSync(data.root.path), id: data.root.store_id ?? null, sourceCwd };
}

/** Management uses the same native root contract without asserting runtime/store readiness. */
export function resolvePlanningContext({ project = process.cwd(), store, run = runOpenspec, env = process.env } = {}) {
  const sourceCwd = path.resolve(project);
  if (!fs.statSync(sourceCwd, { throwIfNoEntry: false })?.isDirectory()) throw new Error("Каталог --project не существует");
  return planningRoot(sourceCwd, store, run, env);
}

function localInstallation(storeRoot) {
  const root = path.join(storeRoot, ".symphysis");
  const manifestPath = path.join(root, "install-manifest.json");
  if (exists(manifestPath) || pendingManagementState(root) || LEGACY_FILES.some((file) => exists(path.join(root, "tools", file)))) return { root, toolsRoot: path.join(root, "tools"), manifestPath };
  // Supported pre-.symphysis flat layout; a data-only tools directory is insufficient.
  if (LEGACY_FILES.some((file) => exists(path.join(storeRoot, "tools", file)))) return { root: storeRoot, toolsRoot: path.join(storeRoot, "tools"), manifestPath: path.join(storeRoot, "install-manifest.json") };
  return null;
}

function manifestData(file, scope) {
  const value = readJson(file);
  if (!object(value) || value.format !== 1 || value.scope !== scope || typeof value.generation !== "string" || !value.generation || typeof value.sourceVersion !== "string" || !value.sourceVersion || !["bootstrapApi", "runtimeApi", "schemaApi"].every((key) => Number.isSafeInteger(value[key]) && value[key] > 0) || !Array.isArray(value.files) || !Array.isArray(value.clients)) throw new Error("неподдерживаемая структура manifest");
  const paths = new Set();
  for (const entry of value.files) {
    if (!object(entry) || !isFullyAbsolute(entry.path) || !/^[a-f0-9]{64}$/.test(entry.sha256 ?? "") || typeof entry.source !== "string" || !entry.source || /[\\:\0]/.test(entry.source) || entry.source.split("/").some((part) => !part || part === "." || part === "..") || typeof entry.purpose !== "string") throw new Error("неверная запись собственного файла manifest");
    if (["symphysis.yaml", "journal-roots.json"].includes(path.basename(entry.source))) throw new Error("личные данные не являются заменяемым ресурсом manifest");
    const key = path.resolve(entry.path);
    if (paths.has(key)) throw new Error("повтор собственного файла manifest");
    paths.add(key);
  }
  for (const client of value.clients) {
    if (!object(client) || Object.entries(client).some(([key, target]) => key.endsWith("Root") && !isFullyAbsolute(target))) throw new Error("неверный абсолютный клиентский корень manifest");
  }
  if (value.bootstrap !== undefined && (!object(value.bootstrap) || !isFullyAbsolute(value.bootstrap.command) || !Array.isArray(value.bootstrap.args) || value.bootstrap.args.some((arg) => typeof arg !== "string"))) throw new Error("неверный абсолютный bootstrap manifest");
  return value;
}

function resourceMaps(runtime, manifest, storeRoot, unavailable) {
  const usable = (file) => fileExists(file) && !unavailable.has(resourceKey(file)) && (!manifest || manifest.files.some((entry) => path.relative(entry.path, file) === ""));
  const resources = { tools: {}, docs: {}, skills: {}, templates: {}, assets: {}, schema: { name: "symphysis", path: runtime.schemaRoot } };
  for (const [name, file] of Object.entries(TOOL_NAMES)) {
    const target = path.join(runtime.toolsRoot, file);
    if (usable(target)) resources.tools[name] = target;
  }
  for (const [name, target] of Object.entries({ mermaid: path.join(runtime.toolsRoot, "mermaid.min.js"), mermaidLicense: path.join(runtime.toolsRoot, "mermaid.LICENSE"), version: path.join(runtime.toolsRoot, "symphysis-version.txt"), steps: path.join(runtime.schemaRoot, "steps.md") })) if (usable(target)) resources.assets[name] = target;
  const add = (source, target) => {
    if (source.startsWith("docs/")) resources.docs[source.slice(5)] = target;
    const skill = /^skills\/([^/]+)\/SKILL\.md$/.exec(source);
    if (skill) resources.skills[skill[1]] = target;
    const template = /^openspec\/schemas\/symphysis\/templates\/(.+)$/.exec(source);
    if (template) resources.templates[template[1]] = target;
  };
  if (manifest) {
    for (const entry of manifest.files) if (entry.projection !== true && usable(entry.path)) add(entry.source, entry.path);
  } else {
    if (fs.statSync(runtime.docsRoot, { throwIfNoEntry: false })?.isDirectory()) for (const file of fs.readdirSync(runtime.docsRoot, { withFileTypes: true })) if (file.isFile()) add(`docs/${file.name}`, path.join(runtime.docsRoot, file.name));
    for (const folder of [".claude", ".opencode", ".agents"]) {
      const skillsRoot = path.join(storeRoot, folder, "skills");
      if (fs.statSync(skillsRoot, { throwIfNoEntry: false })?.isDirectory()) for (const item of fs.readdirSync(skillsRoot, { withFileTypes: true })) {
        const target = path.join(skillsRoot, item.name, "SKILL.md");
        if (item.isDirectory() && fileExists(target) && !Object.hasOwn(resources.skills, item.name)) add(`skills/${item.name}/SKILL.md`, target);
      }
    }
    const templates = path.join(runtime.schemaRoot, "templates");
    if (fs.statSync(templates, { throwIfNoEntry: false })?.isDirectory()) for (const file of fs.readdirSync(templates, { withFileTypes: true })) if (file.isFile()) add(`openspec/schemas/symphysis/templates/${file.name}`, path.join(templates, file.name));
  }
  return resources;
}

function optionalWarning(source, file) {
  return { ...diagnostic("optional-resource-unavailable", `Необязательный ресурс выбранной поставки недоступен: ${source}`, "Восстанови ресурс выбранной поставки; недоступная справка/рисунок не заменяются другой установкой"), source, path: file };
}

function checkFiles(manifest, runtime, storeRoot, env, scope) {
  const problems = [];
  const unavailable = new Set();
  const warnings = [];
  for (const entry of manifest?.files ?? []) {
    // Runtime resources must not be redirected to arbitrary files by a manifest.
    const local = runtime.manifestPath === path.join(storeRoot, ".symphysis", "install-manifest.json");
    let base = runtime.root;
    let expected = path.join(base, entry.source);
    if (local && entry.source.startsWith("openspec/")) { base = storeRoot; expected = path.join(base, entry.source); }
    if ((local || entry.projection === true) && /^(skills|agents|commands)\//.test(entry.source)) {
      const kind = entry.source.split("/")[0];
      const clients = (manifest.clients ?? []).filter((client) => !entry.clientId || client.id === entry.clientId);
      const roots = [...(local ? [path.join(storeRoot, ".claude", kind)] : []), ...clients.flatMap((client) => [client[`${kind}Root`], ...(Array.isArray(client[`${kind}Roots`]) ? client[`${kind}Roots`] : [])]).filter((root) => isFullyAbsolute(root))];
      const suffix = entry.source.slice(kind.length + 1);
      const root = roots.find((root) => path.relative(path.join(root, suffix), entry.path) === "");
      if (!root) throw new Error(`неверная клиентская цель manifest: ${entry.source}`);
      base = root; expected = path.join(base, suffix);
    }
    if (!local && entry.projection === true && entry.source.startsWith("openspec/schemas/symphysis/")) {
      base = path.join(userSchemaDirectory(env), "symphysis");
      expected = path.join(base, entry.source.slice("openspec/schemas/symphysis/".length));
    }
    if (path.relative(expected, entry.path) !== "" || !within(base, entry.path)) throw new Error(`неверная цель ресурса manifest: ${entry.source}`);
    const missing = !exists(entry.path);
    const regular = fileExists(entry.path);
    if (regular && !within(fs.realpathSync(base), fs.realpathSync(entry.path))) throw new Error(`Ресурс перенаправлен за выбранный корень: ${entry.source}`);
    const mismatch = regular && createHash("sha256").update(fs.readFileSync(entry.path)).digest("hex") !== entry.sha256;
    if (!regular || mismatch) {
      unavailable.add(resourceKey(entry.path));
      if (scope === "local" && entry.source === "tools/symphysis-version.txt") continue;
      const optionalLocal = scope === "local" && ["tools/step_help.py", "tools/mermaid.min.js", "tools/mermaid.LICENSE"].includes(entry.source);
      if (optionalLocal || (missing && entry.source === "openspec/schemas/symphysis/steps.md")) warnings.push(optionalWarning(entry.source, entry.path));
      else problems.push(entry.source);
    }
  }
  return { problems, unavailable, warnings };
}

/** Select once. Read-only discovery never authorizes a later direct Python launch. */
export function resolveRuntime({ project, store, journal, tool, args = [], change, env = process.env, run = runOpenspec } = {}) {
  const result = runtimeResult();
  const block = (code, message, action) => { result.diagnostics.push(diagnostic(code, message, action)); return result; };
  const sourceCwd = path.resolve(project ?? process.cwd());
  try {
    if (!fs.statSync(sourceCwd, { throwIfNoEntry: false })?.isDirectory()) return block("project-invalid", "Каталог --project не существует", "Укажи существующий исходный каталог");
    let address;
    try { address = journal ? journalRoot(journal, sourceCwd) : null; } catch (error) { return block("store-mismatch", error.message, "Укажи журнал выбранного store"); }
    result.store = planningRoot(address?.root ?? sourceCwd, store, run, env);
    if (address && !samePath(address.root, result.store.root)) return block("store-mismatch", "Журнал и выбранный store относятся к разным planning roots", "Выбери store адресуемого журнала");
    if (address && !addressInside(result.store.root, address.absolute)) return block("store-mismatch", "Фактический путь журнала выходит за выбранный store", "Укажи журнал внутри выбранного store без перенаправляющей ссылки");
    if (address && project !== undefined && !samePath(planningRoot(sourceCwd, store, run, env).root, address.root)) return block("store-mismatch", "--project и журнал выбирают разные store", "Согласуй --project и адрес журнала");
    result.store.sourceCwd = sourceCwd;
  } catch (error) { return block("planning-root-invalid", error.message, "Проверь закреплённый форк, --project и регистрацию/указатель store"); }

  return inspectSelectedRuntime(result, { tool, args, change, journal, env, run });
}

function runtimeResult(store = null) {
  return { format: 1, status: "blocked", store, scope: null, runtime: null, resources: null, compatibility: { status: "unconfirmed", declarationPath: null }, clients: [], diagnostics: [], warnings: [] };
}

/** Private management selection shares all validation with public discovery. */
function inspectSelectedRuntime(result, { tool, args = [], change, journal, env, run, selection, purpose = "execute", schemaRemoval } = {}) {
  const block = (code, message, action) => { result.diagnostics.push(diagnostic(code, message, action)); return result; };

  const local = selection === "global" ? null : localInstallation(result.store.root);
  let selected = local;
  if (local) result.scope = "local";
  else {
    let home;
    try { home = userDirectory(env); } catch (error) { return block("user-dir-invalid", error.message, "Задай абсолютную базу пользовательской установки"); }
    const manifestPath = path.join(home, "install-manifest.json");
    const root = path.join(home, "runtime");
    if (!exists(manifestPath) && !exists(root) && !pendingManagementState(home)) return block("runtime-missing", "Поставка symphysis не установлена", "Выполни symphysis install для local либо install --scope global");
    selected = { root, toolsRoot: path.join(root, "tools"), manifestPath };
    result.scope = "global";
  }
  const legacy = result.scope === "local" && !exists(selected.manifestPath);
  const management = result.scope === "local" && selected.root === result.store.root ? path.join(selected.root, ".symphysis") : path.dirname(selected.manifestPath);
  if (pendingManagementState(management)) return block("installation-busy", "Выбранная поставка обновляется либо содержит незавершённую транзакцию", "Дождись завершения установки либо явно выполни install --recover после проверки владельца");
  let manifest = null;
  try {
    if (!legacy) manifest = manifestData(selected.manifestPath, result.scope);
  } catch (error) { return block("manifest-invalid", `Manifest выбранной ${result.scope}-поставки: ${error.message}`, "Восстанови выбранную поставку явной установкой; переход в другой scope не выполняется"); }
  const runtime = { root: selected.root, toolsRoot: selected.toolsRoot, docsRoot: path.join(selected.root, "docs"), schemaRoot: result.scope === "local" ? path.join(result.store.root, "openspec", "schemas", "symphysis") : path.join(selected.root, "openspec", "schemas", "symphysis"), manifestPath: legacy ? null : selected.manifestPath, generation: manifest?.generation ?? "legacy-local", sourceVersion: manifest?.sourceVersion ?? null, legacy, bootstrapApi: manifest?.bootstrapApi ?? BOOTSTRAP_API, runtimeApi: manifest?.runtimeApi ?? RUNTIME_API, schemaApi: manifest?.schemaApi ?? SCHEMA_API, journalContract: null };
  result.runtime = runtime;
  try {
    const checked = checkFiles(manifest, runtime, result.store.root, env, result.scope);
    result.clients = evaluateClientReadiness(manifest);
    const missing = checked.problems;
    result.warnings.push(...checked.warnings);
    result.resources = resourceMaps(runtime, manifest, result.store.root, checked.unavailable);
    const contractFile = path.join(runtime.toolsRoot, "journal_render.py");
    if (fileExists(contractFile) && (!manifest || manifest.files.some((entry) => path.relative(entry.path, contractFile) === ""))) runtime.journalContract = Number(/^CONTRACT\s*=\s*(\d+)\s*$/m.exec(fs.readFileSync(contractFile, "utf8"))?.[1]) || null;
    const required = Object.keys(TOOL_NAMES).filter((name) => !(result.scope === "local" && name === "help") && !result.resources.tools[name]);
    for (const [source, target, available] of [
      ["tools/step_help.py", path.join(runtime.toolsRoot, "step_help.py"), result.scope !== "local" || Boolean(result.resources.tools.help)],
      ["tools/mermaid.min.js", path.join(runtime.toolsRoot, "mermaid.min.js"), result.scope !== "local" || Boolean(result.resources.assets.mermaid)],
      ["openspec/schemas/symphysis/steps.md", path.join(runtime.schemaRoot, "steps.md"), exists(path.join(runtime.schemaRoot, "steps.md"))],
    ]) if (!available && !result.warnings.some((issue) => resourceKey(issue.path) === resourceKey(target))) result.warnings.push(optionalWarning(source, target));
    const schemaFile = path.join(runtime.schemaRoot, "schema.yaml");
    const schemaPresent = fileExists(schemaFile) && (!manifest || manifest.files.some((entry) => path.relative(entry.path, schemaFile) === ""));
    if (required.length || missing.length || !runtime.journalContract || !schemaPresent) return block(result.scope === "local" ? "local-damaged" : "resource-missing", `Неполная выбранная поставка: ${[...required, ...missing, ...(!runtime.journalContract ? ["journal contract"] : []), ...(!schemaPresent ? ["schema.yaml"] : [])].join(", ")}`, "Восстанови файлы выбранной поставки; ресурсы другой установки не используются");
  } catch (error) { return block("manifest-invalid", error.message, "Проверь состав и реальные цели файлов выбранной поставки"); }
  result.diagnostics.push(...checkRuntimeCompatibility(result, { tool, args, change, journal, env, run, purpose, schemaRemoval }));
  if (result.diagnostics.length === 0) result.status = "ready";
  return result;
}

/** Explicit init may prepare a declaration; this is never the public resolve response. */
export function resolveInitializationContext(options = {}) {
  const context = resolveRuntime(options);
  const refuse = (issue) => ({ ready: false, context, diagnostics: [issue] });
  if (context.scope === "local") return refuse(diagnostic("migration-required", "В выбранном store обнаружена local-поставка", "Сначала просмотри явный план symphysis migrate --to global"));
  if (!context.runtime || !context.resources || context.diagnostics.some((item) => !["declaration-missing", "declaration-incompatible", "schema-source-conflict"].includes(item.code))) return { ready: false, context, diagnostics: context.diagnostics };
  const diagnostics = checkRuntimeCompatibility(context, { ...options, purpose: "initialize" });
  // Store compatibility remains unconfirmed until the declaration is published.
  context.status = "blocked";
  context.compatibility.status = "unconfirmed";
  return { ready: diagnostics.length === 0, context, diagnostics };
}

/** Management-only preview: one native planning root, never a launchable candidate. */
export function resolveMigrationContext({ project, store, to, env = process.env, run = runOpenspec, schemaRemovalProof } = {}) {
  const result = { managementOnly: true, sourceContext: null, candidateContext: null, planningRoot: null, diagnostics: [], operationReady: false };
  const problem = (code, message, action) => { result.diagnostics.push(diagnostic(code, message, action)); return result; };
  if (!["local", "global"].includes(to)) return problem("migration-scope-invalid", "Для preview нужен явный --to local|global", "Выбери целевой scope миграции");
  if (schemaRemovalProof !== undefined && typeof schemaRemovalProof !== "function") return problem("migration-proof-invalid", "Proof строит внутренний синхронный planner; JSON не исполняется как функция", "Повтори preview штатной командой миграции");
  let planning;
  try { planning = resolvePlanningContext({ project, store, env, run }); }
  catch (error) { return problem("planning-root-invalid", error.message, "Проверь указатель/регистрацию store и закреплённый OpenSpec"); }
  result.planningRoot = { ...planning };
  const source = inspectSelectedRuntime(runtimeResult({ ...planning }), { env, run });
  source.status = "blocked";
  result.sourceContext = source;
  if (!source.runtime || !["local", "global"].includes(source.scope)) {
    result.diagnostics.push(...source.diagnostics);
    return result;
  }
  if (source.diagnostics.length) {
    result.diagnostics.push(...source.diagnostics.map((issue) => ({ ...issue, action: `${issue.action}; сначала согласуй исходный scope, затем повтори preview миграции` })));
    return result;
  }
  // Local operation does not require a global declaration. A declaration that
  // already exists still describes store data; changing scope cannot repair it.
  const declarationPath = path.join(planning.root, "openspec", "symphysis.json");
  if (exists(declarationPath)) {
    let declaration;
    try { declaration = readJson(declarationPath); }
    catch { return problem("declaration-incompatible", "Существующая декларация store не является корректным JSON", "Согласуй декларацию до preview смены scope; миграция не преобразует данные"); }
    if (!object(declaration) || declaration.format !== 1 || declaration.runtimeApi !== RUNTIME_API || declaration.schemaApi !== SCHEMA_API) return problem("declaration-incompatible", "Существующая декларация store несовместима с поддерживаемым API", "Согласуй декларацию до preview смены scope; миграция не преобразует данные");
  }
  if (source.scope === to) return problem("migration-already-selected", `Store уже выбирает ${to}`, "Используй init/check либо явное обновление этой установки");
  if (source.runtime.bootstrapApi !== BOOTSTRAP_API || source.runtime.runtimeApi !== RUNTIME_API || source.runtime.schemaApi !== SCHEMA_API) return problem("runtime-incompatible", "Исходная поставка использует неподдерживаемый API", "Согласуй исходную поставку перед планированием смены scope");
  const pin = forkPin().openspecPin;
  const version = run(["--version"], { cwd: planning.root, env });
  let manifest;
  try { manifest = source.runtime.manifestPath ? readJson(source.runtime.manifestPath) : null; }
  catch (error) { return problem("manifest-invalid", error.message, "Повтори preview по действительному manifest исходной поставки"); }
  if (manifest && (manifest.format !== 1 || manifest.scope !== source.scope || manifest.generation !== source.runtime.generation)) return problem("manifest-invalid", "Исходный manifest изменился во время разрешения миграции", "Повтори preview по текущей поставке");
  if (version.error || version.notFound || version.status !== 0 || String(version.stdout).trim() !== pin || (manifest?.openspecPin !== undefined && manifest.openspecPin !== pin)) return problem("fork-incompatible", "Исходная поставка и фактический форк не согласованы с bootstrap", "Укажи закреплённый форк и повтори preview");
  if (to === "local") {
    // The new local candidate is a validated package plan, not another installed
    // runtime. Its bytes and targets are checked by planManagedInstall.
    result.operationReady = true;
    return result;
  }
  let proof;
  try {
    proof = schemaRemovalProof?.(source);
    if (proof?.then) throw new Error("Proof удаления должен строиться синхронно");
  } catch (error) { return problem("migration-proof-invalid", error.message, "Разреши конфликты исходной поставки и повтори preview"); }
  if (!source.runtime.manifestPath) {
    try {
      if (!legacySourceEvidence(proof, source)) problem("migration-ownership-unconfirmed", "Legacy local требует typed proof точной известной генерации", "Подготовь preview по поставленному inventory; неизвестные файлы сохраняются");
    } catch (error) { return problem("migration-proof-invalid", error.message, "Состав legacy-поставки изменился после проверки; повтори preview"); }
  }
  const candidate = inspectSelectedRuntime(runtimeResult({ ...planning }), { env, run, selection: "global", purpose: "migration-preview", schemaRemoval: { proof, sourceContext: source } });
  candidate.status = "blocked";
  candidate.compatibility.status = "unconfirmed";
  for (const issue of candidate.diagnostics) if (issue.code === "runtime-missing") issue.action = "Сначала выполни symphysis install --scope global и повтори preview выбранного store";
  result.candidateContext = candidate;
  result.diagnostics.push(...candidate.diagnostics);
  result.operationReady = result.diagnostics.length === 0;
  return result;
}
