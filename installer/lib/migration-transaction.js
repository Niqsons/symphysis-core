import fs from "node:fs";
import path from "node:path";
import { randomBytes, randomUUID } from "node:crypto";
import { fileURLToPath } from "node:url";
import { prepareMigrationPlan } from "./migration-plan.js";
import { resolvePlanningContext } from "./runtime-resolver.js";
import { acquireReader, acquireWriter, managementRoot } from "./runtime-leases.js";
import { InstallationError, installationPath, installationKey, installationHash, installationSnapshot, assertInstallationSnapshot,
  normalizeInstallationRequest, installationOwnedTarget, nonOwnedInstallationTarget } from "./installation-plan.js";
import { _transactionFileOps as files } from "./installation-transaction.js";
import { getLegacyInventory } from "./legacy-inventory.js";
import { legacyCarrierHashes } from "./predecessor-adoption.js";

const failure = (message) => new InstallationError("migration-recovery-required", message);
const busy = () => new InstallationError("installation-busy", "Владелец миграции жив или не подтверждён; чужие записи сохранены");
const exists = (file) => fs.lstatSync(file, { throwIfNoEntry: false }) !== undefined;
const key = installationKey;
const identity = (stat) => ({ dev: String(stat.dev), ino: String(stat.ino) });
const sameIdentity = (actual, wanted) => Boolean(actual && wanted && String(actual.dev) === wanted.dev && String(actual.ino) === wanted.ino);
const uuid = (value) => typeof value === "string" && /^[a-f0-9-]{36}$/.test(value);
const hash = (value) => typeof value === "string" && /^[a-f0-9]{64}$/.test(value);
const emptyHash = installationHash(Buffer.alloc(0));
const ownerProcess = Object.freeze({ pid: process.pid, startedAt: Math.floor(Date.now() - process.uptime() * 1000), instance: randomUUID() });
const pendingPath = (root) => path.join(root, ".migration-transaction.json");
const claimPath = (root) => path.join(root, ".migration-recovery.json");
const receiptPath = (store) => path.join(store, ".symphysis", "migration.json");
const receiptBytes = (from, to) => Buffer.from(`${JSON.stringify({ format: 1, from, to, runtimeApi: 1, schemaApi: 1 })}\n`);
const object = (value) => value && typeof value === "object" && !Array.isArray(value);
let knownNative;

function owner(value) {
  return value && Number.isSafeInteger(value.pid) && value.pid > 0 && Number.isSafeInteger(value.startedAt) && value.startedAt > 0 && uuid(value.id) && uuid(value.instance) && hash(value.token) && typeof value.generation === "string" && value.generation;
}

function manifestDefinition(selected, scope, store = null) {
  if (!selected?.value || !selected.request) throw failure("Нет типизированного manifest поколения миграции");
  const request = normalizeInstallationRequest(selected.request);
  const manifest = selected.value;
  if (request.scope !== scope || (store && key(request.storeRoot) !== key(store)) || manifest.format !== 1 || manifest.scope !== scope || typeof manifest.generation !== "string" || !manifest.generation || !Array.isArray(manifest.files) || !Array.isArray(manifest.clients) || ["bootstrapApi", "runtimeApi", "schemaApi"].some((api) => manifest[api] !== 1)) throw failure("Manifest миграции не подтверждает scope/API/поколение");
  const normalized = normalizeInstallationRequest({ ...manifest, root: request.root });
  if (JSON.stringify(normalized) !== JSON.stringify(request)) throw failure("Manifest и типизированные targets миграции не совпали");
  const seen = new Set();
  for (const entry of manifest.files) {
    const file = installationOwnedTarget(request, entry);
    if (seen.has(key(file))) throw failure("Manifest миграции повторяет собственную цель");
    seen.add(key(file));
  }
  return request;
}

function globalDefinition(record) {
  const selected = record.global;
  files.validateSavedRead(selected, selected?.value);
  const request = manifestDefinition(selected, "global");
  const manifestFile = path.join(request.root, "install-manifest.json");
  if (key(selected.file) !== key(manifestFile) || !Array.isArray(selected.observed) || selected.observed.length !== selected.value.files.length) throw failure("Неполное подтверждение неизменяемой global-поставки миграции");
  for (const entry of selected.value.files) {
    const observations = selected.observed.filter((item) => key(item.path) === key(entry.path));
    if (observations.length !== 1 || (observations[0].snapshot?.hash !== entry.sha256 && !(entry.source === "openspec/schemas/symphysis/steps.md" && observations[0].snapshot?.hash === null))) throw failure("Global snapshot не совпадает с реестром поставки");
  }
  const reader = record.reader;
  files.validateSavedRead(reader, reader?.value);
  const descriptor = reader?.descriptor;
  if (!owner(descriptor) || !owner(record.owner) || reader.value.format !== 1 || reader.value.kind !== "reader" || descriptor.generation !== selected.value.generation || key(reader.managementRoot) !== key(request.root) || key(descriptor.file) !== key(path.join(request.root, ".leases", `${descriptor.id}.json`))) throw failure("Миграция не подтверждает собственный global reader");
  for (const field of ["id", "token", "pid", "startedAt", "instance", "generation"]) if (reader.value[field] !== descriptor[field]) throw failure("Global reader proof изменён");
  for (const field of ["pid", "startedAt", "instance", "generation"]) if (descriptor[field] !== record.owner[field]) throw failure("Global reader и store writer принадлежат разным процессам");
  return request;
}

function checkGlobal(record, { requireReader = true } = {}) {
  globalDefinition(record);
  const file = record.reader.descriptor.file;
  if (!exists(file)) { if (requireReader) throw failure("Собственный global reader исчез до подтверждённого cleanup"); return; }
  assertInstallationSnapshot(file, record.reader.snapshot);
  assertInstallationSnapshot(record.global.file, record.global.snapshot);
  for (const entry of record.global.observed) assertInstallationSnapshot(entry.path, entry.snapshot);
}

function legacyDefinition(source, store) {
  const evidence = source.evidence;
  if (!evidence || key(evidence.storeRoot) !== key(store) || ![store, path.join(store, ".symphysis")].some((root) => key(root) === key(evidence.root)) || key(evidence.schemaRoot) !== key(path.join(store, "openspec", "schemas", "symphysis")) || !Array.isArray(evidence.files) || !Array.isArray(evidence.clients)) throw failure("Неподдерживаемая типизированная legacy-поставка миграции");
  const generation = getLegacyInventory().generations.find((entry) => entry.id === evidence.generation);
  if (!generation) throw failure("Legacy-генерация не входит в поставленный inventory");
  const request = normalizeInstallationRequest({ scope: "local", root: path.join(store, ".symphysis"), runtimeRoot: path.join(store, ".symphysis"), storeRoot: store, sourceVersion: evidence.generation, openspecPin: "known-legacy", clients: evidence.clients });
  knownNative ??= legacyCarrierHashes(JSON.parse(fs.readFileSync(fileURLToPath(new URL("../payload/docs/workflow-carriers.json", import.meta.url)), "utf8")));
  const critical = new Set(["tools/journal.py", "tools/journal_cli.py", "openspec/schemas/symphysis/schema.yaml"]);
  const seen = new Set();
  for (const entry of evidence.files) {
    const target = /^(?:tools|docs)\//.test(entry.source) ? path.join(evidence.root, entry.source) : installationOwnedTarget(request, entry);
    if (key(target) !== key(entry.path) || seen.has(key(entry.path)) || entry.snapshot?.hash !== entry.sha256) throw failure("Legacy-ресурс указывает неподтверждённую цель");
    const accepted = entry.purpose === "workflow" ? knownNative.get(`${entry.clientId}/${entry.source}`)?.has(entry.sha256) : generation.files.some((file) => file.source === entry.source && file.sha256.includes(entry.sha256));
    if (!accepted) throw failure("Legacy-ресурс не совпадает с точным известным предшественником");
    critical.delete(entry.source); seen.add(key(entry.path));
  }
  if (critical.size) throw failure("Legacy-поставка не содержит критического общего поколения");
  return evidence.files;
}

function sourceDefinition(record) {
  if (record.source.legacy) {
    if (record.from !== "local" || record.to !== "global") throw failure("Legacy source разрешён только для local→global");
    return legacyDefinition(record.source, record.store);
  }
  files.validateSavedRead(record.source, record.source.value);
  const request = manifestDefinition(record.source, record.from, record.from === "local" ? record.store : null);
  if (key(record.source.file) !== key(path.join(request.root, "install-manifest.json"))) throw failure("Исходный manifest миграции указывает постороннюю цель");
  return record.source.value.files;
}

function targetFor(record, operation, definitions) {
  const file = installationPath(operation.path);
  if (operation.kind === "migration-receipt") return receiptPath(record.store);
  if (operation.kind === "source-manifest") {
    if (record.to !== "global" || record.source.legacy || operation.action !== "remove") throw failure("Удаление manifest не относится к исходной local-поставке");
    if (operation.before.hash !== record.source.snapshot.hash || !sameIdentity(operation.before.identity, record.source.snapshot.identity)) throw failure("Удаление исходного manifest не совпадает с полным snapshot");
    return record.source.file;
  }
  if (record.to === "local") {
    const request = definitions.localRequest;
    if (operation.kind === "manifest") return path.join(request.root, "install-manifest.json");
    if (operation.owned) {
      if (!record.target.value.files.some((entry) => key(entry.path) === key(file) && entry.source === operation.source && entry.purpose === operation.purpose && entry.sha256 === operation.afterHash && (entry.clientId ?? null) === (operation.clientId ?? null))) throw failure("Новый local-ресурс не принадлежит финальному manifest");
      return installationOwnedTarget(request, { ...operation, sha256: operation.afterHash });
    }
    return nonOwnedInstallationTarget(request, operation);
  }
  if (operation.owned) {
    const original = definitions.sourceFiles.find((entry) => key(entry.path) === key(file) && entry.source === operation.source && entry.purpose === operation.purpose && (entry.clientId ?? null) === (operation.clientId ?? null));
    if (!original || operation.action !== "remove" || operation.before.hash !== original.sha256) throw failure("Удаление не подтверждено реестром исходной local-поставки");
    return original.path;
  }
  return nonOwnedInstallationTarget({ storeRoot: record.store }, operation);
}

function validateRecord(record, store, writer) {
  if (!record || record.format !== 1 || record.kind !== "migration" || !uuid(record.id) || !["local", "global"].includes(record.from) || !["local", "global"].includes(record.to) || record.from === record.to || key(installationPath(record.store, { directory: true })) !== key(store) || !["staging", "publishing", "committed"].includes(record.phase) || !Array.isArray(record.operations) || !record.operations.length || !Array.isArray(record.unchanged) || !Array.isArray(record.sourceObserved) || !Array.isArray(record.createdDirectories) || !owner(record.owner) || !owner(writer) || writer.format !== 1 || writer.kind !== "writer" || key(record.owner.file) !== key(path.join(store, ".symphysis", ".install-lock"))) throw failure("Неподдерживаемая запись миграции или store writer");
  for (const field of ["id", "token", "pid", "startedAt", "instance", "generation"]) if (record.owner[field] !== writer[field]) throw failure("Writer и migration record имеют разных владельцев");
  globalDefinition(record);
  const definitions = { sourceFiles: sourceDefinition(record), localRequest: record.to === "local" ? manifestDefinition(record.target, "local", store) : null };
  if (record.from === "global" && (key(record.source.file) !== key(record.global.file) || record.source.snapshot.hash !== record.global.snapshot.hash)) throw failure("Source global и удерживаемый reader относятся к разным поставкам");
  const seen = new Set();
  let receipts = 0, manifests = 0, retired = 0;
  for (const [index, operation] of record.operations.entries()) {
    const target = targetFor(record, operation, definitions);
    if (key(target) !== key(operation.path) || seen.has(key(target)) || !["create", "replace", "remove"].includes(operation.action) || !operation.before || !Array.isArray(operation.before.ancestors) || !(operation.before.hash === null || hash(operation.before.hash)) || !(operation.afterHash === null || hash(operation.afterHash)) || (operation.before.hash !== null && !operation.before.identity) || (operation.action === "remove") !== (operation.afterHash === null)) throw failure("Миграция содержит постороннюю/повторную цель либо неподтверждённые хеши");
    seen.add(key(target));
    if (operation.stage !== (operation.afterHash === null ? null : path.join(path.dirname(target), `.symphysis-migrate-${record.id}-${index}.stage`)) || operation.backup !== (operation.before.hash === null ? null : path.join(path.dirname(target), `.symphysis-migrate-${record.id}-${index}.backup`))) throw failure("Stage/backup миграции не выводятся из собственной цели");
    if (operation.stage) installationPath(operation.stage); if (operation.backup) installationPath(operation.backup);
    if (operation.kind === "migration-receipt") { receipts++; if (index !== record.operations.length - 1 || operation.afterHash !== installationHash(receiptBytes(record.from, record.to))) throw failure("Нет последней подтверждённой квитанции миграции"); }
    if (operation.kind === "manifest") { manifests++; if (record.to !== "local" || index !== record.operations.length - 2 || operation.afterHash !== installationHash(Buffer.from(`${JSON.stringify(record.target.value, null, 2)}\n`))) throw failure("Публикация local manifest не подтверждена"); }
    if (operation.kind === "source-manifest") { retired++; if (index !== record.operations.length - 2) throw failure("Исходный manifest не является последним удалением перед receipt"); }
    if (operation.kind?.startsWith("initial-") && operation.before.hash !== null) throw failure("Миграция не заменяет личные настройки/карту");
    if (operation.action === "create" && operation.before.hash !== null || operation.action === "replace" && operation.before.hash === null) throw failure("Действие миграции не соответствует исходному файлу");
  }
  if (receipts !== 1 || manifests !== (record.to === "local" ? 1 : 0) || retired !== (record.to === "global" && !record.source.legacy ? 1 : 0)) throw failure("Неполный финальный набор manifest/receipt миграции");
  for (const operation of record.unchanged) {
    let target;
    if (record.to === "global" && operation.owned) target = definitions.sourceFiles.find((entry) => key(entry.path) === key(operation.path) && entry.source === operation.source && entry.purpose === operation.purpose && (entry.clientId ?? null) === (operation.clientId ?? null))?.path;
    else target = targetFor(record, operation, definitions);
    if (!target || seen.has(key(target)) || operation.action !== "unchanged" || !operation.before || !Array.isArray(operation.before.ancestors) || operation.afterHash !== operation.before.hash || !(operation.before.hash === null || hash(operation.before.hash)) || (record.to === "global" && operation.owned && operation.before.hash !== null)) throw failure("Неизменяемые цели миграции не подтверждены");
    seen.add(key(target));
  }
  if (record.sourceObserved.length !== definitions.sourceFiles.length) throw failure("Нет полного исходного snapshot реестра миграции");
  for (const entry of definitions.sourceFiles) {
    const found = record.sourceObserved.filter((item) => key(item.path) === key(entry.path));
    if (found.length !== 1 || !found[0].snapshot || !Array.isArray(found[0].snapshot.ancestors) || ![null, entry.sha256].includes(found[0].snapshot.hash)) throw failure("Исходный snapshot не совпадает с полным реестром");
    if (record.to !== "global") continue;
    const snapshot = found[0].snapshot;
    const removed = record.operations.find((operation) => operation.owned && key(operation.path) === key(entry.path));
    const shared = record.global.value.files.find((item) => key(item.path) === key(entry.path) && item.sha256 === entry.sha256);
    const untouched = record.unchanged.find((operation) => operation.owned && key(operation.path) === key(entry.path));
    if (removed && JSON.stringify(removed.before) === JSON.stringify(snapshot)) continue;
    if (shared && snapshot.hash === entry.sha256 && record.global.observed.some((item) => key(item.path) === key(entry.path) && item.snapshot.hash === snapshot.hash && sameIdentity(item.snapshot.identity, snapshot.identity))) continue;
    if (untouched && snapshot.hash === null && JSON.stringify(untouched.before) === JSON.stringify(snapshot)) continue;
    throw failure("Собственный исходный ресурс потерян из полного плана миграции");
  }
  if (record.to === "local") for (const entry of record.target.value.files) {
    if (![...record.operations, ...record.unchanged].some((operation) => operation.owned && key(operation.path) === key(entry.path) && operation.source === entry.source && operation.afterHash === entry.sha256)) throw failure("Новый local manifest содержит непубликуемый ресурс");
  }
  for (const dir of record.createdDirectories) {
    installationPath(dir.path, { directory: true });
    if (path.parse(dir.path).root === path.resolve(dir.path) || !record.operations.some((operation) => { const relative = path.relative(dir.path, path.dirname(operation.path)); return relative === "" || relative !== ".." && !relative.startsWith(`..${path.sep}`) && !path.isAbsolute(relative); })) throw failure("Запись содержит посторонний временный каталог");
  }
  for (const operation of record.unchanged) assertInstallationSnapshot(operation.path, operation.before);
}

function environment(root) {
  installationPath(root, { directory: true });
  const leases = path.join(root, ".leases");
  installationPath(leases, { directory: true });
  if (exists(leases) && fs.readdirSync(leases).length) throw busy();
  if ([".install-transaction.json", ".install-recovery-lock", ".store-init-transaction.json", ".store-init-recovery.json"].some((file) => exists(path.join(root, file)))) throw busy();
  if (fs.readdirSync(root).some((file) => /^\.(?:install|store-init|migration)-(?:record|recovery)-.+\.tmp$/.test(file))) throw failure("Есть неподтверждённый временный журнал; файл сохранён");
}

function publish(file, temp, value, state) {
  installationPath(file); installationPath(temp);
  if (state.snapshot) assertInstallationSnapshot(file, state.snapshot);
  const target = state.snapshot ? temp : file;
  let fd;
  try { fd = fs.openSync(target, "wx", 0o600); } catch (error) { if (error.code === "EEXIST") throw busy(); throw error; }
  const own = identity(fs.fstatSync(fd));
  if (value.kind === "migration-recovery") value.fileIdentity = own;
  const bytes = Buffer.from(`${JSON.stringify(value, null, 2)}\n`);
  try { fs.writeFileSync(fd, bytes); fs.fsyncSync(fd); } finally { fs.closeSync(fd); }
  const written = installationSnapshot(target);
  if (!sameIdentity(written.identity, own) || written.hash !== installationHash(bytes)) throw failure("Журнал миграции заменён при публикации; файл сохранён");
  if (state.snapshot) { assertInstallationSnapshot(file, state.snapshot); fs.renameSync(temp, file); }
  state.snapshot = installationSnapshot(file);
}
const publishRecord = (record, state) => publish(pendingPath(path.join(record.store, ".symphysis")), path.join(record.store, ".symphysis", `.migration-record-${record.id}.tmp`), record, state);
const publishClaim = (claim, root, state) => publish(claimPath(root), path.join(root, `.migration-recovery-${claim.id}.tmp`), claim, state);

function originalCurrent(operation, current) { return current.hash === operation.before.hash && (operation.before.hash === null ? current.identity === null : sameIdentity(current.identity, operation.before.identity) || sameIdentity(current.identity, operation.backupIdentity)); }
function publishedCurrent(operation, current) { return operation.action === "remove" ? current.hash === null : current.hash === operation.afterHash && sameIdentity(current.identity, operation.stageIdentity); }
const fullyPublished = (record) => record.operations.every((operation) => publishedCurrent(operation, installationSnapshot(operation.path)));

function validateAuxiliary(record) {
  for (const operation of record.operations) for (const [file, own, hashes] of [[operation.stage, operation.stageIdentity, [emptyHash, operation.afterHash]], [operation.backup, operation.backupIdentity, [operation.before.hash, ...(record.phase === "staging" ? [emptyHash] : [])]]]) {
    if (!file || !exists(file)) continue;
    const snapshot = installationSnapshot(file);
    if (!own || !sameIdentity(snapshot.identity, own) || !hashes.includes(snapshot.hash)) throw failure("Stage/backup миграции изменён или не подтверждён; файл сохранён");
  }
}
function validateRollback(record) {
  validateAuxiliary(record);
  for (const operation of record.operations) {
    const current = installationSnapshot(operation.path);
    if (!originalCurrent(operation, current) && !publishedCurrent(operation, current)) throw failure("Цель миграции изменена пользователем; файл сохранён");
    if (operation.before.hash !== null && publishedCurrent(operation, current) && !originalCurrent(operation, current)) {
      const backup = installationSnapshot(operation.backup);
      if (backup.hash !== operation.before.hash || !sameIdentity(backup.identity, operation.backupIdentity)) throw failure("Исходный backup миграции не подтверждён");
    }
  }
}
function clearDirectories(record) {
  for (const dir of [...record.createdDirectories].reverse()) {
    installationPath(dir.path, { directory: true });
    const stat = fs.lstatSync(dir.path, { throwIfNoEntry: false });
    if (stat && sameIdentity(stat, dir)) try { fs.rmdirSync(dir.path); } catch (error) { if (!["ENOTEMPTY", "EEXIST", "ENOENT"].includes(error.code)) throw error; }
  }
}
function clearAuxiliary(record, event = () => {}) {
  validateAuxiliary(record);
  for (const [index, operation] of record.operations.entries()) {
    if (operation.stage && exists(operation.stage)) { files.removeVerified(operation.stage, operation.stageIdentity, [emptyHash, operation.afterHash]); event("recovery-stage-removed", index); }
    if (operation.backup && exists(operation.backup)) { files.removeVerified(operation.backup, operation.backupIdentity, [operation.before.hash, ...(record.phase === "staging" ? [emptyHash] : [])]); event("recovery-backup-removed", index); }
  }
  clearDirectories(record);
}
function rollback(record, event = () => {}) {
  validateRollback(record);
  for (const [index, operation] of [...record.operations].reverse().entries()) {
    const current = installationSnapshot(operation.path);
    if (!originalCurrent(operation, current) && operation.before.hash !== null) {
      const backup = installationSnapshot(operation.backup);
      assertInstallationSnapshot(operation.path, current); assertInstallationSnapshot(operation.backup, backup);
      if (current.hash === null) files.safeRename(operation.backup, operation.path); else fs.renameSync(operation.backup, operation.path);
      event("recovery-backup-restored", index);
    } else if (operation.before.hash === null && current.hash !== null) { files.removeVerified(operation.path, operation.stageIdentity, [operation.afterHash]); event("recovery-target-removed", index); }
    if (operation.stage && exists(operation.stage)) { files.removeVerified(operation.stage, operation.stageIdentity, [emptyHash, operation.afterHash]); event("recovery-stage-removed", index); }
    if (operation.backup && exists(operation.backup)) { files.removeVerified(operation.backup, operation.backupIdentity, [operation.before.hash, ...(record.phase === "staging" ? [emptyHash] : [])]); event("recovery-backup-removed", index); }
  }
  clearDirectories(record);
}

function newClaim(recordRead, writerRead, action) { return { format: 1, kind: "migration-recovery", id: randomUUID(), owner: { id: randomUUID(), token: randomBytes(32).toString("hex"), ...ownerProcess }, record: recordRead.value, pending: files.savedRead(recordRead), writer: { ...files.savedRead(writerRead), value: writerRead.value }, action, phase: "recovering", final: null }; }
function validateFinal(claim) {
  if (!Array.isArray(claim.final) || claim.final.length !== claim.record.operations.length) throw failure("Нет полного финального snapshot миграции");
  for (const [index, operation] of claim.record.operations.entries()) {
    const entry = claim.final[index];
    if (!entry || key(entry.path) !== key(operation.path) || !entry.snapshot || !(claim.action === "completed" ? publishedCurrent(operation, entry.snapshot) : originalCurrent(operation, entry.snapshot))) throw failure("Финальный snapshot не соответствует исходу миграции");
    assertInstallationSnapshot(operation.path, entry.snapshot);
    if (operation.stage && exists(operation.stage) || operation.backup && exists(operation.backup)) throw failure("После cleanup появились stage/backup; файлы сохранены");
  }
}
function validateOriginal(claim, root) {
  const writer = path.join(root, ".install-lock"), pending = pendingPath(root);
  const hasWriter = exists(writer), hasPending = exists(pending), hasReader = exists(claim.record.reader.descriptor.file);
  if (hasWriter) assertInstallationSnapshot(writer, claim.writer.snapshot);
  if (hasPending) assertInstallationSnapshot(pending, claim.pending.snapshot);
  if (hasReader) assertInstallationSnapshot(claim.record.reader.descriptor.file, claim.record.reader.snapshot);
  if (claim.phase === "recovering" && (!hasWriter || !hasPending || !hasReader)) throw failure("Рабочий recovery потерял исходные записи миграции");
  if (hasWriter && !hasPending || ["writer-removed", "pending-removed"].includes(claim.phase) && hasWriter || claim.phase === "pending-removed" && hasPending || ["reader-removed", "writer-removed", "pending-removed"].includes(claim.phase) && hasReader) throw failure("Состояние cleanup миграции противоречит сохранённому журналу");
}
function validateClaim(claim, store, fileIdentity) {
  if (!claim || claim.format !== 1 || claim.kind !== "migration-recovery" || !uuid(claim.id) || !["recovering", "cleanup", "reader-removed", "writer-removed", "pending-removed"].includes(claim.phase) || !["completed", "rolled-back"].includes(claim.action) || !owner({ ...claim.owner, generation: "recovery" }) || !sameIdentity(fileIdentity, claim.fileIdentity)) throw failure("Неподдерживаемый или заменённый recovery claim миграции");
  files.validateSavedRead(claim.pending, claim.record); files.validateSavedRead(claim.writer, claim.writer?.value);
  validateRecord(claim.record, store, claim.writer.value);
  if (claim.phase === "recovering") { if (claim.final !== null) throw failure("Рабочий recovery содержит неподтверждённый финальный snapshot"); }
  else validateFinal(claim);
}
function finishCleanup(claim, root, state, event, writer = null, reader = null) {
  validateFinal(claim); validateOriginal(claim, root); checkGlobal(claim.record, { requireReader: false });
  const lease = claim.record.reader;
  if (exists(lease.descriptor.file)) { if (reader) reader.release(); else files.removeVerified(lease.descriptor.file, lease.snapshot.identity, [lease.snapshot.hash]); event("recovery-reader-unlinked"); }
  claim.phase = "reader-removed"; publishClaim(claim, root, state); event("recovery-reader-recorded");
  const lock = path.join(root, ".install-lock");
  if (exists(lock)) { assertInstallationSnapshot(lock, claim.writer.snapshot); if (writer) writer.release(); else fs.unlinkSync(lock); event("recovery-writer-unlinked"); }
  claim.phase = "writer-removed"; publishClaim(claim, root, state); event("recovery-writer-recorded");
  if (exists(pendingPath(root))) { assertInstallationSnapshot(pendingPath(root), claim.pending.snapshot); fs.unlinkSync(pendingPath(root)); event("recovery-pending-unlinked"); }
  claim.phase = "pending-removed"; publishClaim(claim, root, state); event("recovery-pending-recorded");
  validateFinal(claim); validateOriginal(claim, root);
  assertInstallationSnapshot(claimPath(root), state.snapshot); fs.unlinkSync(claimPath(root)); event("recovery-claim-unlinked");
}
function finishOwned(record, pendingState, writer, reader, action, event) {
  const root = path.join(record.store, ".symphysis");
  environment(root); assertInstallationSnapshot(pendingPath(root), pendingState.snapshot);
  const recordRead = files.checkedRead(pendingPath(root)), writerRead = files.checkedRead(writer.file);
  validateRecord(recordRead.value, record.store, writerRead.value);
  const claim = newClaim(recordRead, writerRead, action);
  claim.final = record.operations.map((operation) => ({ path: operation.path, snapshot: installationSnapshot(operation.path) }));
  claim.phase = "cleanup"; validateFinal(claim);
  const state = { snapshot: null }; publishClaim(claim, root, state); event("cleanup-receipt-published");
  finishCleanup(claim, root, state, (name, index = -1) => event(name.replace(/^recovery-/, "cleanup-"), index), writer, reader);
}

function selectedDefinition(selected) {
  if (selected.legacy) return { legacy: true, evidence: selected.evidence };
  const read = files.checkedRead(selected.file);
  return { ...files.savedRead(read), value: read.value, file: selected.file, request: selected.request };
}
function ensureParents(file, record, state) {
  const missing = []; let folder = path.dirname(file);
  installationPath(file);
  while (!exists(folder)) { missing.push(folder); folder = path.dirname(folder); }
  for (const dir of missing.reverse()) { installationPath(dir, { directory: true }); fs.mkdirSync(dir); record.createdDirectories.push({ path: dir, ...identity(fs.lstatSync(dir)) }); publishRecord(record, state); }
}

/** Re-derive the complete preview, then hold one global reader and one store writer. */
export function applyMigrationPlan(value, options = {}) {
  const prepared = prepareMigrationPlan(value, options);
  const context = prepared.preview.to === "local" ? prepared.resolution.sourceContext : prepared.resolution.candidateContext;
  const store = prepared.resolution.planningRoot.root, root = path.join(store, ".symphysis");
  const reader = acquireReader({ ...context, status: "ready" });
  let writer, record, keep = false;
  const state = { snapshot: null }, id = randomUUID();
  const event = (name, index = -1) => { if (options.fault) options.fault({ name, index, id, root }); };
  try {
    writer = acquireWriter({ root, generation: context.runtime.generation });
    const globalSelected = prepared.preview.to === "local" ? prepared.sourceInstallation : prepared.targetInstallation;
    const global = selectedDefinition(globalSelected);
    global.observed = globalSelected.manifest.files.map((entry) => ({ path: entry.path, snapshot: installationSnapshot(entry.path) }));
    const lease = files.checkedRead(reader.file);
    const changed = prepared.operations.filter((operation) => operation.action !== "unchanged");
    record = { format: 1, kind: "migration", id, store, from: prepared.preview.from, to: prepared.preview.to, phase: "staging", owner: writer.descriptor,
      source: selectedDefinition(prepared.sourceInstallation), target: prepared.preparedLocal ? { request: prepared.preparedLocal.request, value: prepared.preparedLocal.manifest } : null,
      global, reader: { ...files.savedRead(lease), value: lease.value, descriptor: reader.descriptor, managementRoot: managementRoot(context) }, createdDirectories: [],
      sourceObserved: prepared.sourceInstallation.manifest.files.map((entry) => {
        const observed = prepared.preview.observed.find((item) => key(item.path) === key(entry.path) && item.ownership === "source-managed");
        if (!observed) throw failure("Fresh preview потерял исходный snapshot");
        return { path: entry.path, snapshot: observed.snapshot };
      }),
      unchanged: prepared.operations.filter((operation) => operation.action === "unchanged").map(({ bytes, ...operation }) => operation),
      operations: changed.map((operation, index) => ({ path: operation.path, ...(operation.source ? { source: operation.source, purpose: operation.purpose } : { kind: operation.kind }), ...(operation.clientId ? { clientId: operation.clientId } : {}), ...(operation.projection ? { projection: true } : {}), owned: operation.owned, action: operation.action, before: operation.before, afterHash: operation.afterHash,
        stage: operation.afterHash === null ? null : path.join(path.dirname(operation.path), `.symphysis-migrate-${id}-${index}.stage`), backup: operation.before.hash === null ? null : path.join(path.dirname(operation.path), `.symphysis-migrate-${id}-${index}.backup`), stageIdentity: null, backupIdentity: null })) };
    validateRecord(record, store, files.checkedRead(writer.file).value);
    for (const observation of prepared.preview.observed) assertInstallationSnapshot(observation.path, observation.snapshot);
    for (const operation of prepared.operations) assertInstallationSnapshot(operation.path, operation.before);
    checkGlobal(record);
    publishRecord(record, state); event("journal");
    for (const [index, operation] of record.operations.entries()) {
      ensureParents(operation.path, record, state);
      if (operation.stage) {
        const fd = fs.openSync(operation.stage, "wx", 0o600); operation.stageIdentity = identity(fs.fstatSync(fd));
        try { publishRecord(record, state); event("stage-open", index); fs.writeFileSync(fd, changed[index].bytes); fs.fsyncSync(fd); } finally { fs.closeSync(fd); }
        if (installationSnapshot(operation.stage).hash !== operation.afterHash) throw failure("Stage миграции не совпал с preview");
        event("stage-written", index);
      }
      if (operation.backup) {
        assertInstallationSnapshot(operation.path, operation.before);
        const sourceFd = fs.openSync(operation.path, fs.constants.O_RDONLY | (fs.constants.O_NOFOLLOW ?? 0));
        let original;
        try { if (!sameIdentity(fs.fstatSync(sourceFd), operation.before.identity)) throw failure("Исходный файл заменён перед backup"); original = fs.readFileSync(sourceFd); } finally { fs.closeSync(sourceFd); }
        assertInstallationSnapshot(operation.path, operation.before);
        const fd = fs.openSync(operation.backup, "wx", 0o600); operation.backupIdentity = identity(fs.fstatSync(fd));
        try { publishRecord(record, state); event("backup-open", index); fs.writeFileSync(fd, original); fs.fsyncSync(fd); } finally { fs.closeSync(fd); }
        const backup = installationSnapshot(operation.backup);
        if (backup.hash !== operation.before.hash || !sameIdentity(backup.identity, operation.backupIdentity)) throw failure("Backup миграции не соответствует исходным байтам");
        event("backup-copied", index);
      }
    }
    checkGlobal(record);
    for (const operation of record.operations) assertInstallationSnapshot(operation.path, operation.before);
    record.phase = "publishing"; publishRecord(record, state);
    for (const [index, operation] of record.operations.entries()) {
      assertInstallationSnapshot(operation.path, operation.before);
      if (operation.action === "remove") { files.removeVerified(operation.path, operation.before.identity, [operation.before.hash]); event("target-removed", index); }
      else {
        const staged = installationSnapshot(operation.stage);
        if (staged.hash !== operation.afterHash || !sameIdentity(staged.identity, operation.stageIdentity)) throw failure("Stage миграции изменился");
        if (operation.before.hash === null) files.safeRename(operation.stage, operation.path); else fs.renameSync(operation.stage, operation.path);
        event("target-published", index);
      }
      publishRecord(record, state);
    }
    record.phase = "committed"; publishRecord(record, state); event("receipt-published", record.operations.length - 1);
    clearAuxiliary(record); finishOwned(record, state, writer, reader, "completed", event);
    return { migrated: true, from: record.from, to: record.to, storeRoot: store, written: changed.map((operation) => operation.path), warnings: prepared.preview.warnings };
  } catch (error) {
    if (record && state.snapshot) try {
      if (record.phase === "committed") throw failure("Миграция опубликована; требуется явный cleanup");
      assertInstallationSnapshot(pendingPath(root), state.snapshot); checkGlobal(record); rollback(record);
      finishOwned(record, state, writer, reader, "rolled-back", event);
    } catch (rollbackError) { keep = true; throw failure(`Миграция сохранена для recovery: ${rollbackError.message}`); }
    throw error;
  } finally { if (!keep) { writer?.release(); reader.release(); } }
}

/** Explicit recovery resumes only verified dead owners and keeps foreign state intact. */
export function recoverMigration(options = {}) {
  const store = resolvePlanningContext(options).root, root = path.join(store, ".symphysis");
  if (!exists(root)) return { recovered: false };
  environment(root);
  const pending = pendingPath(root), lock = path.join(root, ".install-lock"), claimFile = claimPath(root);
  if (!exists(pending) && !exists(lock) && !exists(claimFile)) return { recovered: false };
  let claim;
  const state = { snapshot: null };
  try {
    if (exists(claimFile)) {
      const read = files.checkedRead(claimFile); claim = read.value;
      validateClaim(claim, store, read.snapshot.identity);
      if (!files.ownerDefinitelyDead(claim.owner.pid) || !files.ownerDefinitelyDead(claim.writer.value.pid)) throw busy();
      validateOriginal(claim, root); state.snapshot = read.snapshot;
    } else {
      if (!exists(pending) || !exists(lock)) throw busy();
      const recordRead = files.checkedRead(pending), writerRead = files.checkedRead(lock);
      validateRecord(recordRead.value, store, writerRead.value);
      if (!files.ownerDefinitelyDead(writerRead.value.pid)) throw busy();
      checkGlobal(recordRead.value);
      const complete = fullyPublished(recordRead.value);
      if (recordRead.value.phase === "committed" && !complete) throw failure("Опубликованная миграция изменена пользователем; файлы сохранены");
      if (complete) validateAuxiliary(recordRead.value); else validateRollback(recordRead.value);
      claim = newClaim(recordRead, writerRead, complete ? "completed" : "rolled-back");
      assertInstallationSnapshot(pending, recordRead.snapshot); assertInstallationSnapshot(lock, writerRead.snapshot);
    }
    if (claim.phase === "recovering") {
      checkGlobal(claim.record);
      if (claim.action === "completed") { if (!fullyPublished(claim.record)) throw failure("Цели миграции изменились после recovery"); validateAuxiliary(claim.record); }
      else validateRollback(claim.record);
    }
    claim.owner = { id: randomUUID(), token: randomBytes(32).toString("hex"), ...ownerProcess };
    publishClaim(claim, root, state);
    const event = (name, index = -1) => { if (options.fault) options.fault({ name, index, id: claim.id, root }); };
    event("recovery-claimed"); validateOriginal(claim, root);
    if (claim.phase === "recovering") {
      if (claim.action === "completed") clearAuxiliary(claim.record, event); else rollback(claim.record, event);
      claim.final = claim.record.operations.map((operation) => ({ path: operation.path, snapshot: installationSnapshot(operation.path) }));
      claim.phase = "cleanup"; validateFinal(claim); publishClaim(claim, root, state); event("recovery-resources-cleaned");
    }
    finishCleanup(claim, root, state, event);
    return { recovered: true, action: claim.action, from: claim.record.from, to: claim.record.to, storeRoot: store };
  } catch (error) { if (error instanceof InstallationError && ["installation-busy", "migration-recovery-required"].includes(error.code)) throw error; throw failure(error.message); }
}
