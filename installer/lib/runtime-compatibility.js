import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { createHash } from "node:crypto";
import { parse } from "yaml";
import { BOOTSTRAP_API, RUNTIME_API, SCHEMA_API } from "./runtime-api.js";
import { describeFailure, forkPin, runOpenspec } from "./openspec-bin.js";
import { isFullyAbsolute } from "./paths.js";
import { assertInstallationSnapshot } from "./installation-plan.js";
import { legacySourceEvidence } from "./legacy-source-proof.js";

const object = (value) => value !== null && typeof value === "object" && !Array.isArray(value);
const identifier = (value) => typeof value === "string" && /^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(value);
const digest = (bytes) => createHash("sha256").update(bytes).digest("hex");
const exists = (file) => fs.lstatSync(file, { throwIfNoEntry: false }) !== undefined;
const readJson = (file) => JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(fs.readFileSync(file)));
const inside = (root, target) => {
  const relative = path.relative(root, target);
  return relative === "" || (relative !== ".." && !relative.startsWith(`..${path.sep}`) && !path.isAbsolute(relative));
};
const equalPath = (first, second) => path.relative(fs.realpathSync(first), fs.realpathSync(second)) === "";

function fail(code, message, action) {
  throw Object.assign(new Error(message), { code, action });
}

function selectors(args) {
  const selected = {};
  for (let index = 0; index < args.length; index++) {
    const arg = args[index];
    if (arg === "--") break;
    const match = /^--(store|store-path|schema|change)(?:=(.*))?$/.exec(arg);
    if (!match) continue;
    const key = match[1];
    if (Object.hasOwn(selected, key)) fail("selector-conflict", `Параметр --${key} указан повторно`, "Укажи каждый селектор один раз");
    const value = match[2] ?? args[++index];
    if (typeof value !== "string" || !value || value.startsWith("--")) fail("selector-conflict", `У --${key} нет значения`, "Укажи явное значение селектора");
    selected[key] = value;
  }
  return selected;
}

function jsonCommand(run, args, options, code) {
  const result = run(args, options);
  if (result.notFound || result.error || result.status !== 0) fail(code, describeFailure(result), "Проверь закреплённый форк, выбранный store и его схему");
  let data;
  try { data = JSON.parse(result.stdout); } catch { fail(code, "Форк вернул неверный JSON", "Восстанови закреплённый форк OpenSpec"); }
  if (!object(data)) fail(code, "Форк вернул неподдерживаемую форму JSON", "Восстанови закреплённый форк OpenSpec");
  return data;
}

function checkedChange(value) {
  if (!identifier(value)) fail("selector-conflict", "Имя изменения не является допустимым идентификатором", "Укажи имя изменения без путей и обходов каталогов");
  return value;
}

// Existing directories predate the new-change slug grammar. Native status
// accepts a safe single segment (including Unicode and spaces) read-only.
function checkedExistingChange(value) {
  if (typeof value !== "string" || !value || value === "." || value === ".." || /[\\/\0:]/.test(value)) fail("selector-conflict", "Адрес существующего изменения не является одним сегментом каталога", "Укажи существующее изменение без путей и обходов каталогов");
  return value;
}

function commandPositionals(args) {
  const values = new Set(["--schema", "--store", "--store-path", "--change", "--description", "--goal", "--type", "--level"]);
  const result = [];
  let ended = false;
  for (let index = 0; index < args.length; index++) {
    const arg = args[index];
    if (ended) result.push(arg);
    else if (arg === "--") ended = true;
    else if (values.has(arg)) index++;
    else if (!arg.startsWith("-")) result.push(arg);
  }
  return result;
}

function addressedChange(journal, store) {
  if (!journal) return null;
  const file = path.resolve(store.sourceCwd, journal);
  const root = path.join(store.root, "openspec", "changes");
  if (!inside(root, file)) fail("selector-conflict", "Журнал не принадлежит выбранному store", "Укажи журнал выбранного store");
  const parts = path.relative(root, file).split(path.sep);
  const archived = parts[0] === "archive";
  const name = checkedExistingChange(parts[archived ? 1 : 0]);
  const changeDir = path.join(root, ...(archived ? ["archive", name] : [name]));
  if (parts.length < (archived ? 3 : 2) || !equalPath(changeDir, path.dirname(file)) || !inside(fs.realpathSync(store.root), fs.realpathSync(file))) fail("selector-conflict", "Адрес журнала выходит за каталог изменения", "Укажи штатный журнал изменения без перенаправления ссылками");
  return { name, dir: changeDir, archived };
}

/** Pinned new-change.ts / resolveSchemaForChange adapter: CLI has no read-only default-schema query. */
function configSchema(storeRoot) {
  const file = ["config.yaml", "config.yml"].map((name) => path.join(storeRoot, "openspec", name)).find(exists);
  if (!file) return "spec-driven";
  let config;
  try { config = parse(fs.readFileSync(file, "utf8")); } catch { fail("schema-source-conflict", "Planning config не является корректным YAML", "Исправь planning config без автоматического изменения store"); }
  if (!object(config) || (config.schema !== undefined && (typeof config.schema !== "string" || !config.schema))) fail("schema-source-conflict", "Planning config не задаёт корректную схему", "Исправь planning config либо выполни явную инициализацию");
  return config.schema ?? "spec-driven";
}

/** Archived journals cannot use active-only status; read pinned metadata/config without creating a change. */
function archivedSchema(address, storeRoot) {
  const metadataPath = path.join(address.dir, ".openspec.yaml");
  if (!exists(metadataPath)) return configSchema(storeRoot);
  if (!inside(fs.realpathSync(address.dir), fs.realpathSync(metadataPath))) fail("schema-source-conflict", "Metadata архива перенаправлено за каталог изменения", "Восстанови metadata выбранного архива");
  const metadata = parse(fs.readFileSync(metadataPath, "utf8"));
  if (!object(metadata) || !identifier(metadata.schema)) fail("schema-source-conflict", "Некорректное metadata архивного изменения", "Исправь metadata архива без изменения выбранной поставки");
  return metadata.schema;
}

function effectiveSchema(context, { tool, args, change, journal, run, options, selected }) {
  const address = addressedChange(journal, context.store);
  const native = tool === "openspec";
  let name = change;
  if (selected.change !== undefined) {
    if (name !== undefined && name !== selected.change) fail("selector-conflict", "Вызов адресует разные изменения", "Согласуй имя изменения и вложенный --change");
    name = selected.change;
  }
  if (address) {
    if (name !== undefined && name !== address.name) fail("selector-conflict", "Журнал и команда адресуют разные изменения", "Выбери одно адресуемое изменение");
    name = address.name;
  }
  const creating = native && args[0] === "new" && args[1] === "change";
  const positional = commandPositionals(args.slice(creating ? 2 : 1));
  if (creating && positional[0] !== undefined) checkedChange(positional[0]);
  if (!name && native && ["archive", "show", "validate"].includes(args[0]) && positional[0]) {
    const candidate = checkedExistingChange(positional[0]);
    if (args[0] === "archive" || exists(path.join(context.store.root, "openspec", "changes", candidate))) name = candidate;
  }
  if (!name && tool === "trace" && ["build", "report", "freeze", "check", "archive-gaps"].includes(args[0]) && args[1] && !args[1].startsWith("-")) name = checkedExistingChange(args[1]);
  if (!name && ["anchors", "sync-check"].includes(tool) && args[0] && !args[0].startsWith("-")) name = checkedExistingChange(args[0]);
  const override = selected.schema;
  if (override !== undefined && !identifier(override)) fail("schema-source-conflict", "Неподдерживаемое имя схемы --schema", "Укажи схему выбранной поставки");
  if (name && !creating) {
    checkedExistingChange(name);
    if (address?.archived) {
      const baseline = archivedSchema(address, context.store.root);
      if (override !== undefined && override !== baseline) fail("schema-source-conflict", "--schema меняет схему существующего архивного изменения", "Используй объявленную схему изменения");
      return baseline;
    }
    const directory = path.join(context.store.root, "openspec", "changes", name);
    if (exists(directory) && !inside(fs.realpathSync(context.store.root), fs.realpathSync(directory))) fail("selector-conflict", "Каталог изменения перенаправлен за выбранный store", "Используй изменение выбранного store без перенаправления ссылкой");
    const baseline = jsonCommand(run, ["status", "--change", name, "--json"], options, "schema-source-conflict");
    if (!identifier(baseline.schemaName) || !object(baseline.root) || !isFullyAbsolute(baseline.root.path) || !equalPath(baseline.root.path, context.store.root)) fail("schema-source-conflict", "Status не подтвердил схему выбранного изменения/store", "Проверь metadata и закреплённый форк");
    if (override !== undefined) {
      const explicit = jsonCommand(run, ["status", "--change", name, "--schema", override, "--json"], options, "schema-source-conflict");
      if (explicit.schemaName !== baseline.schemaName || override !== baseline.schemaName) fail("schema-source-conflict", "--schema меняет схему существующего изменения", "Используй объявленную схему изменения");
    }
    return baseline.schemaName;
  }
  return override ?? configSchema(context.store.root);
}

export function userSchemaDirectory(env = process.env) {
  const base = env.XDG_DATA_HOME || (process.platform === "win32" ? env.LOCALAPPDATA || path.join(env.USERPROFILE || os.homedir(), "AppData", "Local") : path.join(env.HOME || os.homedir(), ".local", "share"));
  if (!isFullyAbsolute(base)) fail("schema-source-conflict", "База пользовательской схемы должна быть абсолютной", "Задай абсолютный XDG_DATA_HOME либо системный пользовательский каталог");
  return path.join(base, "openspec", "schemas");
}

function schemaFiles(root) {
  if (!fs.lstatSync(root, { throwIfNoEntry: false })?.isDirectory()) fail("schema-source-conflict", "Ожидаемый каталог схемы отсутствует либо перенаправлен ссылкой", "Восстанови управляемую схему выбранной поставки");
  const files = new Map();
  const walk = (dir, prefix = "") => {
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
      if (entry.isSymbolicLink()) fail("schema-source-conflict", "Схема содержит перенаправленный ресурс", "Восстанови управляемую схему без посторонних ссылок");
      const rel = prefix ? `${prefix}/${entry.name}` : entry.name;
      if (entry.isDirectory()) { if (rel === "steps.md") fail("schema-source-conflict", "steps.md занят каталогом; это не отсутствие текста", "Восстанови файл текстов шагов выбранной поставки"); walk(path.join(dir, entry.name), rel); }
      else if (entry.isFile()) files.set(rel, digest(fs.readFileSync(path.join(dir, entry.name))));
      else fail("schema-source-conflict", "Схема содержит неподдерживаемый тип ресурса", "Восстанови управляемые файлы схемы");
    }
  };
  walk(root);
  return files;
}

function validateSchemaRemoval(removal, storeRoot, actualPath) {
  const proof = removal?.proof;
  const source = removal?.sourceContext;
  if (source?.scope === "local" && source.runtime?.legacy && !source.runtime.manifestPath) {
    let evidence;
    try { evidence = legacySourceEvidence(proof, source); }
    catch (error) { fail("migration-proof-invalid", error.message, "Legacy-файлы изменились после проверки; повтори preview"); }
    if (!evidence) fail("migration-ownership-unconfirmed", "Legacy-схема требует typed proof точной известной генерации", "Подготовь preview по поставленному inventory; неизвестные файлы сохраняются");
    if (!equalPath(evidence.storeRoot, storeRoot) || !equalPath(evidence.schemaRoot, actualPath) || !inside(fs.realpathSync(storeRoot), fs.realpathSync(actualPath))) fail("migration-proof-invalid", "Legacy proof относится к другому store или схеме", "Повтори preview выбранного store");
    const expected = evidence.files.filter((file) => file.source.startsWith("openspec/schemas/symphysis/"));
    for (const [relative, sha256] of schemaFiles(actualPath)) if (!expected.some((file) => file.source === `openspec/schemas/symphysis/${relative}` && file.sha256 === sha256 && path.relative(file.path, path.join(actualPath, relative)) === "")) fail("migration-proof-invalid", "Legacy-схема изменилась либо содержит неизвестные файлы", "Сохрани неизвестные файлы и составь новый preview");
    return;
  }
  if (!proof || source?.scope !== "local" || !source.runtime?.manifestPath || !isFullyAbsolute(proof.root) || !isFullyAbsolute(proof.manifestPath) || typeof proof.generation !== "string" || !Array.isArray(proof.files)) fail("migration-ownership-unconfirmed", "Проектная схема требует проверенного плана удаления собственных local-файлов", "Подготовь preview по действительному manifest local-поставки; неизвестные файлы сохраняются");
  if (!equalPath(proof.root, source.runtime.schemaRoot) || !equalPath(actualPath, proof.root) || !equalPath(proof.manifestPath, source.runtime.manifestPath) || proof.generation !== source.runtime.generation || !inside(fs.realpathSync(storeRoot), fs.realpathSync(proof.root))) fail("migration-proof-invalid", "Proof удаления относится к другой схеме, поставке или поколению", "Повтори preview выбранного store по текущему manifest");
  const local = readJson(proof.manifestPath);
  if (!object(local) || local.format !== 1 || local.scope !== "local" || local.generation !== proof.generation || !Array.isArray(local.files)) fail("migration-proof-invalid", "Manifest local-схемы изменился после preview", "Повтори preview по действительной local-поставке");
  const current = schemaFiles(proof.root);
  const registered = local.files.filter((entry) => typeof entry.source === "string" && entry.source.startsWith("openspec/schemas/symphysis/") && entry.projection !== true);
  if (proof.files.length > registered.length) fail("migration-proof-invalid", "План не подтверждает полный состав удаляемой проектной схемы", "Сохрани неизвестные файлы и разреши конфликты до миграции");
  const seen = new Set();
  for (const entry of registered) {
    const relative = entry.source.slice("openspec/schemas/symphysis/".length);
    const expected = path.join(proof.root, relative);
    if (!relative || path.isAbsolute(relative) || relative.split(/[\\/]/).some((part) => !part || part === "." || part === "..") || !isFullyAbsolute(entry.path) || path.relative(expected, entry.path) !== "" || (current.has(relative) && current.get(relative) !== entry.sha256)) fail("migration-proof-invalid", "Local-схема содержит изменённый или посторонний файл", "Повтори preview и сохрани изменения пользователя");
    const wanted = proof.files.filter((file) => isFullyAbsolute(file.path) && path.relative(file.path, entry.path) === "");
    if (seen.has(relative) || wanted.length > 1 || (current.has(relative) && wanted.length !== 1) || (wanted.length && wanted[0].sha256 !== entry.sha256) || (!current.has(relative) && exists(entry.path))) fail("migration-proof-invalid", "Proof удаления не совпадает с собственным файлом local-схемы", "Повтори preview выбранной поставки");
    seen.add(relative);
    if (!wanted.length) continue;
    try { assertInstallationSnapshot(entry.path, wanted[0].snapshot); }
    catch (error) { fail("migration-proof-invalid", error.message, "Файл схемы изменился после preview; повтори план без перезаписи пользователя"); }
  }
  if ([...current.keys()].some((relative) => !seen.has(relative)) || proof.files.some((file) => !registered.some((entry) => isFullyAbsolute(file.path) && path.relative(file.path, entry.path) === ""))) fail("migration-proof-invalid", "В проектной схеме или proof есть неизвестный файл", "Сохрани неизвестные файлы и повтори preview");
}

function verifySchema(context, manifest, name, run, options, env, { purpose, schemaRemoval } = {}) {
  if (!identifier(name) || name !== context.resources.schema.name) fail("schema-source-conflict", `Эффективная схема ${String(name)} не принадлежит выбранной поставке`, "Выбери схему поставки либо явно исправь planning config/metadata");
  const actual = jsonCommand(run, ["schema", "which", name, "--json"], options, "schema-source-conflict");
  const expected = context.scope === "global" ? path.join(userSchemaDirectory(env), name) : context.runtime.schemaRoot;
  const removalPreview = context.scope === "global" && purpose === "migration-preview" && actual.source === "project";
  if (removalPreview && actual.name === name && isFullyAbsolute(actual.path)) validateSchemaRemoval(schemaRemoval, context.store.root, actual.path);
  else if (actual.name !== name || actual.source !== (context.scope === "global" ? "user" : "project") || !isFullyAbsolute(actual.path) || path.relative(expected, actual.path) !== "" || !equalPath(expected, actual.path)) fail("schema-source-conflict", "Нативный источник схемы не совпадает с выбранной поставкой", "Сохрани конфликтующую схему и выполни явную настройку/миграцию");
  const schemaBase = context.scope === "global" ? context.runtime.root : context.store.root;
  if (!inside(fs.realpathSync(schemaBase), fs.realpathSync(context.runtime.schemaRoot))) fail("schema-source-conflict", "Каноническая схема перенаправлена за выбранную поставку", "Восстанови собственную схему без внешнего перенаправления");
  const canonical = schemaFiles(context.runtime.schemaRoot);
  const projected = schemaFiles(expected);
  const coreCanonical = new Map([...canonical].filter(([file]) => file !== "steps.md"));
  const coreProjected = new Map([...projected].filter(([file]) => file !== "steps.md"));
  if (coreCanonical.size !== coreProjected.size || [...coreCanonical].some(([file, hash]) => coreProjected.get(file) !== hash) || (canonical.has("steps.md") && projected.has("steps.md") && canonical.get("steps.md") !== projected.get("steps.md"))) fail("schema-source-conflict", "Пользовательская проекция схемы отличается от runtime", "Восстанови управляемую проекцию; чужие файлы автоматически не заменяются");
  if (manifest) {
    const prefix = `openspec/schemas/${name}/`;
    const entries = manifest.files.filter((entry) => entry.source.startsWith(prefix) && entry.projection !== true);
    const registered = new Map();
    for (const entry of entries) {
      const relative = entry.source.slice(prefix.length);
      if (!relative || path.isAbsolute(relative) || relative.split(/[\\/]/).some((part) => !part || part === "." || part === "..") || path.relative(path.join(context.runtime.schemaRoot, relative), entry.path) !== "") fail("schema-source-conflict", "Manifest указывает чужую цель схемы", "Восстанови manifest выбранной поставки");
      registered.set(relative, entry.sha256);
    }
    const presentRegistered = new Map([...registered].filter(([file]) => file !== "steps.md" || canonical.has(file)));
    if (presentRegistered.size !== canonical.size || [...canonical].some(([file, hash]) => registered.get(file) !== hash) || (projected.has("steps.md") && projected.get("steps.md") !== registered.get("steps.md"))) fail("schema-source-conflict", "Состав или байты схемы не подтверждены manifest", "Восстанови собственные ресурсы выбранной поставки");
    for (const entry of manifest.files.filter((entry) => entry.source.startsWith(prefix) && entry.projection === true)) {
      const relative = entry.source.slice(prefix.length);
      if (!relative || path.isAbsolute(relative) || relative.split(/[\\/]/).some((part) => !part || part === "." || part === "..") || path.relative(path.join(expected, relative), entry.path) !== "" || (!(relative === "steps.md" && !projected.has(relative)) && projected.get(relative) !== entry.sha256)) fail("schema-source-conflict", "Manifest проекции схемы не совпадает с её нативной целью и байтами", "Восстанови управляемую проекцию выбранной поставки");
    }
  }
}

/** Read-only compatibility preflight. It only updates context.compatibility and returns diagnostics. */
export function checkRuntimeCompatibility(context, { tool, args = [], change, journal, purpose = "execute", schemaRemoval, run = runOpenspec, env = process.env } = {}) {
  context.compatibility = { status: "unconfirmed", declarationPath: context.scope === "global" && isFullyAbsolute(context.store?.root) ? path.join(context.store.root, "openspec", "symphysis.json") : null };
  try {
    if (!context.store || !context.runtime || !context.resources?.schema || !["local", "global"].includes(context.scope)) fail("runtime-incompatible", "Поставка и store ещё не выбраны", "Сначала разреши действительную установленную поставку");
    const runtime = context.runtime;
    if (![context.store.root, context.store.sourceCwd, runtime.root, runtime.toolsRoot, runtime.docsRoot, runtime.schemaRoot, context.resources.schema.path].every((file) => isFullyAbsolute(file)) || (runtime.manifestPath !== null && !isFullyAbsolute(runtime.manifestPath))) fail("runtime-incompatible", "Контекст поставки содержит путь без однозначного абсолютного корня", "Повтори разрешение runtime с абсолютными путями");
    const supported = { bootstrapApi: BOOTSTRAP_API, runtimeApi: RUNTIME_API, schemaApi: SCHEMA_API };
    let manifest = null;
    if (runtime.manifestPath) {
      manifest = readJson(runtime.manifestPath);
      if (!object(manifest) || manifest.format !== 1 || manifest.scope !== context.scope || manifest.generation !== runtime.generation || !Array.isArray(manifest.files) || manifest.files.some((entry) => !isFullyAbsolute(entry?.path))) fail("runtime-incompatible", "Manifest и выбранное поколение поставки не согласованы", "Восстанови выбранную поставку явной установкой");
    }
    for (const [api, value] of Object.entries(supported)) if (runtime[api] !== value || (manifest && manifest[api] !== value)) fail("runtime-incompatible", `Неподдерживаемый ${api} выбранной поставки`, "Установи совместимые bootstrap и runtime; другой scope не выбирается");
    if (context.scope === "global" && !["initialize", "migration-preview"].includes(purpose)) {
      const declarationPath = context.compatibility.declarationPath;
      if (!exists(declarationPath)) fail("declaration-missing", "Store не объявляет совместимость с global-поставкой", "Выполни symphysis init либо явную миграцию выбранного store");
      let declaration;
      try { declaration = readJson(declarationPath); } catch { fail("declaration-incompatible", "Декларация store не является корректным UTF-8 JSON", "Исправь декларацию через явную инициализацию/миграцию"); }
      if (!object(declaration) || declaration.format !== 1 || declaration.runtimeApi !== runtime.runtimeApi || declaration.schemaApi !== runtime.schemaApi) fail("declaration-incompatible", "Декларация store несовместима с выбранным runtime", "Явно согласуй совместимость либо установи совместимую поставку");
    }
    const options = { cwd: context.store.root, env };
    const selected = selectors(args);
    if (selected.store !== undefined || selected["store-path"] !== undefined) {
      if (selected.store !== undefined && !identifier(selected.store)) fail("selector-conflict", "Некорректный вложенный store id", "Выбери один действительный store");
      if (selected.store !== undefined && selected["store-path"] !== undefined) fail("selector-conflict", "Вложенный вызов задаёт два селектора store", "Оставь один согласованный селектор");
      const flag = selected.store !== undefined ? "--store" : "--store-path";
      const value = selected.store ?? selected["store-path"];
      const late = jsonCommand(run, ["context", flag, value, "--json"], options, "selector-conflict");
      if (!object(late.root) || !isFullyAbsolute(late.root.path) || !equalPath(context.store.root, late.root.path)) fail("selector-conflict", "Вложенный селектор выбирает другой store", "Согласуй внешний и вложенный store до запуска команды");
    }
    const pin = forkPin().openspecPin;
    if (manifest?.openspecPin !== undefined && manifest.openspecPin !== pin) fail("runtime-incompatible", "Runtime и bootstrap требуют разные закреплённые форки", "Установи согласованную поставку и bootstrap");
    const version = run(["--version"], options);
    if (version.notFound || version.error || version.status !== 0 || String(version.stdout).trim() !== (manifest?.openspecPin ?? pin)) fail("fork-incompatible", "Фактическая версия OpenSpec не совпадает с pin выбранной поставки", "Установи закреплённый форк либо укажи его через SYMPHYSIS_OPENSPEC");
    const name = ["initialize", "migration-preview"].includes(purpose) ? context.resources.schema.name : effectiveSchema(context, { tool, args, change, journal, run, options, selected });
    verifySchema(context, manifest, name, run, options, env, { purpose, schemaRemoval });
    context.compatibility.status = "compatible";
    return [];
  } catch (error) {
    context.compatibility.status = error.code === "declaration-missing" ? "unconfirmed" : "incompatible";
    return [{ code: error.code && error.action ? error.code : "runtime-incompatible", message: error.message, action: error.action ?? "Проверь выбранную поставку, metadata/config и закреплённый форк; автоматического исправления нет" }];
  }
}
