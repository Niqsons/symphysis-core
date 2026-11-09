import fs from "node:fs";
import path from "node:path";
import { randomUUID } from "node:crypto";
import { resolveMigrationContext, LEGACY_TOOL_FILES } from "./runtime-resolver.js";
import { planManagedInstall } from "./managed-install.js";
import { planPlanningConfig } from "./planning-config.js";
import { InstallationError, installationHash, installationKey, installationSnapshot,
  normalizeInstallationRequest, readInstallationManifest, prepareInstallationPlan, installationPath } from "./installation-plan.js";
import { createLegacySourceProof, legacySourceEvidence } from "./legacy-source-proof.js";

const previews = new WeakMap();
const fail = (message) => { throw new InstallationError("migration-plan-invalid", message); };
const object = (value) => value !== null && typeof value === "object" && !Array.isArray(value);
const keys = (value, allowed) => object(value) && Object.keys(value).every((key) => allowed.includes(key));
const strings = (value) => Array.isArray(value) && value.every((item) => typeof item === "string" && item && !item.includes("\0"));
const issue = (code, message, action = "Разреши конфликт и составь новый preview") => ({ code, message, action });

function checkedManifest(context) {
  if (!context?.runtime?.manifestPath) return null;
  const file = context.runtime.manifestPath;
  const raw = JSON.parse(fs.readFileSync(file, "utf8"));
  const request = normalizeInstallationRequest({ ...raw, root: path.dirname(file) });
  const manifest = readInstallationManifest(file, request);
  if (manifest.generation !== context.runtime.generation) fail("Поколение manifest изменилось при составлении preview");
  return { file, manifest, request };
}

function removalProof(source) {
  const selected = checkedManifest(source);
  if (!selected || source.scope !== "local") return undefined;
  const files = selected.manifest.files.filter((file) => file.source.startsWith("openspec/schemas/symphysis/")).map((file) => ({ path: file.path, sha256: file.sha256, snapshot: installationSnapshot(file.path) }));
  return { root: source.runtime.schemaRoot, manifestPath: selected.file, generation: selected.manifest.generation, files };
}

function requestFor(options) {
  const request = { project: path.resolve(options.project ?? process.cwd()), store: options.store ?? null, to: options.to,
    clients: options.clients ?? [], skillsDirs: options.skillsDirs ?? [], agentsDirs: options.agentsDirs ?? [], profile: options.profile ?? null };
  if (!["local", "global"].includes(request.to) || !(request.store === null || typeof request.store === "string" && request.store && !request.store.includes("\0")) || ![request.clients, request.skillsDirs, request.agentsDirs].every(strings) || !(request.profile === null || ["core", "custom"].includes(request.profile))) fail("Некорректные параметры preview миграции");
  if (request.clients.some((id) => !["claude", "codex", "opencode"].includes(id)) || (request.clients.length > 1 && (request.skillsDirs.length || request.agentsDirs.length))) fail("Неизвестный клиент либо неоднозначные legacy overrides миграции");
  return request;
}

const observation = (file, extra = {}) => ({ path: file, snapshot: installationSnapshot(file), ...extra });
function blueprint(operation, data) {
  // A new local generation is assigned only to the opaque apply plan. Its
  // deterministic blueprint binds every other manifest field before confirm.
  const afterHash = operation.kind === "manifest" ? installationHash(Buffer.from(JSON.stringify({ ...data.manifest, generation: null }))) : operation.afterHash;
  return { path: operation.path, ...(operation.source ? { source: operation.source } : { kind: operation.kind }), action: operation.action, ownership: operation.owned ? "target-managed" : "project-data",
    before: operation.before, afterHash, ...(operation.kind === "manifest" ? { generation: "assigned-after-confirmation" } : {}) };
}

/** A preview observes only the selected store and explicit managed roots. */
export function previewMigration(options = {}) {
  const request = requestFor(options);
  let legacy = null;
  const resolution = resolveMigrationContext({ project: request.project, ...(request.store ? { store: request.store } : {}), to: request.to,
    ...(options.env ? { env: options.env } : {}), ...(options.run ? { run: options.run } : {}), schemaRemovalProof: (source) => {
      if (source.runtime?.manifestPath) return removalProof(source);
      legacy = createLegacySourceProof(source, { clients: request.clients, skillsDirs: request.skillsDirs.map((directory) => path.resolve(request.project, directory)), agentsDirs: request.agentsDirs.map((directory) => path.resolve(request.project, directory)),
        ...(options.env ? { env: options.env } : {}), ...(options.payloadDir ? { payloadDir: options.payloadDir } : {}) });
      return legacy.proof;
    } });
  const source = resolution.sourceContext;
  const candidate = resolution.candidateContext;
  const conflicts = [...resolution.diagnostics];
  if (legacy && !legacy.ready) conflicts.push(...legacy.conflicts);
  const warnings = [...(source?.warnings ?? []), ...(candidate?.warnings ?? [])];
  const files = [];
  const observed = [];
  let sourceInstallation = null;
  let targetInstallation = null;
  let preparedLocal = null;
  let preparedLocalPlan = null;
  let operations = [];
  if (source?.runtime?.legacy && resolution.planningRoot && installationKey(source.runtime.root) === installationKey(resolution.planningRoot.root)) {
    const canonicalMap = path.join(resolution.planningRoot.root, ".symphysis", "tools", "journal-roots.json");
    try {
      installationPath(canonicalMap);
      if (fs.lstatSync(canonicalMap, { throwIfNoEntry: false })) conflicts.push(issue("migration-roots-layout-ambiguous", "Flat legacy читает карту из tools/, а после перехода активируется уже существующая canonical карта", "Явно выбери расположение личной карты и повтори preview; содержимое карт не читается и не сливается"));
    } catch (error) { conflicts.push(issue("migration-roots-layout-ambiguous", error.message)); }
  }
  if (source?.runtime && source.scope === "local" && resolution.planningRoot && installationKey(source.runtime.root) !== installationKey(resolution.planningRoot.root)) {
    for (const name of LEGACY_TOOL_FILES) {
      const target = path.join(resolution.planningRoot.root, "tools", name);
      try {
        installationPath(target);
        if (fs.lstatSync(target, { throwIfNoEntry: false })) conflicts.push(issue("migration-other-local-copy", `${target}: кроме выбранной поставки остаётся flat legacy runtime`, "Явно разреши вторую локальную копию и повтори preview; она не удаляется по имени"));
      } catch (error) { conflicts.push(issue("migration-other-local-copy", `${target}: ${error.message}`)); }
    }
  }
  try {
    sourceInstallation = checkedManifest(source);
    if (!sourceInstallation && legacy?.ready) {
      const evidence = legacySourceEvidence(legacy.proof, source);
      if (!evidence) fail("Known legacy proof изменился при составлении preview");
      sourceInstallation = { file: null, legacy: true, evidence, manifest: { scope: "local", generation: evidence.generation, clients: evidence.clients, files: evidence.files } };
    }
    targetInstallation = request.to === "global" ? checkedManifest(candidate) : null;
    for (const selected of [sourceInstallation, targetInstallation].filter(Boolean)) {
      if (selected.file) observed.push(observation(selected.file, { kind: "install-manifest", generation: selected.manifest.generation }));
      for (const file of selected.manifest.files) observed.push(observation(file.path, { source: file.source, ownership: selected === sourceInstallation ? "source-managed" : "target-managed" }));
    }
    if (resolution.operationReady && sourceInstallation && request.to === "local") {
      const clients = request.clients.length ? request.clients : sourceInstallation.manifest.clients.map((client) => client.id);
      const planned = planManagedInstall(resolution.planningRoot.root, { scope: "local", clients, skillsDirs: request.skillsDirs.map((directory) => path.resolve(request.project, directory)), agentsDirs: request.agentsDirs.map((directory) => path.resolve(request.project, directory)),
        ...(request.profile ? { profile: request.profile } : {}), ...(options.env ? { env: options.env } : {}), ...(options.run ? { run: options.run } : {}),
        ...(options.payloadDir ? { payloadDir: options.payloadDir } : {}), ...(options.sourceRoot ? { sourceRoot: options.sourceRoot } : {}), migrationContext: resolution });
      for (const conflict of planned.plan.conflicts) conflicts.push(issue(conflict.code, `${conflict.path}: ${conflict.message}`));
      if (planned.plan.ready) {
        preparedLocalPlan = planned.plan;
        preparedLocal = prepareInstallationPlan(planned.plan);
        operations = preparedLocal.operations;
        files.push(...operations.map((operation) => blueprint(operation, preparedLocal)));
      } else files.push(...planned.plan.files.map((file) => ({ ...file, ownership: "target-candidate" })));
      const mixed = sourceInstallation.manifest.clients.map((client) => client.id).filter((id) => clients.includes(id));
      if (mixed.length) warnings.push(issue("native-discovery-mixed", `Для ${mixed.join(", ")} остаются пользовательские global-проекции одновременно с новыми local-копиями`, "Разреши native discovery вручную; user runtime и проекции других store не удаляются"));
    } else if (resolution.operationReady && sourceInstallation && targetInstallation && request.to === "global") {
      const selectedClients = request.clients.length ? request.clients : sourceInstallation.manifest.clients.map((client) => client.id);
      for (const [kind, overrides] of [["skills", request.skillsDirs], ["agents", request.agentsDirs]]) for (const directory of overrides) {
        const target = path.resolve(request.project, directory);
        if (!sourceInstallation.manifest.clients.filter((client) => selectedClients.includes(client.id)).some((client) => (client[`${kind}Roots`] ?? []).some((root) => installationKey(root) === installationKey(target)))) conflicts.push(issue("migration-target-not-managed", `${target}: override не соответствует исходным управляемым ${kind} roots`));
      }
      for (const client of selectedClients) if (!targetInstallation.manifest.clients.some((item) => item.id === client)) conflicts.push(issue("migration-client-missing", `В global-поставке нет выбранного клиента ${client}`, `Выполни symphysis install --scope global --client ${client} и составь новый preview`));
      const globalOwned = new Map(targetInstallation.manifest.files.map((file) => [installationKey(file.path), file]));
      for (const entry of sourceInstallation.manifest.files) {
        const before = installationSnapshot(entry.path);
        const shared = globalOwned.get(installationKey(entry.path));
        if (shared) {
          if (before.hash !== entry.sha256 || before.hash !== shared.sha256) conflicts.push(issue("migration-shared-target-conflict", `${entry.path}: общая цель local/global не подтверждена обоими поколениями`));
          files.push({ path: entry.path, source: entry.source, ownership: "shared-global-owned", action: "preserve", before, afterHash: before.hash });
          continue;
        }
        if (before.hash !== null && before.hash !== entry.sha256) conflicts.push(issue("migration-owned-file-modified", `${entry.path}: пользовательская правка сохранена`));
        operations.push({ ...entry, owned: true, action: before.hash === null ? "unchanged" : "remove", before, afterHash: null, bytes: null });
        files.push({ path: entry.path, source: entry.source, ownership: "source-managed", action: before.hash === null ? "unchanged" : "remove", before, afterHash: null });
      }
      const data = planPlanningConfig({ storeRoot: resolution.planningRoot.root, sourceConfig: fs.readFileSync(path.join(candidate.runtime.root, "openspec", "config.symphysis.yaml"), "utf8"), declaration: true });
      for (const operation of data) {
        const before = installationSnapshot(operation.path);
        const afterHash = installationHash(operation.bytes);
        operations.push({ ...operation, owned: false, before, afterHash, action: before.hash === afterHash ? "unchanged" : before.hash === null ? "create" : "replace" });
        files.push({ path: operation.path, kind: operation.kind, ownership: "project-data", action: before.hash === afterHash ? "unchanged" : before.hash === null ? "create" : "replace", before, afterHash });
      }
      if (sourceInstallation.file) {
        const before = installationSnapshot(sourceInstallation.file);
        operations.push({ path: sourceInstallation.file, kind: "source-manifest", action: "remove", before, afterHash: null, bytes: null, owned: false });
        files.push({ path: sourceInstallation.file, kind: "source-manifest", ownership: "source-managed", action: "remove", before, afterHash: null });
      }
    }
  } catch (error) { conflicts.push(issue(error.code ?? "migration-preview-conflict", error.message)); }
  if (resolution.operationReady && conflicts.length === 0) {
    try {
      const receipt = path.join(resolution.planningRoot.root, ".symphysis", "migration.json");
      const before = installationSnapshot(receipt);
      if (before.hash !== null) {
        let previous;
        try { previous = JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(fs.readFileSync(receipt))); }
        catch { fail("Квитанция миграции имеет неизвестный формат и сохранена"); }
        if (!keys(previous, ["format", "from", "to", "runtimeApi", "schemaApi"]) || Object.keys(previous).length !== 5 || previous.format !== 1 || previous.runtimeApi !== 1 || previous.schemaApi !== 1 || !["local", "global"].includes(previous.from) || !["local", "global"].includes(previous.to) || previous.from === previous.to) fail("Квитанция миграции имеет неизвестный формат и сохранена");
      }
      const bytes = Buffer.from(`${JSON.stringify({ format: 1, from: source.scope, to: request.to, runtimeApi: 1, schemaApi: 1 })}\n`);
      const afterHash = installationHash(bytes);
      const action = before.hash === null ? "create" : "replace";
      operations.push({ kind: "migration-receipt", path: receipt, before, afterHash, bytes, owned: false, action });
      files.push({ kind: "migration-receipt", path: receipt, before, afterHash, ownership: "project-data", action });
    } catch (error) { conflicts.push(issue(error.code ?? "migration-receipt-conflict", error.message)); }
  }
  const preview = { format: 1, kind: "symphysis-migration", id: randomUUID(), request, storeRoot: resolution.planningRoot?.root ?? null, from: source?.scope ?? null, to: request.to,
    sourceGeneration: sourceInstallation?.legacy ? sourceInstallation.manifest.generation : source?.runtime?.generation ?? null, targetGeneration: candidate?.runtime?.generation ?? null,
    files, observed, conflicts, warnings, ready: resolution.operationReady && conflicts.length === 0 };
  previews.set(preview, { resolution, sourceInstallation, targetInstallation, preparedLocal, preparedLocalPlan, operations, options });
  return preview;
}

/** Serialized previews are compared to newly derived capabilities, never applied directly. */
export function readMigrationPlan(value) {
  if (!keys(value, ["format", "kind", "id", "request", "storeRoot", "from", "to", "sourceGeneration", "targetGeneration", "files", "observed", "conflicts", "warnings", "ready"]) || value.format !== 1 || value.kind !== "symphysis-migration" || typeof value.id !== "string" || !/^[a-f0-9-]{36}$/.test(value.id) || !keys(value.request, ["project", "store", "to", "clients", "skillsDirs", "agentsDirs", "profile"]) || typeof value.request.project !== "string" || !path.isAbsolute(value.request.project) || !Array.isArray(value.files) || !Array.isArray(value.observed) || !Array.isArray(value.conflicts) || !Array.isArray(value.warnings) || typeof value.ready !== "boolean") fail("Неподдерживаемый или изменённый формат migration plan");
  const request = requestFor(value.request);
  if (JSON.stringify(request) !== JSON.stringify(value.request) || value.to !== request.to) fail("Селекторы migration plan не согласованы");
  return value;
}

export function prepareMigrationPlan(value, options = {}) {
  const original = readMigrationPlan(value);
  if (!options.confirm) fail("Применение требует явного --confirm после просмотра preview");
  if (!original.ready || original.conflicts.length) fail("Preview содержит конфликты; составь новый план после их разрешения");
  const fresh = previewMigration({ ...original.request, store: original.request.store ?? undefined, profile: original.request.profile ?? undefined, ...options });
  const normalized = (plan) => ({ ...plan, id: null });
  if (!fresh.ready || JSON.stringify(normalized(fresh)) !== JSON.stringify(normalized(original))) throw new InstallationError("migration-state-changed", "Состояние файлов, реальных путей, payload или поколений изменилось после preview; переключения нет, составь новый план");
  return { preview: fresh, ...previews.get(fresh) };
}
