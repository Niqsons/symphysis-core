import fs from "node:fs";
import path from "node:path";
import { randomUUID } from "node:crypto";
import { planManagedInstall, finishManagedInstallation } from "./managed-install.js";
import { applyInstallationPlan } from "./installation-transaction.js";
import { InstallationError, installationHash, prepareInstallationPlan, installationPath } from "./installation-plan.js";

const fail = (message) => { throw new InstallationError("installation-review-invalid", message); };
const object = (value) => value !== null && typeof value === "object" && !Array.isArray(value);
const strings = (value) => Array.isArray(value) && value.every((item) => typeof item === "string" && item && !item.includes("\0"));
const allowedKeys = (value, allowed) => object(value) && Object.keys(value).every((key) => allowed.includes(key));

function requestFor(project, options) {
  const scope = options.scope ?? "local";
  if (!["local", "global"].includes(scope) || scope === "global" && project != null) fail("Global review не выбирает --project/store");
  const request = { scope, project: scope === "global" ? null : path.resolve(project ?? process.cwd()), clients: options.clients ?? [], skillsDirs: options.skillsDirs ?? [], agentsDirs: options.agentsDirs ?? [], profile: options.profile ?? null };
  if (![request.clients, request.skillsDirs, request.agentsDirs].every(strings) || !(request.profile === null || ["core", "custom"].includes(request.profile))) fail("Некорректные параметры installation review");
  return request;
}

function describe(prepared) {
  const data = prepared.plan.ready ? prepareInstallationPlan(prepared.plan) : null;
  const normalizedManifestHash = data ? installationHash(Buffer.from(JSON.stringify({ ...data.manifest, generation: null }))) : null;
  return prepared.plan.files.map((operation, index) => ({ ...operation,
    ...(operation.kind === "manifest" ? { afterHash: normalizedManifestHash, generation: "assigned-after-confirmation" } : {}),
    ...(data ? { before: data.operations[index].before } : {}),
  }));
}

/** Review can accept only shipped known predecessors, and never writes product files. */
export function previewInstallation(project, options = {}) {
  const request = requestFor(project, options);
  const prepared = planManagedInstall(request.project ?? undefined, { ...options, ...request, project: undefined, profile: request.profile ?? undefined, reviewKnownPredecessors: true });
  const preview = { format: 1, kind: "symphysis-installation-review", id: randomUUID(), request, root: prepared.root, scope: prepared.scope,
    files: describe(prepared), adoptions: prepared.adoptions, retiredPredecessors: prepared.retiredPredecessors, conflicts: prepared.plan.conflicts, ready: prepared.plan.ready };
  return { preview, prepared };
}

export function parseInstallationReview(value) {
  if (!allowedKeys(value, ["format", "kind", "id", "request", "root", "scope", "files", "adoptions", "retiredPredecessors", "conflicts", "ready"]) || value.format !== 1 || value.kind !== "symphysis-installation-review" || typeof value.id !== "string" || !/^[a-f0-9-]{36}$/.test(value.id) || !allowedKeys(value.request, ["scope", "project", "clients", "skillsDirs", "agentsDirs", "profile"]) || !Array.isArray(value.files) || !Array.isArray(value.adoptions) || !Array.isArray(value.retiredPredecessors) || !Array.isArray(value.conflicts) || typeof value.ready !== "boolean") fail("Неподдерживаемый installation review");
  const request = requestFor(value.request.project, value.request);
  if (JSON.stringify(request) !== JSON.stringify(value.request) || value.scope !== request.scope) fail("Параметры installation review изменены");
  return value;
}

/** The saved JSON supplies observations, never an executable installation capability. */
export function applyInstallationReview(value, options = {}) {
  const original = parseInstallationReview(value);
  if (!options.confirm) fail("После просмотра требуется явный --confirm");
  if (!original.ready || original.conflicts.length) fail("Review содержит конфликты; составь новый после их разрешения");
  const { preview: fresh, prepared } = previewInstallation(original.request.project ?? undefined, { ...options, ...original.request, profile: original.request.profile ?? undefined });
  const comparable = (preview) => JSON.stringify({ ...preview, id: null });
  if (!fresh.ready || comparable(fresh) !== comparable(original)) throw new InstallationError("installation-review-changed", "Файлы, реальные пути, profile, payload или окружение изменились после preview; нужен новый review");
  const result = applyInstallationPlan(prepared.plan, options.transactionOptions);
  return { ...finishManagedInstallation(prepared, result, options), scope: prepared.scope };
}

/** Only explicit --out authorizes a plan file. Existing unrelated files stay intact. */
export function saveReview(file, value) {
  const target = installationPath(path.resolve(file));
  const bytes = Buffer.from(`${JSON.stringify(value, null, 2)}\n`);
  if (fs.existsSync(target)) {
    if (fs.readFileSync(target).equals(bytes)) return target;
    fail("Файл --out уже существует; выбери новый путь для нового preview");
  }
  fs.mkdirSync(path.dirname(target), { recursive: true });
  installationPath(target);
  const fd = fs.openSync(target, "wx", 0o600);
  try { fs.writeFileSync(fd, bytes); fs.fsyncSync(fd); } finally { fs.closeSync(fd); }
  return target;
}
