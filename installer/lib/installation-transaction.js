import fs from "node:fs";
import path from "node:path";
import { randomBytes, randomUUID } from "node:crypto";
import { acquireWriter } from "./runtime-leases.js";
import { InstallationError, assertInstallationSnapshot, installationHash, installationKey, installationPath,
  installationSnapshot, installationOwnedTarget, nonOwnedInstallationTarget, normalizeInstallationRequest,
  prepareInstallationPlan } from "./installation-plan.js";

const exists = (file) => fs.lstatSync(file, { throwIfNoEntry: false }) !== undefined;
const sameIdentity = (stat, wanted) => wanted && String(stat.dev) === wanted.dev && String(stat.ino) === wanted.ino;
const identity = (stat) => ({ dev: String(stat.dev), ino: String(stat.ino) });
const invalid = (message) => new InstallationError("installation-recovery-required", message);
const busy = () => new InstallationError("installation-busy", "Владелец транзакции жив либо не подтверждён; чужие блокировки не снимаются");
const recordPath = (root) => path.join(root, ".install-transaction.json");
const emptyHash = installationHash(Buffer.alloc(0));
const recoveryPath = (root) => path.join(root, ".install-recovery-lock");
const recoveryOwner = Object.freeze({ pid: process.pid, startedAt: Math.floor(Date.now() - process.uptime() * 1000), instance: randomUUID() });

function checkedRead(file) {
  installationPath(file);
  const snapshot = installationSnapshot(file);
  if (snapshot.hash === null) throw invalid("Ожидаемая запись транзакции отсутствует");
  let value;
  const bytes = fs.readFileSync(file);
  try { value = JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(bytes)); } catch { throw invalid("Запись транзакции не является корректным UTF-8 JSON; файл сохранён"); }
  if (installationHash(bytes) !== snapshot.hash) throw invalid("Запись изменилась во время чтения; файл сохранён");
  assertInstallationSnapshot(file, snapshot);
  return { value, snapshot, bytes };
}

/** Journal replacement is atomic; no target file is published before its stage identity is journalled. */
function writeRecord(record, state) {
  const file = recordPath(record.request.root);
  const temp = path.join(record.request.root, `.install-record-${record.id}.tmp`);
  installationPath(file); installationPath(temp);
  if (state.recordSnapshot) assertInstallationSnapshot(file, state.recordSnapshot);
  else if (exists(file)) throw invalid("Есть незавершённая или чужая запись установки");
  const bytes = Buffer.from(`${JSON.stringify(record, null, 2)}\n`);
  const fd = fs.openSync(temp, "wx", 0o600);
  const own = identity(fs.fstatSync(fd));
  try { fs.writeFileSync(fd, bytes); fs.fsyncSync(fd); }
  finally { fs.closeSync(fd); }
  installationPath(temp);
  if (!sameIdentity(fs.lstatSync(temp), own) || installationHash(fs.readFileSync(temp)) !== installationHash(bytes)) throw invalid("Временная запись транзакции была заменена");
  if (state.recordSnapshot) assertInstallationSnapshot(file, state.recordSnapshot);
  else if (exists(file)) throw invalid("Запись транзакции появилась до публикации; чужой файл сохранён");
  fs.renameSync(temp, file);
  state.recordSnapshot = installationSnapshot(file);
}

function removeVerified(file, wantedIdentity, hashes) {
  installationPath(file);
  if (!exists(file)) return false;
  const snapshot = installationSnapshot(file);
  if (!wantedIdentity || !sameIdentity(snapshot.identity, wantedIdentity) || !hashes.includes(snapshot.hash)) throw invalid("Временный или установленный файл изменён; он сохранён");
  assertInstallationSnapshot(file, snapshot);
  fs.unlinkSync(file);
  return true;
}

function ensureParents(file, record, state) {
  installationPath(file);
  const missing = [];
  let folder = path.dirname(file);
  while (!exists(folder)) { missing.push(folder); folder = path.dirname(folder); }
  for (const dir of missing.reverse()) {
    installationPath(dir, { directory: true });
    fs.mkdirSync(dir);
    record.createdDirectories.push({ path: dir, ...identity(fs.lstatSync(dir)) });
    writeRecord(record, state);
  }
}

function safeRename(from, to) {
  installationPath(from); installationPath(to);
  if (exists(to)) throw invalid("Цель атомарной публикации занята; чужой файл сохранён");
  fs.renameSync(from, to);
}

function clearAuxiliary(record, event = () => {}) {
  for (const [index, operation] of record.operations.entries()) {
    if (operation.stage && exists(operation.stage)) { removeVerified(operation.stage, operation.stageIdentity, [operation.afterHash, emptyHash]); event("recovery-stage-removed", index); }
    if (operation.backup && exists(operation.backup)) { removeVerified(operation.backup, operation.before.identity, [operation.before.hash]); event("recovery-backup-removed", index); }
  }
  for (const dir of [...record.createdDirectories].reverse()) {
    installationPath(dir.path, { directory: true });
    const stat = fs.lstatSync(dir.path, { throwIfNoEntry: false });
    if (stat && sameIdentity(stat, dir)) {
      try { fs.rmdirSync(dir.path); } catch (error) { if (!["ENOTEMPTY", "EEXIST", "ENOENT"].includes(error.code)) throw error; }
    }
  }
}

function validateRollback(record) {
  for (const operation of record.operations) {
    const current = installationSnapshot(operation.path);
    const backup = operation.backup ? installationSnapshot(operation.backup) : null;
    if (backup?.hash !== null && backup !== null) {
      if (backup.hash !== operation.before.hash || !sameIdentity(backup.identity, operation.before.identity)) throw invalid("Backup не совпадает с исходными собственными байтами");
      if (current.hash !== null && (current.hash !== operation.afterHash || !sameIdentity(current.identity, operation.stageIdentity))) throw invalid("Файл после сбоя изменён пользователем; восстановление остановлено");
    } else if (operation.before.hash === null) {
      if (current.hash !== null && (current.hash !== operation.afterHash || !sameIdentity(current.identity, operation.stageIdentity))) throw invalid("Новая цель занята чужим файлом после сбоя");
    } else if (current.hash !== operation.before.hash || !sameIdentity(current.identity, operation.before.identity)) throw invalid("Исходный файл и его backup не подтверждены");
    if (operation.stage && exists(operation.stage)) {
      const stage = installationSnapshot(operation.stage);
      if (!sameIdentity(stage.identity, operation.stageIdentity) || ![emptyHash, operation.afterHash].includes(stage.hash)) throw invalid("Stage изменён или не подтверждён; файл сохранён");
    }
  }
}

function rollback(record, event = () => {}) {
  // Validate the whole recovery before changing a single file.
  validateRollback(record);
  for (const [index, operation] of [...record.operations].reverse().entries()) {
    if (operation.backup && exists(operation.backup)) {
      if (exists(operation.path)) { removeVerified(operation.path, operation.stageIdentity, [operation.afterHash]); event("recovery-target-removed", index); }
      safeRename(operation.backup, operation.path);
      event("recovery-backup-restored", index);
    } else if (operation.before.hash === null && exists(operation.path)) removeVerified(operation.path, operation.stageIdentity, [operation.afterHash]);
    if (operation.stage && exists(operation.stage)) { removeVerified(operation.stage, operation.stageIdentity, [emptyHash, operation.afterHash]); event("recovery-stage-removed", index); }
  }
  clearAuxiliary(record, event);
}

function fullyPublished(record) {
  return record.operations.every((operation) => {
    const current = installationSnapshot(operation.path);
    return operation.action === "remove" ? current.hash === null : current.hash === operation.afterHash && sameIdentity(current.identity, operation.stageIdentity);
  });
}

/** Publish owned resources and typed merges coherently, with the manifest as the final target. */
export function applyInstallationPlan(plan, { fault = undefined } = {}) {
  const data = prepareInstallationPlan(plan);
  const pending = recordPath(data.request.root);
  if (exists(pending)) throw invalid("Установка не завершена; сначала явно восстанови её транзакцию");
  const changed = data.operations.filter((operation) => operation.action !== "unchanged");
  if (!changed.length) return { manifest: data.manifest, generation: data.manifest.generation, written: [], unchanged: data.operations.map((operation) => operation.path) };
  const writer = acquireWriter({ root: data.request.root, generation: data.previous?.generation ?? null });
  let keepLock = false;
  let record;
  const state = { recordSnapshot: null };
  const event = (name, index) => { if (fault) fault({ name, index, id: data.id, root: data.request.root }); };
  try {
    prepareInstallationPlan(plan);
    record = { format: 1, kind: "installation", id: data.id, owner: writer.descriptor, request: data.request, previousRequest: data.previousRequest,
      generation: data.manifest.generation, phase: "staging", createdDirectories: [], operations: changed.map((operation, index) => ({
        path: operation.path, ...(operation.source ? { source: operation.source, purpose: operation.purpose } : { kind: operation.kind }),
        ...(operation.projection ? { projection: true } : {}), ...(operation.clientId ? { clientId: operation.clientId } : {}), ...(operation.predecessor ? { predecessor: true } : {}),
        action: operation.action, owned: operation.owned, before: operation.before, afterHash: operation.afterHash,
        stage: operation.afterHash === null ? null : path.join(path.dirname(operation.path), `.symphysis-install-${data.id}-${index}.stage`),
        backup: operation.before.hash === null ? null : path.join(path.dirname(operation.path), `.symphysis-install-${data.id}-${index}.backup`), stageIdentity: null,
      })) };
    writeRecord(record, state);
    event("journal", -1);
    for (let index = 0; index < changed.length; index++) {
      const operation = record.operations[index];
      ensureParents(operation.path, record, state);
      if (operation.stage) {
        installationPath(operation.stage);
        const fd = fs.openSync(operation.stage, "wx", 0o600);
        operation.stageIdentity = identity(fs.fstatSync(fd));
        try {
          writeRecord(record, state);
          event("stage-open", index);
          fs.writeFileSync(fd, changed[index].bytes);
          fs.fsyncSync(fd);
        } finally { fs.closeSync(fd); }
        if (installationSnapshot(operation.stage).hash !== operation.afterHash) throw invalid("Stage не совпадает с проверенными байтами payload");
        event("stage-written", index);
      }
    }
    prepareInstallationPlan(plan);
    record.phase = "publishing";
    writeRecord(record, state);
    for (let index = 0; index < record.operations.length; index++) {
      const operation = record.operations[index];
      assertInstallationSnapshot(operation.path, operation.before);
      if (operation.backup) {
        safeRename(operation.path, operation.backup);
        event("backup-renamed", index);
      }
      if (operation.stage) {
        const stage = installationSnapshot(operation.stage);
        if (!sameIdentity(stage.identity, operation.stageIdentity) || stage.hash !== operation.afterHash) throw invalid("Stage изменился перед публикацией");
        safeRename(operation.stage, operation.path);
      }
      event("target-renamed", index);
      writeRecord(record, state);
    }
    record.phase = "committed";
    writeRecord(record, state);
    event("manifest-published", record.operations.length - 1);
    clearAuxiliary(record);
    finishOwnedTransaction(record, state, writer, "completed", event);
    return { manifest: data.manifest, generation: data.manifest.generation, written: changed.map((operation) => operation.path), unchanged: data.operations.filter((operation) => operation.action === "unchanged").map((operation) => operation.path) };
  } catch (error) {
    if (record && state.recordSnapshot) {
      try {
        if (record.phase === "committed") throw invalid("Manifest опубликован, требуется явное завершение cleanup");
        assertInstallationSnapshot(pending, state.recordSnapshot);
        rollback(record);
        finishOwnedTransaction(record, state, writer, "rolled-back", event);
      } catch (rollbackError) {
        keepLock = true;
        throw Object.assign(invalid(`Транзакция сохранена для явного восстановления: ${rollbackError.message}`), { cause: error });
      }
    }
    throw error;
  } finally { if (!keepLock) writer.release(); }
}

function validateRecovery(record, root, lock) {
  if (!record || record.format !== 1 || record.kind !== "installation" || !/^[a-f0-9-]{36}$/.test(record.id ?? "") || typeof record.generation !== "string" || !record.generation || !["staging", "publishing", "committed"].includes(record.phase) || !Array.isArray(record.operations) || !Array.isArray(record.createdDirectories)) throw invalid("Запись восстановления не поддерживается");
  const request = normalizeInstallationRequest(record.request);
  if (installationKey(request.root) !== installationKey(root)) throw invalid("Транзакция принадлежит другому management root");
  const previousRequest = record.previousRequest ? normalizeInstallationRequest(record.previousRequest) : request;
  if (previousRequest.scope !== request.scope || installationKey(previousRequest.root) !== installationKey(root) || installationKey(previousRequest.runtimeRoot) !== installationKey(request.runtimeRoot)) throw invalid("Исходная поставка транзакции не совпадает с выбранным root");
  if (!record.owner || installationKey(record.owner.file ?? "") !== installationKey(path.join(root, ".install-lock"))) throw invalid("Транзакция не подтверждает свой writer lock");
  if (!lock || lock.format !== 1 || lock.kind !== "writer" || !Number.isSafeInteger(lock.pid) || lock.pid <= 0 || !Number.isSafeInteger(lock.startedAt) || lock.startedAt <= 0 || !/^[a-f0-9-]{36}$/.test(lock.id ?? "") || !/^[a-f0-9-]{36}$/.test(lock.instance ?? "") || !/^[a-f0-9]{64}$/.test(lock.token ?? "") || !(lock.generation === null || (typeof lock.generation === "string" && lock.generation))) throw invalid("Writer lock не поддерживается");
  for (const key of ["id", "generation", "token", "pid", "startedAt", "instance"]) if (lock[key] !== record.owner[key] || lock[key] === undefined) throw invalid("Writer lock и транзакция имеют разных владельцев");
  const selected = new Set();
  let manifests = 0;
  for (let index = 0; index < record.operations.length; index++) {
    const operation = record.operations[index];
    const target = installationPath(operation.path);
    let expected;
    if (operation.kind === "manifest") { expected = path.join(root, "install-manifest.json"); manifests++; if (index !== record.operations.length - 1) throw invalid("Manifest не является последней публикацией"); }
    else expected = operation.owned ? installationOwnedTarget(operation.action === "remove" && !operation.predecessor ? previousRequest : request, { ...operation, sha256: operation.afterHash ?? operation.before?.hash }) : nonOwnedInstallationTarget(request, operation);
    if (operation.predecessor !== undefined && (operation.predecessor !== true || !operation.owned || operation.action !== "remove")) throw invalid("Predecessor разрешён только для удаления явно принятого прежнего ресурса");
    if (installationKey(expected) !== installationKey(target) || selected.has(installationKey(target))) throw invalid("Транзакция содержит постороннюю/повторную цель");
    selected.add(installationKey(target));
    if (!operation.before || !Array.isArray(operation.before.ancestors) || !["create", "replace", "remove"].includes(operation.action) || !(operation.before.hash === null || /^[a-f0-9]{64}$/.test(operation.before.hash)) || !(operation.afterHash === null || /^[a-f0-9]{64}$/.test(operation.afterHash))) throw invalid("Транзакция не подтверждает исходные и конечные хеши");
    const stage = operation.afterHash === null ? null : path.join(path.dirname(target), `.symphysis-install-${record.id}-${index}.stage`);
    const backup = operation.before.hash === null ? null : path.join(path.dirname(target), `.symphysis-install-${record.id}-${index}.backup`);
    if (operation.stage !== stage || operation.backup !== backup) throw invalid("Пути stage/backup не выводятся из собственной операции");
    if (stage) installationPath(stage);
    if (backup) installationPath(backup);
  }
  if (manifests !== 1) throw invalid("Нет единственной публикации manifest");
  for (const dir of record.createdDirectories) {
    installationPath(dir.path, { directory: true });
    if (path.resolve(dir.path) === path.parse(path.resolve(dir.path)).root) throw invalid("Корень диска не является временным каталогом транзакции");
    if (!record.operations.some((operation) => {
      const relative = path.relative(dir.path, path.dirname(operation.path));
      return relative === "" || (relative !== ".." && !relative.startsWith(`..${path.sep}`) && !path.isAbsolute(relative));
    })) throw invalid("Запись содержит посторонний временный каталог");
  }
  return request;
}

function ownerDefinitelyDead(pid) {
  try { process.kill(pid, 0); return false; }
  catch (error) { return error.code === "ESRCH"; }
}

function validateAuxiliary(record) {
  for (const operation of record.operations) {
    for (const [file, wanted, hashes] of [[operation.stage, operation.stageIdentity, [operation.afterHash, emptyHash]], [operation.backup, operation.before.identity, [operation.before.hash]]]) {
      if (!file || !exists(file)) continue;
      const snapshot = installationSnapshot(file);
      if (!wanted || !sameIdentity(snapshot.identity, wanted) || !hashes.includes(snapshot.hash)) throw invalid("Временный файл recovery изменён; файл сохранён");
    }
  }
}

function savedRead(read) { return { bytes: read.bytes.toString("base64"), snapshot: read.snapshot }; }
function newClaim(recordRead, lockRead, action) {
  return { format: 1, kind: "recovery", id: randomUUID(), owner: { id: randomUUID(), token: randomBytes(32).toString("hex"), ...recoveryOwner },
    transaction: recordRead.value, writer: { ...savedRead(lockRead), value: lockRead.value }, pending: savedRead(recordRead),
    action, phase: "recovering", final: null };
}
function validateSavedRead(saved, value) {
  if (!saved || typeof saved.bytes !== "string" || !saved.snapshot || !/^[a-f0-9]{64}$/.test(saved.snapshot.hash ?? "") || !saved.snapshot.identity || !Array.isArray(saved.snapshot.ancestors)) throw invalid("Recovery не содержит полного снимка исходной записи");
  const bytes = Buffer.from(saved.bytes, "base64");
  if (bytes.toString("base64") !== saved.bytes || installationHash(bytes) !== saved.snapshot.hash) throw invalid("Хеш исходной записи recovery не совпал");
  let parsed;
  try { parsed = JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(bytes)); } catch { throw invalid("Исходная запись recovery не является допустимым JSON"); }
  if (JSON.stringify(parsed) !== JSON.stringify(value)) throw invalid("Снимок recovery не соответствует сохранённой транзакции/владельцу");
}

function expectedFinal(operation, action) {
  return action === "completed" ? { hash: operation.afterHash, identity: operation.afterHash === null ? null : operation.stageIdentity } : { hash: operation.before.hash, identity: operation.before.identity };
}

function validateFinal(claim) {
  if (!Array.isArray(claim.final) || claim.final.length !== claim.transaction.operations.length) throw invalid("Recovery не содержит полного подтверждения завершённых файлов");
  for (const [index, operation] of claim.transaction.operations.entries()) {
    const entry = claim.final[index];
    const expected = expectedFinal(operation, claim.action);
    if (!entry || installationKey(entry.path) !== installationKey(operation.path) || !entry.snapshot || entry.snapshot.hash !== expected.hash || Boolean(entry.snapshot.identity) !== Boolean(expected.identity) || (expected.identity && !sameIdentity(entry.snapshot.identity, expected.identity))) throw invalid("Финальный снимок recovery не соответствует выбранному исходу");
    assertInstallationSnapshot(operation.path, entry.snapshot);
    if ((operation.stage && exists(operation.stage)) || (operation.backup && exists(operation.backup))) throw invalid("После подтверждённого cleanup появились временные файлы; они сохранены");
  }
}

function validateClaim(claim, root, ownIdentity) {
  if (!claim || claim.format !== 1 || claim.kind !== "recovery" || !/^[a-f0-9-]{36}$/.test(claim.id ?? "") || !["recovering", "cleanup", "writer-removed", "pending-removed"].includes(claim.phase) || !["completed", "rolled-back"].includes(claim.action)) throw invalid("Recovery claim не поддерживается; запись сохранена");
  const owner = claim.owner;
  if (!claim.fileIdentity || !sameIdentity(ownIdentity, claim.fileIdentity)) throw invalid("Файл recovery claim заменён; чужая копия сохранена");
  if (!owner || !Number.isSafeInteger(owner.pid) || owner.pid <= 0 || !Number.isSafeInteger(owner.startedAt) || owner.startedAt <= 0 || !/^[a-f0-9-]{36}$/.test(owner.instance ?? "") || !/^[a-f0-9-]{36}$/.test(owner.id ?? "") || !/^[a-f0-9]{64}$/.test(owner.token ?? "")) throw invalid("Владелец recovery не подтверждён");
  validateSavedRead(claim.pending, claim.transaction);
  validateSavedRead(claim.writer, claim.writer?.value);
  const request = validateRecovery(claim.transaction, root, claim.writer.value);
  if (claim.phase === "recovering") {
    if (claim.final !== null) throw invalid("Незавершённый recovery содержит неподтверждённый финальный снимок");
  } else validateFinal(claim);
  return request;
}

function validateRecoveryFiles(claim, root) {
  const pending = recordPath(root);
  const writer = path.join(root, ".install-lock");
  const hasPending = exists(pending);
  const hasWriter = exists(writer);
  if (hasWriter) assertInstallationSnapshot(writer, claim.writer.snapshot);
  if (hasPending) assertInstallationSnapshot(pending, claim.pending.snapshot);
  if (claim.phase === "recovering" && (!hasPending || !hasWriter)) throw invalid("Рабочая фаза recovery потеряла исходные записи");
  if (hasWriter && !hasPending) throw invalid("Writer остался без подтверждённого журнала recovery");
  if (["writer-removed", "pending-removed"].includes(claim.phase) && hasWriter) throw invalid("После cleanup появился writer lock; запись сохранена");
  if (claim.phase === "pending-removed" && hasPending) throw invalid("После cleanup появился журнал установки; запись сохранена");
}

/** Atomic updates keep the previous complete claim on disk until the next phase is durable. */
function publishClaim(claim, root, state) {
  const file = recoveryPath(root);
  const temp = path.join(root, `.install-recovery-${claim.id}.tmp`);
  installationPath(file); installationPath(temp);
  if (state.snapshot) assertInstallationSnapshot(file, state.snapshot);
  const target = state.snapshot ? temp : file;
  let fd;
  try { fd = fs.openSync(target, "wx", 0o600); } catch (error) { if (error.code === "EEXIST") throw busy(); throw error; }
  const own = identity(fs.fstatSync(fd));
  claim.fileIdentity = own;
  const bytes = Buffer.from(`${JSON.stringify(claim, null, 2)}\n`);
  try { fs.writeFileSync(fd, bytes); fs.fsyncSync(fd); } finally { fs.closeSync(fd); }
  const snapshot = installationSnapshot(target);
  if (!sameIdentity(snapshot.identity, own) || snapshot.hash !== installationHash(bytes)) throw invalid("Запись recovery заменена при публикации; файл сохранён");
  if (state.snapshot) {
    assertInstallationSnapshot(file, state.snapshot);
    fs.renameSync(temp, file);
  }
  state.snapshot = installationSnapshot(file);
}

function validateRecoveryEnvironment(root) {
  const readers = path.join(root, ".leases");
  installationPath(readers, { directory: true });
  if (exists(readers) && fs.readdirSync(readers).length) throw busy();
  if (fs.readdirSync(root).some((name) => /^\.install-(?:record|recovery)-.*\.tmp$/.test(name))) throw invalid("Есть неподтверждённая временная запись журнала; она сохранена");
}

/** Shared by a live owned transaction and a later ESRCH-confirmed recovery. */
function finishCleanup(claim, root, state, event, releaseWriter = null) {
  const file = recordPath(root);
  const lockFile = path.join(root, ".install-lock");
  validateFinal(claim);
  validateRecoveryFiles(claim, root);
  if (exists(lockFile)) {
    assertInstallationSnapshot(lockFile, claim.writer.snapshot);
    if (releaseWriter) releaseWriter();
    else fs.unlinkSync(lockFile);
    event("recovery-writer-unlinked");
  }
  claim.phase = "writer-removed";
  publishClaim(claim, root, state);
  event("recovery-writer-recorded");
  if (exists(file)) {
    assertInstallationSnapshot(file, claim.pending.snapshot);
    fs.unlinkSync(file);
    event("recovery-pending-unlinked");
  }
  claim.phase = "pending-removed";
  publishClaim(claim, root, state);
  event("recovery-pending-recorded");
  validateFinal(claim);
  validateRecoveryFiles(claim, root);
  assertInstallationSnapshot(recoveryPath(root), state.snapshot);
  fs.unlinkSync(recoveryPath(root));
  event("recovery-claim-unlinked");
}

function finishOwnedTransaction(record, state, writer, action, event) {
  const root = record.request.root;
  validateRecoveryEnvironment(root);
  assertInstallationSnapshot(recordPath(root), state.recordSnapshot);
  const recordRead = checkedRead(recordPath(root));
  const lockRead = checkedRead(writer.file);
  validateRecovery(recordRead.value, root, lockRead.value);
  const claim = newClaim(recordRead, lockRead, action);
  claim.final = record.operations.map((operation) => ({ path: operation.path, snapshot: installationSnapshot(operation.path) }));
  claim.phase = "cleanup";
  validateFinal(claim);
  const claimState = { snapshot: null };
  publishClaim(claim, root, claimState);
  event("cleanup-receipt-published", -1);
  finishCleanup(claim, root, claimState, (name, index = -1) => event(name.replace(/^recovery-/, "cleanup-"), index), () => writer.release());
}

/** Explicit repeatable recovery; only ESRCH permits takeover, never a present/reused PID. */
export function recoverInstallation({ root: requestedRoot, scope } = {}, { fault } = {}) {
  const root = installationPath(requestedRoot, { directory: true });
  const file = recordPath(root);
  const lockFile = path.join(root, ".install-lock");
  const claimFile = recoveryPath(root);
  if (!exists(root)) return { recovered: false };
  validateRecoveryEnvironment(root);
  if (!exists(file) && !exists(lockFile) && !exists(claimFile)) return { recovered: false };
  let claim;
  let request;
  const state = { snapshot: null };
  try {
    if (exists(claimFile)) {
      const read = checkedRead(claimFile);
      claim = read.value;
      request = validateClaim(claim, root, read.snapshot.identity);
      if (!ownerDefinitelyDead(claim.owner.pid)) throw busy();
      if (!ownerDefinitelyDead(claim.writer.value.pid)) throw busy();
      validateRecoveryFiles(claim, root);
      if (claim.phase === "recovering") {
        if (claim.action === "completed") { if (!fullyPublished(claim.transaction)) throw invalid("Завершённые файлы изменены после сбоя recovery"); validateAuxiliary(claim.transaction); }
        else validateRollback(claim.transaction);
      }
      state.snapshot = read.snapshot;
    } else {
      if (!exists(file) || !exists(lockFile)) throw busy();
      const recordRead = checkedRead(file);
      const lockRead = checkedRead(lockFile);
      request = validateRecovery(recordRead.value, root, lockRead.value);
      if (!ownerDefinitelyDead(lockRead.value.pid)) throw busy();
      const complete = fullyPublished(recordRead.value);
      if (recordRead.value.phase === "committed" && !complete) throw invalid("Файлы опубликованного поколения изменены после commit; пользовательское состояние сохранено");
      if (complete) validateAuxiliary(recordRead.value); else validateRollback(recordRead.value);
      claim = newClaim(recordRead, lockRead, complete ? "completed" : "rolled-back");
      assertInstallationSnapshot(file, recordRead.snapshot);
      assertInstallationSnapshot(lockFile, lockRead.snapshot);
    }
    if (scope !== undefined && scope !== request.scope) throw invalid("Scope восстановления не совпадает с транзакцией");
    claim.owner = { id: randomUUID(), token: randomBytes(32).toString("hex"), ...recoveryOwner };
    publishClaim(claim, root, state);
    const event = (name, index = -1) => { if (fault) fault({ name, index, id: claim.id, root }); };
    event("recovery-claimed");
    validateRecoveryFiles(claim, root);
    if (claim.phase === "recovering") {
      if (claim.action === "completed") clearAuxiliary(claim.transaction, event);
      else rollback(claim.transaction, event);
      claim.final = claim.transaction.operations.map((operation) => ({ path: operation.path, snapshot: installationSnapshot(operation.path) }));
      claim.phase = "cleanup";
      validateFinal(claim);
      publishClaim(claim, root, state);
      event("recovery-resources-cleaned");
    }
    finishCleanup(claim, root, state, event);
    return { recovered: true, action: claim.action, generation: claim.action === "completed" ? claim.transaction.generation : null };
  } catch (error) {
    if (error instanceof InstallationError && ["installation-busy", "installation-recovery-required"].includes(error.code)) throw error;
    throw invalid(error.message);
  }
}

// Internal filesystem primitives for the store-init dialect. Its caller must
// validate every typed target, record and owner before passing a record here;
// this is not a public JSON-plan or transaction execution API.
export const _transactionFileOps = Object.freeze({ checkedRead, removeVerified, safeRename, rollback, validateRollback,
  clearAuxiliary, fullyPublished, validateAuxiliary, savedRead, validateSavedRead, expectedFinal, ownerDefinitelyDead });
