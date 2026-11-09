import fs from "node:fs";
import path from "node:path";
import { randomBytes, randomUUID } from "node:crypto";
import { resolveInitializationContext, resolvePlanningContext } from "./runtime-resolver.js";
import { acquireReader, acquireWriter, managementRoot } from "./runtime-leases.js";
import { InstallationError, installationHash, installationKey, installationSnapshot, assertInstallationSnapshot, installationPath } from "./installation-plan.js";
import { _transactionFileOps as files } from "./installation-transaction.js";
import { planPlanningConfig } from "./planning-config.js";

const failure = (message) => new InstallationError("store-initialization-conflict", message);
const pendingPath = (root) => path.join(root, ".store-init-transaction.json");
const receiptPath = (root) => path.join(root, "store-init.json");
const claimPath = (root) => path.join(root, ".store-init-recovery.json");
const exists = (file) => fs.lstatSync(file, { throwIfNoEntry: false }) !== undefined;
const identity = (stat) => ({ dev: String(stat.dev), ino: String(stat.ino) });
const sameIdentity = (first, second) => Boolean(first && second && String(first.dev) === second.dev && String(first.ino) === second.ino);
const uuid = (value) => typeof value === "string" && /^[a-f0-9-]{36}$/.test(value);
const hash = (value) => typeof value === "string" && /^[a-f0-9]{64}$/.test(value);
const emptyHash = installationHash(Buffer.alloc(0));
const ownerProcess = Object.freeze({ pid: process.pid, startedAt: Math.floor(Date.now() - process.uptime() * 1000), instance: randomUUID() });
const busy = () => new InstallationError("installation-busy", "Владелец store init жив или не подтверждён; чужие записи сохраняются");
const typedTargets = (store) => ({
  "planning-config": ["openspec/config.yaml", "openspec/config.yml"],
  "store-declaration": ["openspec/symphysis.json"],
  "initial-settings": ["symphysis.yaml"],
  "initial-roots": [".symphysis/tools/journal-roots.json"],
  "gitignore-merge": [".gitignore"],
  receipt: [".symphysis/store-init.json"],
});

function targetFor(store, operation) {
  installationPath(operation.path);
  const target = typedTargets(store)[operation.kind]?.map((relative) => path.join(store, relative)).find((file) => installationKey(file) === installationKey(operation.path));
  if (!target) throw failure("Store init содержит неизвестный тип или постороннюю цель");
  return target;
}

function publish(file, temp, value, state) {
  installationPath(file); installationPath(temp);
  if (state.snapshot) assertInstallationSnapshot(file, state.snapshot);
  const target = state.snapshot ? temp : file;
  let fd;
  try { fd = fs.openSync(target, "wx", 0o600); } catch (error) { if (error.code === "EEXIST") throw busy(); throw error; }
  const own = identity(fs.fstatSync(fd));
  if (value.kind === "store-init-recovery") value.fileIdentity = own;
  const bytes = Buffer.from(`${JSON.stringify(value, null, 2)}\n`);
  try { fs.writeFileSync(fd, bytes); fs.fsyncSync(fd); } finally { fs.closeSync(fd); }
  const written = installationSnapshot(target);
  if (!sameIdentity(written.identity, own) || written.hash !== installationHash(bytes)) throw failure("Запись store init заменена при публикации; файл сохранён");
  if (state.snapshot) { assertInstallationSnapshot(file, state.snapshot); fs.renameSync(temp, file); }
  state.snapshot = installationSnapshot(file);
}

function publishRecord(record, state) {
  const root = path.join(record.store, ".symphysis");
  publish(pendingPath(root), path.join(root, `.store-init-record-${record.id}.tmp`), record, state);
}
function publishClaim(claim, root, state) {
  publish(claimPath(root), path.join(root, `.store-init-recovery-${claim.id}.tmp`), claim, state);
}

function validOwner(owner) {
  return owner && Number.isSafeInteger(owner.pid) && owner.pid > 0 && Number.isSafeInteger(owner.startedAt) && owner.startedAt > 0 && uuid(owner.id) && uuid(owner.instance) && hash(owner.token) && (owner.generation === null || typeof owner.generation === "string");
}
function validateReader(reader, owner) {
  if (!reader || !reader.descriptor || !reader.value) throw failure("Store init не подтверждает свой global reader lease");
  files.validateSavedRead(reader, reader.value);
  const descriptor = reader.descriptor;
  const root = installationPath(reader.managementRoot, { directory: true });
  const expected = path.join(root, ".leases", `${descriptor.id}.json`);
  if (!validOwner(descriptor) || descriptor.pid !== owner.pid || reader.value.format !== 1 || reader.value.kind !== "reader" || installationKey(installationPath(descriptor.file)) !== installationKey(expected)) throw failure("Неподдерживаемое владение global reader lease store init");
  for (const key of ["pid", "startedAt", "instance", "generation"]) if (descriptor[key] !== owner[key]) throw failure("Global reader и store writer принадлежат разным процессам/поколениям");
  for (const key of ["id", "token", "pid", "startedAt", "instance", "generation"]) if (reader.value[key] !== descriptor[key]) throw failure("Global reader lease и запись store init не согласованы");
  if (exists(expected)) assertInstallationSnapshot(expected, reader.snapshot);
}

function validateRecord(record, store, writer) {
  if (!record || record.format !== 1 || record.kind !== "store-init" || !uuid(record.id) || !["staging", "publishing", "committed"].includes(record.phase) || typeof record.generation !== "string" || !record.generation || !Array.isArray(record.operations) || !record.operations.length || !Array.isArray(record.createdDirectories) || installationKey(installationPath(record.store, { directory: true })) !== installationKey(store)) throw failure("Неподдерживаемая запись store init");
  const root = path.join(store, ".symphysis");
  if (!validOwner(writer) || writer.format !== 1 || writer.kind !== "writer" || !validOwner(record.owner) || installationKey(installationPath(record.owner.file)) !== installationKey(path.join(root, ".install-lock"))) throw failure("Writer store init не подтверждён");
  if (record.generation !== record.owner.generation) throw failure("Store init и writer относятся к разным поколениям runtime");
  for (const key of ["id", "generation", "token", "pid", "startedAt", "instance"]) if (writer[key] !== record.owner[key]) throw failure("Writer lock принадлежит другой операции");
  const seen = new Set();
  for (const [index, operation] of record.operations.entries()) {
    const target = targetFor(store, operation);
    if (seen.has(installationKey(target)) || !["create", "replace"].includes(operation.action) || !operation.before || !Array.isArray(operation.before.ancestors) || !(operation.before.hash === null || hash(operation.before.hash)) || !hash(operation.afterHash) || (operation.before.hash !== null && !operation.before.identity)) throw failure("Store init не подтверждает исходные/конечные файлы");
    seen.add(installationKey(target));
    if (operation.stage !== path.join(path.dirname(target), `.symphysis-init-${record.id}-${index}.stage`) || operation.backup !== (operation.before.hash === null ? null : path.join(path.dirname(target), `.symphysis-init-${record.id}-${index}.backup`))) throw failure("Store init содержит неподтверждённый stage/backup");
    installationPath(operation.stage); if (operation.backup) installationPath(operation.backup);
    if (operation.kind === "receipt" && index !== record.operations.length - 1) throw failure("Квитанция не является последней публикацией store init");
    if (operation.kind.startsWith("initial-") && operation.before.hash !== null) throw failure("Личные настройки и карта не заменяются store init");
  }
  for (const dir of record.createdDirectories) {
    installationPath(dir.path, { directory: true });
    const relative = path.relative(store, dir.path);
    if (!relative || relative === ".." || relative.startsWith(`..${path.sep}`) || path.isAbsolute(relative) || !record.operations.some((operation) => { const tail = path.relative(dir.path, path.dirname(operation.path)); return tail === "" || (tail !== ".." && !tail.startsWith(`..${path.sep}`) && !path.isAbsolute(tail)); })) throw failure("Store init содержит посторонний временный каталог");
  }
  validateReader(record.reader, record.owner);
}

function environment(root) {
  const readers = path.join(root, ".leases");
  installationPath(readers, { directory: true });
  if (exists(readers) && fs.readdirSync(readers).length) throw busy();
  if ([".install-transaction.json", ".install-recovery-lock"].some((file) => exists(path.join(root, file)))) throw busy();
  if (fs.readdirSync(root).some((file) => /^\.store-init-(?:record|recovery)-.*\.tmp$/.test(file))) throw failure("Есть неподтверждённый временный журнал store init; файл сохранён");
}

function ensureParents(file, record, state) {
  installationPath(file);
  const missing = [];
  let folder = path.dirname(file);
  while (!exists(folder)) { missing.push(folder); folder = path.dirname(folder); }
  for (const dir of missing.reverse()) {
    installationPath(dir, { directory: true }); fs.mkdirSync(dir);
    record.createdDirectories.push({ path: dir, ...identity(fs.lstatSync(dir)) });
    publishRecord(record, state);
  }
}

function originalCurrent(operation, current) {
  return current.hash === operation.before.hash && (operation.before.hash === null ? current.identity === null : sameIdentity(current.identity, operation.before.identity) || sameIdentity(current.identity, operation.backupIdentity));
}
function publishedCurrent(operation, current) { return current.hash === operation.afterHash && sameIdentity(current.identity, operation.stageIdentity); }

function validateStoreAuxiliary(record) {
  for (const operation of record.operations) {
    for (const [file, own, hashes] of [[operation.stage, operation.stageIdentity, [emptyHash, operation.afterHash]], [operation.backup, operation.backupIdentity, [operation.before.hash, ...(record.phase === "staging" ? [emptyHash] : [])]]]) {
      if (!file || !exists(file)) continue;
      const snapshot = installationSnapshot(file);
      if (!own || !sameIdentity(snapshot.identity, own) || !hashes.includes(snapshot.hash)) throw failure("Store init stage/backup изменён или не подтверждён; файл сохранён");
    }
  }
}

function validateStoreRollback(record) {
  validateStoreAuxiliary(record);
  for (const operation of record.operations) {
    const current = installationSnapshot(operation.path);
    if (!originalCurrent(operation, current) && !publishedCurrent(operation, current)) throw failure("Цель store init изменена пользователем; файл сохранён");
    if (operation.before.hash !== null && publishedCurrent(operation, current)) {
      const backup = installationSnapshot(operation.backup);
      if (backup.hash !== operation.before.hash || !sameIdentity(backup.identity, operation.backupIdentity)) throw failure("Исходный backup store init не подтверждён");
    }
  }
}

function clearCreatedDirectories(record) {
  for (const dir of [...record.createdDirectories].reverse()) {
    installationPath(dir.path, { directory: true });
    const stat = fs.lstatSync(dir.path, { throwIfNoEntry: false });
    if (stat && sameIdentity(stat, dir)) {
      try { fs.rmdirSync(dir.path); } catch (error) { if (!["ENOTEMPTY", "EEXIST", "ENOENT"].includes(error.code)) throw error; }
    }
  }
}
function clearStoreAuxiliary(record, event = () => {}) {
  validateStoreAuxiliary(record);
  for (const [index, operation] of record.operations.entries()) {
    if (exists(operation.stage)) { files.removeVerified(operation.stage, operation.stageIdentity, [emptyHash, operation.afterHash]); event("recovery-stage-removed", index); }
    if (operation.backup && exists(operation.backup)) { files.removeVerified(operation.backup, operation.backupIdentity, [operation.before.hash, ...(record.phase === "staging" ? [emptyHash] : [])]); event("recovery-backup-removed", index); }
  }
  clearCreatedDirectories(record);
}

function rollbackStore(record, event = () => {}) {
  validateStoreRollback(record);
  for (const [index, operation] of [...record.operations].reverse().entries()) {
    const current = installationSnapshot(operation.path);
    if (operation.before.hash !== null && publishedCurrent(operation, current)) {
      const backup = installationSnapshot(operation.backup);
      assertInstallationSnapshot(operation.path, current); assertInstallationSnapshot(operation.backup, backup);
      // Replace the current file atomically; a planning root never temporarily
      // loses config.yaml/config.yml, including when recovery itself crashes.
      fs.renameSync(operation.backup, operation.path);
      event("recovery-backup-restored", index);
    } else if (operation.before.hash === null && current.hash !== null) {
      files.removeVerified(operation.path, operation.stageIdentity, [operation.afterHash]);
      event("recovery-target-removed", index);
    }
    if (exists(operation.stage)) { files.removeVerified(operation.stage, operation.stageIdentity, [emptyHash, operation.afterHash]); event("recovery-stage-removed", index); }
    if (operation.backup && exists(operation.backup)) { files.removeVerified(operation.backup, operation.backupIdentity, [operation.before.hash, ...(record.phase === "staging" ? [emptyHash] : [])]); event("recovery-backup-removed", index); }
  }
  clearCreatedDirectories(record);
}

/** Store-only transaction: its receipt can never be mistaken for a local runtime manifest. */
function applyStorePlan(store, operations, generation, { fault, reader, context } = {}) {
  const root = path.join(store, ".symphysis");
  const file = pendingPath(root);
  if (exists(file) || exists(claimPath(root))) throw failure("Есть незавершённый store init; выполни symphysis init --recover");
  const receipt = receiptPath(root);
  const receiptBytes = Buffer.from(`${JSON.stringify({ format: 1, scope: "global", runtimeApi: 1, schemaApi: 1 }, null, 2)}\n`);
  const all = [...operations, { kind: "receipt", path: receipt, beforeHash: installationSnapshot(receipt).hash, bytes: receiptBytes }];
  const changed = all.filter((operation) => operation.beforeHash !== installationHash(operation.bytes));
  if (!changed.length) return { written: [], unchanged: all.map((operation) => operation.path) };
  const writer = acquireWriter({ root, generation });
  const id = randomUUID();
  let record = null;
  let keepLock = false;
  const state = { snapshot: null };
  const event = (name, index = -1) => { if (fault) fault({ name, index, id, root }); };
  try {
    const snapshots = changed.map((operation) => {
      const before = installationSnapshot(operation.path);
      if (before.hash !== operation.beforeHash) throw failure("Состояние store изменилось после подготовки merge");
      return before;
    });
    const lease = files.checkedRead(reader.file);
    record = { format: 1, kind: "store-init", id, store, generation, phase: "staging", createdDirectories: [], owner: writer.descriptor,
      reader: { ...files.savedRead(lease), value: lease.value, descriptor: reader.descriptor, managementRoot: managementRoot(context) },
      operations: changed.map((operation, index) => ({ kind: operation.kind, path: targetFor(store, operation), action: snapshots[index].hash === null ? "create" : "replace", before: snapshots[index], afterHash: installationHash(operation.bytes), stage: path.join(path.dirname(operation.path), `.symphysis-init-${id}-${index}.stage`), backup: snapshots[index].hash === null ? null : path.join(path.dirname(operation.path), `.symphysis-init-${id}-${index}.backup`), stageIdentity: null, backupIdentity: null })) };
    validateRecord(record, store, files.checkedRead(writer.file).value);
    publishRecord(record, state);
    event("journal");
    for (const [index, operation] of record.operations.entries()) {
      installationPath(operation.path);
      ensureParents(operation.path, record, state);
      const fd = fs.openSync(operation.stage, "wx", 0o600);
      operation.stageIdentity = identity(fs.fstatSync(fd));
      try { publishRecord(record, state); event("stage-open", index); fs.writeFileSync(fd, changed[index].bytes); fs.fsyncSync(fd); }
      finally { fs.closeSync(fd); }
      if (installationSnapshot(operation.stage).hash !== operation.afterHash) throw failure("Stage store init не совпал с запланированными байтами");
      event("stage-written", index);
      if (operation.backup) {
        assertInstallationSnapshot(operation.path, operation.before);
        const sourceFd = fs.openSync(operation.path, fs.constants.O_RDONLY | (fs.constants.O_NOFOLLOW ?? 0));
        let original;
        try {
          if (!sameIdentity(fs.fstatSync(sourceFd), operation.before.identity)) throw failure("Исходный файл store init заменён перед backup");
          original = fs.readFileSync(sourceFd);
        } finally { fs.closeSync(sourceFd); }
        assertInstallationSnapshot(operation.path, operation.before);
        const backupFd = fs.openSync(operation.backup, "wx", 0o600);
        operation.backupIdentity = identity(fs.fstatSync(backupFd));
        try { publishRecord(record, state); event("backup-open", index); fs.writeFileSync(backupFd, original); fs.fsyncSync(backupFd); }
        finally { fs.closeSync(backupFd); }
        const backup = installationSnapshot(operation.backup);
        if (backup.hash !== operation.before.hash || !sameIdentity(backup.identity, operation.backupIdentity)) throw failure("Backup store init не соответствует исходным байтам");
        // This legacy event name denotes a durable backup; the original target
        // remains present so OpenSpec can resolve the pointer during recovery.
        event("backup-renamed", index);
      }
    }
    for (const operation of record.operations) assertInstallationSnapshot(operation.path, operation.before);
    record.phase = "publishing"; publishRecord(record, state);
    for (const [index, operation] of record.operations.entries()) {
      assertInstallationSnapshot(operation.path, operation.before);
      const staged = installationSnapshot(operation.stage);
      if (staged.hash !== operation.afterHash || !sameIdentity(staged.identity, operation.stageIdentity)) throw failure("Stage store-init изменился");
      if (operation.backup) fs.renameSync(operation.stage, operation.path);
      else files.safeRename(operation.stage, operation.path);
      event("target-renamed", index); publishRecord(record, state);
    }
    record.phase = "committed"; publishRecord(record, state); event("receipt-published", record.operations.length - 1);
    clearStoreAuxiliary(record);
    finishOwned(record, state, writer, reader, "completed", event);
    return { written: changed.map((operation) => operation.path), unchanged: all.filter((operation) => !changed.includes(operation)).map((operation) => operation.path) };
  } catch (error) {
    if (record && state.snapshot) {
      try {
        if (record.phase === "committed") throw failure("Store init опубликован; требуется явный cleanup");
        assertInstallationSnapshot(file, state.snapshot); rollbackStore(record);
        finishOwned(record, state, writer, reader, "rolled-back", event);
      }
      catch (rollbackError) { keepLock = true; throw failure(`Store init сохранён для восстановления: ${rollbackError.message}`); }
    }
    throw error;
  } finally { if (!keepLock) writer.release(); }
}

export function planProjectInitialization(options = {}) {
  const resolved = resolveInitializationContext(options);
  if (!resolved.ready) throw new InstallationError(resolved.diagnostics[0]?.code ?? "initialization-blocked", resolved.diagnostics.map((issue) => `${issue.message}\n${issue.action}`).join("\n"));
  const context = resolved.context;
  const store = context.store.root;
  const nonOwned = planPlanningConfig({ storeRoot: store, sourceConfig: fs.readFileSync(path.join(context.runtime.root, "openspec", "config.symphysis.yaml"), "utf8"), declaration: true });
  const receipt = receiptPath(path.join(store, ".symphysis"));
  if (fs.existsSync(receipt)) {
    let old;
    try { old = JSON.parse(fs.readFileSync(receipt, "utf8")); } catch { throw failure("Квитанция store init не является JSON"); }
    if (old.format !== 1 || old.scope !== "global" || old.runtimeApi !== 1 || old.schemaApi !== 1) throw failure("Неизвестная квитанция store init сохранена");
  }
  return { context, storeRoot: store, operations: nonOwned };
}

export function initProject(options = {}) {
  const { context, storeRoot: store, operations: nonOwned } = planProjectInitialization(options);
  // Installation preconditions are distinct from public runtime compatibility.
  const reader = acquireReader({ ...context, status: "ready" });
  try {
    const result = applyStorePlan(store, nonOwned, context.runtime.generation, { ...options, reader, context });
    return { ...result, storeRoot: store, scope: "global", generation: context.runtime.generation, messages: [`Инициализирован выбранный store: ${store}`] };
  } finally { reader.release(); }
}

function newClaim(recordRead, writerRead, action) {
  return { format: 1, kind: "store-init-recovery", id: randomUUID(), owner: { id: randomUUID(), token: randomBytes(32).toString("hex"), ...ownerProcess },
    record: recordRead.value, pending: files.savedRead(recordRead), writer: { ...files.savedRead(writerRead), value: writerRead.value },
    action, phase: "recovering", final: null };
}

function validateFinal(claim) {
  if (!Array.isArray(claim.final) || claim.final.length !== claim.record.operations.length) throw failure("Store init recovery не содержит полного финального снимка");
  for (const [index, operation] of claim.record.operations.entries()) {
    const entry = claim.final[index];
    const valid = entry?.snapshot && (claim.action === "completed" ? publishedCurrent(operation, entry.snapshot) : originalCurrent(operation, entry.snapshot));
    if (!entry || installationKey(entry.path) !== installationKey(operation.path) || !valid) throw failure("Финальный снимок store init не соответствует выбранному исходу");
    assertInstallationSnapshot(operation.path, entry.snapshot);
    if (exists(operation.stage) || (operation.backup && exists(operation.backup))) throw failure("После cleanup появились stage/backup store init; файлы сохранены");
  }
}

function validateClaim(claim, store, ownIdentity) {
  if (!claim || claim.format !== 1 || claim.kind !== "store-init-recovery" || !uuid(claim.id) || !["recovering", "cleanup", "reader-removed", "writer-removed", "pending-removed"].includes(claim.phase) || !["completed", "rolled-back"].includes(claim.action) || !validOwner({ ...claim.owner, generation: null }) || !sameIdentity(ownIdentity, claim.fileIdentity)) throw failure("Неподдерживаемый или заменённый recovery claim store init");
  files.validateSavedRead(claim.pending, claim.record);
  files.validateSavedRead(claim.writer, claim.writer?.value);
  validateRecord(claim.record, store, claim.writer.value);
  if (claim.phase === "recovering") { if (claim.final !== null) throw failure("Рабочий recovery содержит неподтверждённый финальный снимок"); }
  else validateFinal(claim);
}

function validateOriginalFiles(claim, root) {
  const writer = path.join(root, ".install-lock");
  const pending = pendingPath(root);
  const hasWriter = exists(writer); const hasPending = exists(pending);
  if (hasWriter) assertInstallationSnapshot(writer, claim.writer.snapshot);
  if (hasPending) assertInstallationSnapshot(pending, claim.pending.snapshot);
  if (claim.phase === "recovering" && (!hasWriter || !hasPending)) throw failure("Рабочий store init recovery потерял исходные записи");
  if (hasWriter && !hasPending) throw failure("Store writer остался без подтверждённого журнала");
  if (["writer-removed", "pending-removed"].includes(claim.phase) && hasWriter) throw failure("После cleanup появился чужой store writer");
  if (claim.phase === "pending-removed" && hasPending) throw failure("После cleanup появился журнал store init");
}

function finishCleanup(claim, root, state, event, writer = null, reader = null) {
  validateFinal(claim); validateOriginalFiles(claim, root);
  const lease = claim.record.reader;
  validateReader(lease, claim.record.owner);
  if (exists(lease.descriptor.file)) {
    if (reader) reader.release();
    else files.removeVerified(lease.descriptor.file, lease.snapshot.identity, [lease.snapshot.hash]);
    event("recovery-reader-unlinked");
  }
  claim.phase = "reader-removed"; publishClaim(claim, root, state); event("recovery-reader-recorded");
  const lock = path.join(root, ".install-lock");
  if (exists(lock)) {
    assertInstallationSnapshot(lock, claim.writer.snapshot);
    if (writer) writer.release(); else fs.unlinkSync(lock);
    event("recovery-writer-unlinked");
  }
  claim.phase = "writer-removed"; publishClaim(claim, root, state); event("recovery-writer-recorded");
  if (exists(pendingPath(root))) { assertInstallationSnapshot(pendingPath(root), claim.pending.snapshot); fs.unlinkSync(pendingPath(root)); event("recovery-pending-unlinked"); }
  claim.phase = "pending-removed"; publishClaim(claim, root, state); event("recovery-pending-recorded");
  validateFinal(claim); validateOriginalFiles(claim, root);
  assertInstallationSnapshot(claimPath(root), state.snapshot); fs.unlinkSync(claimPath(root)); event("recovery-claim-unlinked");
}

function finishOwned(record, pendingState, writer, reader, action, event) {
  const root = path.join(record.store, ".symphysis");
  environment(root); assertInstallationSnapshot(pendingPath(root), pendingState.snapshot);
  const recordRead = files.checkedRead(pendingPath(root));
  const writerRead = files.checkedRead(writer.file);
  validateRecord(recordRead.value, record.store, writerRead.value);
  const claim = newClaim(recordRead, writerRead, action);
  claim.final = record.operations.map((operation) => ({ path: operation.path, snapshot: installationSnapshot(operation.path) }));
  claim.phase = "cleanup"; validateFinal(claim);
  const state = { snapshot: null }; publishClaim(claim, root, state); event("cleanup-receipt-published");
  finishCleanup(claim, root, state, (name, index = -1) => event(name.replace(/^recovery-/, "cleanup-"), index), writer, reader);
}

/** Explicit scoped recovery; unrelated global or store reader leases are never pruned. */
export function recoverProjectInitialization(options = {}) {
  const store = resolvePlanningContext(options).root;
  const root = path.join(store, ".symphysis");
  if (!exists(root)) return { recovered: false };
  environment(root);
  const pending = pendingPath(root); const lock = path.join(root, ".install-lock"); const claimFile = claimPath(root);
  if (!exists(pending) && !exists(lock) && !exists(claimFile)) return { recovered: false };
  let claim;
  const state = { snapshot: null };
  try {
    if (exists(claimFile)) {
      const read = files.checkedRead(claimFile); claim = read.value;
      validateClaim(claim, store, read.snapshot.identity);
      if (!files.ownerDefinitelyDead(claim.owner.pid) || !files.ownerDefinitelyDead(claim.writer.value.pid)) throw busy();
      validateOriginalFiles(claim, root);
      state.snapshot = read.snapshot;
    } else {
      if (!exists(pending) || !exists(lock)) throw busy();
      const recordRead = files.checkedRead(pending); const writerRead = files.checkedRead(lock);
      validateRecord(recordRead.value, store, writerRead.value);
      if (!files.ownerDefinitelyDead(writerRead.value.pid)) throw busy();
      const complete = files.fullyPublished(recordRead.value);
      if (recordRead.value.phase === "committed" && !complete) throw failure("Опубликованный store init изменён пользователем; файлы сохранены");
      if (complete) validateStoreAuxiliary(recordRead.value); else validateStoreRollback(recordRead.value);
      claim = newClaim(recordRead, writerRead, complete ? "completed" : "rolled-back");
      assertInstallationSnapshot(pending, recordRead.snapshot); assertInstallationSnapshot(lock, writerRead.snapshot);
    }
    if (claim.phase === "recovering") {
      if (claim.action === "completed") { if (!files.fullyPublished(claim.record)) throw failure("Файлы store init изменены после сбоя recovery"); validateStoreAuxiliary(claim.record); }
      else validateStoreRollback(claim.record);
    }
    claim.owner = { id: randomUUID(), token: randomBytes(32).toString("hex"), ...ownerProcess };
    publishClaim(claim, root, state);
    const event = (name, index = -1) => { if (options.fault) options.fault({ name, index, id: claim.id, root }); };
    event("recovery-claimed"); validateOriginalFiles(claim, root);
    if (claim.phase === "recovering") {
      if (claim.action === "completed") clearStoreAuxiliary(claim.record, event); else rollbackStore(claim.record, event);
      claim.final = claim.record.operations.map((operation) => ({ path: operation.path, snapshot: installationSnapshot(operation.path) }));
      claim.phase = "cleanup"; validateFinal(claim); publishClaim(claim, root, state); event("recovery-resources-cleaned");
    }
    finishCleanup(claim, root, state, event);
    return { recovered: true, action: claim.action };
  } catch (error) {
    if (error instanceof InstallationError && ["installation-busy", "store-initialization-conflict"].includes(error.code)) throw error;
    throw failure(error.message);
  }
}
