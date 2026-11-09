import fs from "node:fs";
import path from "node:path";
import { randomBytes, randomUUID } from "node:crypto";
import { isFullyAbsolute } from "./paths.js";

const PROCESS = Object.freeze({
  pid: process.pid,
  startedAt: Math.floor(Date.now() - process.uptime() * 1000),
  instance: randomUUID(),
});
const sameFile = (first, second) => first.dev === second.dev && first.ino === second.ino;

export class LeaseError extends Error {
  constructor(code, message) {
    super(message);
    this.name = "LeaseError";
    this.code = code;
    this.exitCode = 2;
  }
}

const busy = () => new LeaseError("installation-busy", "Поставка занята или содержит неподтверждённую блокировку; заверши активную операцию либо явно проверь восстановление");
const invalid = (message) => new LeaseError("lease-invalid", message);
const unsafe = () => new LeaseError("lease-path-invalid", "Путь блокировки проходит через ссылку/reparse или неподходящий тип файла");

/** Check every existing component, including Windows junctions. Never follow a link. */
function checkedPath(target, { directory = false, create = false } = {}) {
  if (!isFullyAbsolute(target)) throw unsafe();
  const resolved = path.resolve(target);
  let current = path.parse(resolved).root;
  const parts = resolved.slice(current.length).split(path.sep).filter(Boolean);
  for (let index = 0; index < parts.length; index++) {
    current = path.join(current, parts[index]);
    let stat = fs.lstatSync(current, { throwIfNoEntry: false });
    const needsDirectory = index < parts.length - 1 || directory;
    if (!stat && create && needsDirectory) {
      try { fs.mkdirSync(current); } catch (error) { if (error.code !== "EEXIST") throw error; }
      stat = fs.lstatSync(current, { throwIfNoEntry: false });
    }
    if (stat?.isSymbolicLink() || (stat && needsDirectory && !stat.isDirectory())) throw unsafe();
    if (!stat) break;
  }
  return resolved;
}

function lockExists(root) {
  const file = checkedPath(path.join(root, ".install-lock"));
  return fs.lstatSync(file, { throwIfNoEntry: false }) !== undefined;
}

/** Incomplete management state is never silently removed or treated as ready. */
export function pendingManagementState(root, { includeWriter = true } = {}) {
  if (!fs.statSync(root, { throwIfNoEntry: false })?.isDirectory()) return false;
  return fs.readdirSync(root).some((name) => (includeWriter && name === ".install-lock") || [".install-transaction.json", ".install-recovery-lock", ".store-init-transaction.json", ".store-init-recovery.json", ".migration-transaction.json", ".migration-recovery.json"].includes(name) || /^\.(?:install|store-init|migration)-(?:record|recovery)-.+\.tmp$/.test(name));
}

/** Only our original inode and exact record bytes may be removed. */
function removeOwn(file, identity, bytes) {
  checkedPath(file);
  const stat = fs.lstatSync(file, { throwIfNoEntry: false });
  if (!stat) return false;
  if (!stat.isFile() || !sameFile(stat, identity)) throw invalid("Запись блокировки заменена; чужой файл сохранён");
  const fd = fs.openSync(file, fs.constants.O_RDONLY | (fs.constants.O_NOFOLLOW ?? 0));
  try {
    if (!sameFile(fs.fstatSync(fd), identity) || (bytes !== null && !fs.readFileSync(fd).equals(bytes))) throw invalid("Владелец или содержимое блокировки изменились; запись сохранена");
  } finally { fs.closeSync(fd); }
  checkedPath(file);
  const current = fs.lstatSync(file, { throwIfNoEntry: false });
  if (!current || !current.isFile() || !sameFile(current, identity)) throw invalid("Запись блокировки изменилась перед освобождением; запись сохранена");
  fs.unlinkSync(file);
  return true;
}

function createRecord(file, kind, generation, id = randomUUID()) {
  checkedPath(file);
  let fd;
  try { fd = fs.openSync(file, "wx", 0o600); }
  catch (error) { if (error.code === "EEXIST") throw busy(); throw error; }
  const identity = fs.fstatSync(fd);
  const record = { format: 1, kind, id, token: randomBytes(32).toString("hex"), generation, ...PROCESS };
  const bytes = Buffer.from(`${JSON.stringify(record)}\n`, "utf8");
  try {
    fs.writeFileSync(fd, bytes);
  } catch (error) {
    fs.closeSync(fd);
    removeOwn(file, identity, null);
    throw error;
  }
  fs.closeSync(fd);
  try { checkedPath(file); }
  catch (error) { removeOwn(file, identity, bytes); throw error; }
  let released = false;
  return {
    id: record.id, file, generation,
    descriptor: Object.freeze({ file, id: record.id, generation, token: record.token, ...PROCESS }),
    release() {
      if (released) return false;
      const removed = removeOwn(file, identity, bytes);
      released = true;
      return removed;
    },
  };
}

/** The directory containing the install manifest owns management state. */
export function managementRoot(context) {
  const runtime = context?.runtime;
  if (!runtime || !isFullyAbsolute(runtime.root)) throw invalid("Нет проверенного runtime для lease");
  if (runtime.manifestPath) {
    if (!isFullyAbsolute(runtime.manifestPath) || path.basename(runtime.manifestPath) !== "install-manifest.json") throw invalid("Неверный путь manifest для lease");
    return path.dirname(runtime.manifestPath);
  }
  if (!runtime.legacy || context.scope !== "local" || !isFullyAbsolute(context.store?.root)) throw invalid("Отсутствует manifest управляемой поставки");
  return path.relative(context.store.root, runtime.root) === "" ? path.join(runtime.root, ".symphysis") : runtime.root;
}

function verifyGeneration(context) {
  const runtime = context.runtime;
  if (typeof runtime.generation !== "string" || !runtime.generation) throw invalid("Неизвестно поколение runtime для lease");
  if (!runtime.manifestPath) return;
  checkedPath(runtime.manifestPath);
  let manifest;
  try { manifest = JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(fs.readFileSync(runtime.manifestPath))); }
  catch { throw invalid("Manifest изменился либо недоступен перед запуском инструмента"); }
  if (manifest.format !== 1 || manifest.scope !== context.scope || manifest.generation !== runtime.generation) throw invalid("Поколение поставки изменилось; повтори разрешение runtime");
}

/** Discovery has no lease. The dispatcher keeps this reader until its child exits. */
export function acquireReader(context) {
  if (context?.status !== "ready") throw invalid("Нельзя запустить инструмент без успешного preflight");
  const root = checkedPath(managementRoot(context), { directory: true, create: true });
  if (pendingManagementState(root)) throw busy();
  verifyGeneration(context);
  const directory = checkedPath(path.join(root, ".leases"), { directory: true, create: true });
  const id = randomUUID();
  const lease = createRecord(path.join(directory, `${id}.json`), "reader", context.runtime.generation, id);
  try {
    if (pendingManagementState(root)) throw busy();
    verifyGeneration(context);
    return lease;
  } catch (error) { lease.release(); throw error; }
}

/** A writer publishes its lock before checking readers; no stale record is pruned. */
export function acquireWriter({ root: requestedRoot, generation = null } = {}) {
  if (!isFullyAbsolute(requestedRoot) || path.resolve(requestedRoot) === path.parse(path.resolve(requestedRoot)).root) throw invalid("Нужен отдельный абсолютный management root");
  const root = checkedPath(requestedRoot, { directory: true, create: true });
  if (pendingManagementState(root)) throw busy();
  const lock = createRecord(path.join(root, ".install-lock"), "writer", generation);
  try {
    if (pendingManagementState(root, { includeWriter: false })) throw busy();
    const directory = checkedPath(path.join(root, ".leases"), { directory: true });
    const stat = fs.lstatSync(directory, { throwIfNoEntry: false });
    // Even malformed, foreign and apparently dead records need explicit recovery.
    if (stat && fs.readdirSync(directory).length) throw busy();
    return lock;
  } catch (error) { lock.release(); throw error; }
}
