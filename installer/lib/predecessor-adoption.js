import fs from "node:fs";
import path from "node:path";
import { createHash } from "node:crypto";
import { getLegacyInventory, matchingLegacyGenerations } from "./legacy-inventory.js";
import { validateWorkflowBundle, workflowVariantContent } from "../scripts/build-workflow-carriers.js";
import { installationKey, installationSnapshot, assertInstallationSnapshot, installationTarget,
  normalizeInstallationRequest } from "./installation-plan.js";

const proofs = new WeakMap();
const hash = (bytes) => createHash("sha256").update(bytes).digest("hex");
const keyFor = (request) => JSON.stringify(normalizeInstallationRequest(request));
const relativeCarrier = (entry) => entry.clientId === "claude" && entry.kind === "command" ? entry.relativePath.replace(/^opsx\//, "") : entry.relativePath;

/** Only shipped callback outputs may authorize native predecessor replacement. */
export function legacyCarrierHashes(bundle) {
  validateWorkflowBundle(bundle);
  const known = new Map();
  for (const entry of bundle.legacyCatalog ?? []) {
    const source = `${entry.kind === "command" ? "commands" : "skills"}/${relativeCarrier(entry)}`;
    const hashes = known.get(`${entry.clientId}/${source}`) ?? new Set();
    for (const variant of entry.variants ?? []) {
      hashes.add(variant.sha256);
      const content = workflowVariantContent(entry, variant);
      // Git's official Windows checkout convention is a distinct exact byte
      // predecessor, never a normalization of an unknown user file.
      hashes.add(hash(Buffer.from(content.replace(/\r?\n/g, "\r\n"))));
    }
    known.set(`${entry.clientId}/${source}`, hashes);
  }
  return known;
}

/** Read-only adoption capability. Calling ordinary install never creates one. */
export function createPredecessorAdoptionProof({ request: input, files, bundle }) {
  const request = normalizeInstallationRequest(input);
  if (bundle.pin !== request.openspecPin) throw new Error("Adoption inventory belongs to another pinned native generation");
  const native = legacyCarrierHashes(bundle);
  const generations = getLegacyInventory().generations;
  const inventorySources = new Set(generations.flatMap((generation) => generation.files.map((file) => file.source)));
  const inspected = files.map((file) => {
    if (installationKey(installationTarget(request, file)) !== installationKey(file.path)) throw new Error("Adoption candidate has an unrelated target");
    const before = installationSnapshot(file.path);
    let bytes = null;
    if (before.hash !== null) {
      const fd = fs.openSync(file.path, fs.constants.O_RDONLY | (fs.constants.O_NOFOLLOW ?? 0));
      try {
        const current = fs.fstatSync(fd);
        if (String(current.dev) !== before.identity.dev || String(current.ino) !== before.identity.ino || !current.isFile()) throw new Error("Adoption source was replaced before reading");
        bytes = fs.readFileSync(fd);
      } finally { fs.closeSync(fd); }
      assertInstallationSnapshot(file.path, before);
      if (hash(bytes) !== before.hash) throw new Error("Adoption source changed while reading");
    }
    return { file, before, bytes };
  });
  const common = inspected.filter(({ file, bytes }) => bytes && inventorySources.has(file.source) && file.purpose !== "workflow");
  const unique = [...new Map(common.map(({ file, bytes }) => [file.source, { source: file.source, bytes }])).values()];
  const commonGenerations = matchingLegacyGenerations(unique).filter((id) => {
    const generation = generations.find((entry) => entry.id === id);
    return common.every(({ file, before }) => generation.files.some((entry) => entry.source === file.source && entry.sha256.includes(before.hash)));
  });
  const accepted = new Map();
  for (const { file, before, bytes } of inspected) {
    if (!bytes || before.hash === hash(file.bytes)) continue;
    let evidence = null;
    if (file.purpose === "workflow" && native.get(`${file.clientId}/${file.source}`)?.has(before.hash)) evidence = { kind: "known-native-predecessor", source: file.source, sha256: before.hash };
    else if (commonGenerations.length && inventorySources.has(file.source)) evidence = { kind: "known-product-generation", generation: commonGenerations[0], source: file.source, sha256: before.hash };
    else if ((file.purpose === "agent" || (file.projection && file.purpose === "schema")) && generations.some((generation) => generation.files.some((entry) => entry.source === file.source && entry.sha256.includes(before.hash)))) evidence = { kind: "known-native-resource-predecessor", source: file.source, sha256: before.hash };
    if (evidence) accepted.set(installationKey(file.path), { source: file.source, clientId: file.clientId ?? null, purpose: file.purpose, before, evidence });
  }
  const desired = new Set(files.map((file) => installationKey(file.path)));
  const retired = new Map();
  const candidates = [];
  for (const source of inventorySources) {
    const kind = source.split("/")[0];
    if (request.scope === "global" || ["tools", "docs"].includes(kind)) candidates.push({ source, path: path.join(request.runtimeRoot, source), purpose: kind === "agents" ? "agent" : kind === "skills" ? "skill" : kind });
    if (source.startsWith("openspec/schemas/symphysis/")) candidates.push({ source, path: path.join(request.schemaDirectory, "symphysis", source.slice("openspec/schemas/symphysis/".length)), purpose: "schema", ...(request.scope === "global" ? { projection: true } : {}) });
    if (["skills", "agents"].includes(kind)) for (const client of request.clients) for (const root of client[`${kind}Roots`] ?? []) candidates.push({ source, path: path.join(root, source.slice(kind.length + 1)), purpose: kind === "agents" ? "agent" : "skill", clientId: client.id, ...(request.scope === "global" ? { projection: true } : {}) });
  }
  for (const file of candidates) {
    if (desired.has(installationKey(file.path)) || retired.has(installationKey(file.path))) continue;
    if (installationKey(installationTarget(request, file)) !== installationKey(file.path)) continue;
    const before = installationSnapshot(file.path);
    if (before.hash === null) continue;
    const commonMatch = commonGenerations.some((id) => generations.find((generation) => generation.id === id).files.some((entry) => entry.source === file.source && entry.sha256.includes(before.hash)));
    const nativeSchemaMatch = file.projection && file.purpose === "schema" && generations.some((generation) => generation.files.some((entry) => entry.source === file.source && entry.sha256.includes(before.hash)));
    if (commonMatch || nativeSchemaMatch) retired.set(installationKey(file.path), { ...file, sha256: before.hash, before });
  }
  const proof = Object.freeze({ format: 1, kind: "trusted-predecessor-adoption", files: Object.freeze([...accepted].map(([file, value]) => Object.freeze({ path: inspected.find(({ file: entry }) => installationKey(entry.path) === file)?.file.path, ...value.evidence }))), retiredFiles: Object.freeze([...retired.values()].map((file) => Object.freeze({ path: file.path, source: file.source, sha256: file.sha256 }))) });
  proofs.set(proof, { requestKey: keyFor(request), accepted, retired });
  return proof;
}

/** JSON lookalikes and changed source files cannot authorize replacement. */
export function predecessorAdoption(proof, request, file, before) {
  const trusted = proofs.get(proof);
  if (!trusted || trusted.requestKey !== keyFor(request)) return null;
  const entry = trusted.accepted.get(installationKey(file.path));
  if (!entry || entry.source !== file.source || entry.purpose !== file.purpose || entry.clientId !== (file.clientId ?? null) || before.hash !== entry.before.hash) return null;
  assertInstallationSnapshot(file.path, entry.before);
  return entry.evidence;
}

export function predecessorRemoval(proof, request, target, before) {
  const trusted = proofs.get(proof);
  if (!trusted || trusted.requestKey !== keyFor(request)) return null;
  const entry = trusted.retired.get(installationKey(target));
  if (!entry || entry.before.hash !== before.hash) return null;
  assertInstallationSnapshot(target, entry.before);
  return entry;
}
