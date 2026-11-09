import fs from "node:fs";
import path from "node:path";
import { createHash, randomUUID } from "node:crypto";
import { isFullyAbsolute } from "./paths.js";
import { BOOTSTRAP_API, RUNTIME_API, SCHEMA_API } from "./runtime-api.js";
import { predecessorAdoption, predecessorRemoval } from "./predecessor-adoption.js";

const plans = new WeakMap();
const object = (value) => value !== null && typeof value === "object" && !Array.isArray(value);
const identity = (stat) => ({ dev: String(stat.dev), ino: String(stat.ino) });
const sameIdentity = (a, b) => a.dev === b.dev && a.ino === b.ino;
export const installationHash = (bytes) => createHash("sha256").update(bytes).digest("hex");
export const installationKey = (file) => process.platform === "win32" ? path.resolve(file).toLowerCase() : path.resolve(file);

export class InstallationError extends Error {
  constructor(code, message) { super(message); this.name = "InstallationError"; this.code = code; this.exitCode = 2; }
}
const invalid = (message) => new InstallationError("installation-plan-invalid", message);
const changed = () => new InstallationError("installation-state-changed", "Файлы, реальные пути или manifest изменились после просмотра; составь новый план");

/** Validate every existing component without following Windows junctions or symlinks. */
export function installationPath(value, { directory = false } = {}) {
  if (!isFullyAbsolute(value)) throw invalid("Установка требует полного абсолютного пути");
  const target = path.resolve(value);
  let current = path.parse(target).root;
  const parts = target.slice(current.length).split(path.sep).filter(Boolean);
  for (let index = 0; index < parts.length; index++) {
    current = path.join(current, parts[index]);
    const stat = fs.lstatSync(current, { throwIfNoEntry: false });
    if (!stat) break;
    if (stat.isSymbolicLink() || ((index < parts.length - 1 || directory) && !stat.isDirectory())) throw invalid("Цель установки проходит через reparse/ссылку либо неподходящий тип файла");
  }
  return target;
}

export function installationSnapshot(file) {
  file = installationPath(file);
  const ancestors = [];
  let parent = path.dirname(file);
  while (parent !== path.dirname(parent)) {
    const stat = fs.lstatSync(parent, { throwIfNoEntry: false });
    if (stat) ancestors.push({ path: parent, ...identity(stat) });
    parent = path.dirname(parent);
  }
  const stat = fs.lstatSync(file, { throwIfNoEntry: false });
  if (!stat) return { hash: null, identity: null, ancestors };
  if (!stat.isFile()) throw invalid("Цель файла установки занята другим типом объекта");
  const fd = fs.openSync(file, fs.constants.O_RDONLY | (fs.constants.O_NOFOLLOW ?? 0));
  try {
    if (!sameIdentity(identity(fs.fstatSync(fd)), identity(stat))) throw changed();
    const bytes = fs.readFileSync(fd);
    if (!sameIdentity(identity(fs.fstatSync(fd)), identity(fs.lstatSync(file)))) throw changed();
    return { hash: installationHash(bytes), identity: identity(stat), ancestors };
  } finally { fs.closeSync(fd); }
}

export function assertInstallationSnapshot(file, expected) {
  const actual = installationSnapshot(file);
  if (actual.hash !== expected.hash || Boolean(actual.identity) !== Boolean(expected.identity) || (actual.identity && !sameIdentity(actual.identity, expected.identity))) throw changed();
  for (const ancestor of expected.ancestors) {
    installationPath(ancestor.path, { directory: true });
    const stat = fs.lstatSync(ancestor.path, { throwIfNoEntry: false });
    if (!stat || !sameIdentity(identity(stat), ancestor)) throw changed();
  }
}

function sourceName(source) {
  if (typeof source !== "string" || !source || /[\\:\0]/.test(source) || source.split("/").some((part) => !part || part === "." || part === "..")) throw invalid("Неверный идентификатор ресурса payload");
  if (source === "tools/journal-roots.json" || source.endsWith("/symphysis.yaml") || source.startsWith("viewer/")) throw invalid("Личные файлы не входят в заменяемые ресурсы");
  if (source.startsWith("skills/") && !/^skills\/[a-z0-9]+(?:-[a-z0-9]+)*\/.+/.test(source)) throw invalid("Ресурс skill должен находиться в каталоге именованного скилла");
  return source;
}

export function normalizeInstallationRequest(input) {
  if (!object(input) || !["local", "global"].includes(input.scope)) throw invalid("Нужен явный local/global scope");
  const root = installationPath(input.root, { directory: true });
  if (root === path.parse(root).root) throw invalid("Корень диска не является местом установки");
  const runtimeRoot = installationPath(input.runtimeRoot, { directory: true });
  const storeRoot = input.scope === "local" ? installationPath(input.storeRoot, { directory: true }) : null;
  if (input.scope === "global" && input.storeRoot != null) throw invalid("Global install не выбирает store");
  if (installationKey(runtimeRoot) !== installationKey(input.scope === "global" ? path.join(root, "runtime") : root) || (storeRoot && installationKey(root) !== installationKey(path.join(storeRoot, ".symphysis")))) throw invalid("Runtime и management root не соответствуют выбранному scope");
  if (typeof input.sourceVersion !== "string" || !input.sourceVersion || typeof input.openspecPin !== "string" || !input.openspecPin) throw invalid("Нужны версия источника и pin форка");
  const schemaDirectory = input.scope === "global" ? installationPath(input.schemaDirectory, { directory: true }) : path.join(storeRoot, "openspec", "schemas");
  if (input.clients !== undefined && !Array.isArray(input.clients)) throw invalid("Нужен массив клиентских targets");
  const clients = (input.clients ?? []).map((client) => {
    if (!object(client) || typeof client.id !== "string" || !/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(client.id)) throw invalid("Неверный client id");
    const result = { id: client.id };
    for (const kind of ["skills", "agents", "commands"]) {
      const multiple = client[`${kind}Roots`];
      if (multiple !== undefined && !Array.isArray(multiple)) throw invalid("Client roots должны быть массивом");
      const roots = [...(multiple ?? []), ...(client[`${kind}Root`] != null ? [client[`${kind}Root`]] : [])].map((root) => installationPath(root, { directory: true }));
      const unique = [...new Map(roots.map((root) => [installationKey(root), root])).values()];
      if (unique.length) result[`${kind}Roots`] = unique;
      if (unique.length === 1) result[`${kind}Root`] = unique[0];
    }
    return result;
  });
  if (new Set(clients.map((client) => client.id)).size !== clients.length) throw invalid("Client id указан повторно");
  let bootstrap;
  if (input.bootstrap !== undefined) {
    if (!object(input.bootstrap) || !Array.isArray(input.bootstrap.args) || !input.bootstrap.args.length || input.bootstrap.args.some((arg) => typeof arg !== "string" || arg.includes("\0"))) throw invalid("Неверная привязка bootstrap");
    bootstrap = { command: installationPath(input.bootstrap.command), args: [...input.bootstrap.args] };
    installationPath(bootstrap.args[0]);
  }
  if (input.scope === "global" && !bootstrap) throw invalid("Global runtime требует явную привязку bootstrap");
  return { scope: input.scope, root, runtimeRoot, storeRoot, schemaDirectory, sourceVersion: input.sourceVersion, openspecPin: input.openspecPin, clients, ...(bootstrap ? { bootstrap } : {}) };
}

/** The target must be reconstructable from the source, scope and explicit client/schema roots. */
export function installationTarget(request, file) {
  const source = sourceName(file.source);
  if (source === ".symphysis-runtime.json") {
    if (request.scope !== "global" || file.projection) throw invalid("Marker разрешён только canonical global runtime");
    return path.join(request.runtimeRoot, source);
  }
  if (source === "openspec/config.symphysis.yaml") {
    if (request.scope !== "global" || file.projection) throw invalid("Planning config не является собственным файлом local payload");
    return path.join(request.runtimeRoot, source);
  }
  if (source.startsWith("openspec/schemas/symphysis/")) {
    const suffix = source.slice("openspec/schemas/symphysis/".length);
    return request.scope === "local" || file.projection === true ? path.join(request.schemaDirectory, "symphysis", suffix) : path.join(request.runtimeRoot, source);
  }
  const carrier = /^(skills|agents|commands)\/(.+)$/.exec(source);
  if (carrier && (request.scope === "local" || file.projection === true)) {
    const candidates = request.clients.filter((client) => !file.clientId || client.id === file.clientId).flatMap((client) => client[`${carrier[1]}Roots`] ?? (client[`${carrier[1]}Root`] ? [client[`${carrier[1]}Root`]] : []));
    const selected = candidates.find((root) => installationKey(path.join(root, carrier[2])) === installationKey(file.path));
    if (!selected) throw invalid("Клиентский ресурс не соответствует явно выбранному target");
    return path.join(selected, carrier[2]);
  }
  if (file.projection === true) throw invalid("Неизвестная проекция payload");
  if (!/^(tools|docs|skills|agents|commands)\/.+/.test(source)) throw invalid("Неизвестная область ресурсов payload");
  return path.join(request.runtimeRoot, source);
}

export function nonOwnedInstallationTarget(request, operation) {
  if (!request.storeRoot) throw invalid("Операция с проектными данными требует выбранного local store");
  const allowed = {
    "planning-config": ["openspec/config.yaml", "openspec/config.yml"],
    "store-declaration": ["openspec/symphysis.json"],
    "initial-settings": ["symphysis.yaml"],
    "initial-roots": [".symphysis/tools/journal-roots.json"],
    "gitignore-merge": [".gitignore", ".git/info/exclude"],
  }[operation.kind];
  const target = allowed?.map((relative) => path.join(request.storeRoot, relative)).find((file) => installationKey(file) === installationKey(operation.path));
  if (!target) throw invalid("Неизвестная типизированная операция с проектными данными");
  return target;
}

function registryFile(request, item) {
  if (!object(item) || typeof item.purpose !== "string" || !item.purpose || !/^[a-f0-9]{64}$/.test(item.sha256 ?? "")) throw invalid("Некорректная запись собственного файла manifest");
  const target = installationPath(item.path);
  if (installationKey(installationTarget(request, item)) !== installationKey(target)) throw invalid("Manifest/план указывает постороннюю цель ресурса");
  if (request.storeRoot) {
    const personal = ["symphysis.yaml", ".gitignore", ".git/info/exclude", ".symphysis/tools/journal-roots.json", "openspec/config.yaml", "openspec/config.yml", "openspec/symphysis.json"];
    const key = installationKey(target);
    const protectedDirectories = [".symphysis/viewer", "openspec/changes", "openspec/specs"];
    if (personal.some((relative) => installationKey(path.join(request.storeRoot, relative)) === key) || protectedDirectories.some((relative) => {
      const inside = path.relative(path.join(request.storeRoot, relative), target);
      return inside === "" || (inside !== ".." && !inside.startsWith(`..${path.sep}`) && !path.isAbsolute(inside));
    })) throw invalid("Проектные данные не становятся собственными файлами через alias клиентского target");
  }
  return target;
}

export function installationOwnedTarget(request, file) { return registryFile(request, file); }

export function readInstallationManifest(file, request) {
  let value;
  try { value = JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(fs.readFileSync(file))); } catch { throw invalid("Manifest установки не прочитан как UTF-8 JSON"); }
  if (!object(value) || value.format !== 1 || value.scope !== request.scope || typeof value.generation !== "string" || !value.generation || !Array.isArray(value.files) || !Array.isArray(value.clients)) throw invalid("Неподдерживаемый manifest установки");
  const previous = normalizeInstallationRequest({ ...request, ...value, root: request.root, runtimeRoot: request.runtimeRoot, storeRoot: request.storeRoot, schemaDirectory: value.schemaDirectory ?? request.schemaDirectory });
  const paths = new Set();
  for (const entry of value.files) {
    const key = installationKey(registryFile(previous, entry));
    if (paths.has(key)) throw invalid("Manifest повторяет собственную цель");
    paths.add(key);
  }
  return value;
}

function conflict(path, code, message) { return { path, code, message }; }
const metadata = (request, generation, files) => ({ format: 1, scope: request.scope, generation, sourceVersion: request.sourceVersion,
  bootstrapApi: BOOTSTRAP_API, runtimeApi: RUNTIME_API, schemaApi: SCHEMA_API, openspecPin: request.openspecPin,
  runtimeRoot: request.runtimeRoot, storeRoot: request.storeRoot, schemaDirectory: request.schemaDirectory,
  files, clients: request.clients, ...(request.bootstrap ? { bootstrap: request.bootstrap } : {}) });

/** Preview is read-only. Only this opaque plan object may subsequently be applied. */
export function createInstallationPlan(input) {
  const request = normalizeInstallationRequest(input);
  if (request.bootstrap && (!fs.statSync(request.bootstrap.command, { throwIfNoEntry: false })?.isFile() || !fs.statSync(request.bootstrap.args[0], { throwIfNoEntry: false })?.isFile())) throw invalid("Привязка bootstrap указывает недоступный исполняемый файл или entrypoint");
  if (!Array.isArray(input.files)) throw invalid("Нужен полный состав файлов новой поставки");
  const id = randomUUID();
  const manifestPath = path.join(request.root, "install-manifest.json");
  const manifestBefore = installationSnapshot(manifestPath);
  const previous = manifestBefore.hash === null ? null : readInstallationManifest(manifestPath, request);
  const previousRequest = previous ? normalizeInstallationRequest({ ...request, ...previous, root: request.root, runtimeRoot: request.runtimeRoot, storeRoot: request.storeRoot, schemaDirectory: previous.schemaDirectory ?? request.schemaDirectory }) : null;
  const oldFiles = new Map((previous?.files ?? []).map((entry) => [installationKey(entry.path), entry]));
  const desired = input.files.map((file) => {
    if (!object(file) || !Buffer.isBuffer(file.bytes)) throw invalid("Payload должен содержать явные проверенные Buffer bytes");
    sourceName(file.source);
    return { ...file, bytes: Buffer.from(file.bytes) };
  });
  if (request.scope === "global") {
    const bytes = Buffer.from('{"format":1,"scope":"global"}\n');
    const marker = desired.find((file) => file.source === ".symphysis-runtime.json");
    if (marker && !marker.bytes.equals(bytes)) throw invalid("Байты global marker не соответствуют формату");
    if (!marker) desired.push({ path: path.join(request.runtimeRoot, ".symphysis-runtime.json"), source: ".symphysis-runtime.json", purpose: "metadata", bytes });
    const schemas = new Map(desired.filter((file) => file.projection !== true && file.source.startsWith("openspec/schemas/symphysis/")).map((file) => [file.source, installationHash(file.bytes)]));
    for (const file of desired) if (file.projection === true && file.source.startsWith("openspec/schemas/symphysis/") && schemas.get(file.source) !== installationHash(file.bytes)) throw invalid("Проекция схемы не совпадает с canonical payload того же поколения");
  }
  const operations = [];
  const files = [];
  const conflicts = [];
  const selected = new Set();
  for (const file of desired) {
    const sha256 = installationHash(file.bytes);
    const target = registryFile(request, { ...file, sha256 });
    const key = installationKey(target);
    if (selected.has(key)) throw invalid("Две операции установки адресуют один файл");
    selected.add(key);
    const before = installationSnapshot(target);
    const old = oldFiles.get(key);
    const action = before.hash === sha256 ? "unchanged" : before.hash === null ? "create" : "replace";
    if (before.hash !== null && before.hash !== sha256 && (!old || old.sha256 !== before.hash) && !(!old && predecessorAdoption(input.adoptionProof, request, file, before))) conflicts.push(conflict(target, old ? "owned-file-modified" : "foreign-file", "Изменённый или чужой файл сохранён; force не отменяет ownership"));
    files.push({ path: target, source: file.source, purpose: file.purpose, sha256, ...(file.projection === true ? { projection: true } : {}), ...(file.clientId ? { clientId: file.clientId } : {}) });
    operations.push({ path: target, source: file.source, purpose: file.purpose, ...(file.projection === true ? { projection: true } : {}), ...(file.clientId ? { clientId: file.clientId } : {}), action, before, afterHash: sha256, bytes: file.bytes, owned: true });
  }
  const removed = new Set();
  for (const requested of input.removeFiles ?? []) {
    const target = installationPath(requested);
    const key = installationKey(target);
    const before = installationSnapshot(target);
    const old = oldFiles.get(key) ?? predecessorRemoval(input.adoptionProof, request, target, before);
    if (!old || selected.has(key) || removed.has(key)) throw invalid("Удаляется неизвестный/повторный либо устанавливаемый файл");
    removed.add(key);
    if (before.hash !== null && before.hash !== old.sha256) conflicts.push(conflict(target, "owned-file-modified", "Удаление сохраняет изменённый собственный файл"));
    operations.push({ ...old, path: target, action: before.hash === null ? "unchanged" : "remove", before, afterHash: null, bytes: null, owned: true, ...(!oldFiles.has(key) ? { predecessor: true } : {}) });
  }
  for (const [key, old] of oldFiles) if (!selected.has(key) && !removed.has(key)) conflicts.push(conflict(old.path, "owned-target-omitted", "Нужен полный состав ранее управляемых ресурсов либо явное удаление"));
  for (const operation of input.nonOwned ?? []) {
    if (!object(operation) || !Buffer.isBuffer(operation.bytes)) throw invalid("Типизированная операция требует явные Buffer bytes");
    const target = installationPath(nonOwnedInstallationTarget(request, operation));
    const key = installationKey(target);
    if (selected.has(key) || removed.has(key)) throw invalid("Проектные данные пересекаются с ресурсами поставки");
    selected.add(key);
    const before = installationSnapshot(target);
    if (operation.beforeHash !== before.hash) conflicts.push(conflict(target, "config-state-changed", "Исходные байты проектного файла изменились после подготовки merge"));
    let bytes = Buffer.from(operation.bytes);
    if (operation.kind.startsWith("initial-") && before.hash !== null) bytes = fs.readFileSync(target);
    const afterHash = installationHash(bytes);
    operations.push({ path: target, kind: operation.kind, action: before.hash === afterHash ? "unchanged" : before.hash === null ? "create" : "replace", before, afterHash, bytes, owned: false });
  }
  const allTargets = [...operations.map((operation) => operation.path), manifestPath].sort();
  for (let index = 0; index < allTargets.length; index++) for (let other = index + 1; other < allTargets.length; other++) {
    const relative = path.relative(allTargets[index], allTargets[other]);
    if (relative === "" || (relative !== ".." && !relative.startsWith(`..${path.sep}`) && !path.isAbsolute(relative))) throw invalid("Цели файлов установки вложены друг в друга");
  }
  let generation = randomUUID();
  let manifest = metadata(request, generation, files);
  if (previous && operations.every((operation) => operation.action === "unchanged") && JSON.stringify(metadata(request, previous.generation, files)) === JSON.stringify(previous)) {
    generation = previous.generation;
    manifest = previous;
  }
  const manifestBytes = Buffer.from(`${JSON.stringify(manifest, null, 2)}\n`);
  const manifestHash = installationHash(manifestBytes);
  operations.push({ path: manifestPath, kind: "manifest", action: manifestBefore.hash === manifestHash ? "unchanged" : manifestBefore.hash === null ? "create" : "replace", before: manifestBefore, afterHash: manifestHash, bytes: manifestBytes, owned: false });
  const plan = Object.freeze({ format: 1, id, scope: request.scope, root: request.root, generation, manifestPath,
    files: Object.freeze(operations.map(({ path, source, kind, action, before, afterHash }) => Object.freeze({ path, ...(source ? { source } : { kind }), action, beforeHash: before.hash, afterHash }))),
    conflicts: Object.freeze(conflicts.map(Object.freeze)), ready: conflicts.length === 0 });
  plans.set(plan, { id, request, previousRequest, manifest, manifestPath, operations, manifestBefore, previous });
  return plan;
}

/** Internal transaction boundary: serialized or reconstructed lookalikes are not execution authority. */
export function prepareInstallationPlan(plan) {
  const data = plans.get(plan);
  if (!data) throw invalid("Нужен исходный проверенный план; JSON не является разрешением записи");
  if (!plan.ready) throw new InstallationError("installation-conflict", plan.conflicts.map((item) => `${item.path}: ${item.message}`).join("\n"));
  for (const operation of data.operations) assertInstallationSnapshot(operation.path, operation.before);
  return data;
}
