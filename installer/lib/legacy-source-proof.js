import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { getLegacyInventory, matchingLegacyGenerations } from "./legacy-inventory.js";
import { clientTargets } from "./client-targets.js";
import { installationKey, installationPath, installationSnapshot, assertInstallationSnapshot, installationHash } from "./installation-plan.js";
import { legacyCarrierHashes } from "./predecessor-adoption.js";

const DEFAULT_PAYLOAD = fileURLToPath(new URL("../payload/", import.meta.url));
const capabilities = new WeakMap();
const same = (a, b) => installationKey(a) === installationKey(b);
const prefix = "openspec/schemas/symphysis/";
const clone = (value) => structuredClone(value);

function sourceBinding(context) {
  if (context?.scope !== "local" || context.runtime?.legacy !== true || context.runtime.manifestPath !== null || !context.store?.root) throw new Error("Known legacy source requires a selected manifest-less local runtime");
  const storeRoot = installationPath(context.store.root, { directory: true });
  const root = installationPath(context.runtime.root, { directory: true });
  if ((!same(root, storeRoot) && !same(root, path.join(storeRoot, ".symphysis"))) || !same(context.runtime.toolsRoot, path.join(root, "tools")) || !same(context.runtime.docsRoot, path.join(root, "docs")) || !same(context.runtime.schemaRoot, path.join(storeRoot, "openspec", "schemas", "symphysis"))) throw new Error("Legacy source paths do not belong to the selected store");
  return { root, storeRoot, schemaRoot: context.runtime.schemaRoot, runtimeGeneration: context.runtime.generation };
}

function walk(directory, visit, relative = "") {
  if (!fs.existsSync(directory)) return;
  installationPath(directory, { directory: true });
  for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
    const tail = relative ? `${relative}/${entry.name}` : entry.name;
    const file = path.join(directory, entry.name);
    if (entry.isSymbolicLink()) visit(file, tail, "link");
    else if (entry.isDirectory()) walk(file, visit, tail);
    else visit(file, tail, entry.isFile() ? "file" : "other");
  }
}

/** A read-only capability minted exclusively from shipped hashes and exact bytes. */
export function createLegacySourceProof(sourceContext, { clients = [], skillsDirs = [], agentsDirs = [], env = process.env, payloadDir = DEFAULT_PAYLOAD } = {}) {
  const result = { ready: false, proof: null, generation: null, files: [], clients: [], conflicts: [] };
  const conflict = (file, message) => result.conflicts.push({ code: "migration-ownership-unconfirmed", path: file, message, action: "Сохрани неизвестные или изменённые файлы и согласуй ownership перед миграцией" });
  try {
    const binding = sourceBinding(sourceContext);
    const inventory = getLegacyInventory();
    const resources = new Map(inventory.generations.flatMap((generation) => generation.files.map((file) => [file.source, file])));
    const core = new Map();
    const natives = [];
    const read = (file, source, purpose, clientId) => {
      const snapshot = installationSnapshot(file);
      if (snapshot.hash === null) return null;
      const fd = fs.openSync(file, fs.constants.O_RDONLY | (fs.constants.O_NOFOLLOW ?? 0));
      let bytes;
      try {
        const stat = fs.fstatSync(fd);
        if (!stat.isFile() || String(stat.dev) !== snapshot.identity.dev || String(stat.ino) !== snapshot.identity.ino) throw new Error("Legacy source was replaced before reading");
        bytes = fs.readFileSync(fd);
      } finally { fs.closeSync(fd); }
      assertInstallationSnapshot(file, snapshot);
      if (installationHash(bytes) !== snapshot.hash) throw new Error("Legacy source changed while being read");
      return { source, path: file, sha256: snapshot.hash, snapshot, purpose, ...(clientId ? { clientId } : {}), bytes };
    };
    const expectedCore = new Map();
    for (const source of resources.keys()) {
      let file;
      if (source.startsWith("tools/")) file = path.join(sourceContext.runtime.toolsRoot, source.slice(6));
      else if (source.startsWith("docs/")) file = path.join(sourceContext.runtime.docsRoot, source.slice(5));
      else if (source.startsWith(prefix)) file = path.join(binding.schemaRoot, source.slice(prefix.length));
      if (!file) continue;
      expectedCore.set(installationKey(file), source);
      const item = read(file, source, source.startsWith(prefix) ? "schema" : source.startsWith("docs/") ? "doc" : "tool");
      if (item) core.set(source, item);
    }
    // Inspect only public product candidates. Personal settings/maps and other
    // runtime directories never enter inventory matching or file reads.
    for (const directory of [sourceContext.runtime.toolsRoot, sourceContext.runtime.docsRoot]) {
      if (!fs.existsSync(directory)) continue;
      installationPath(directory, { directory: true });
      for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
        if (entry.name === "journal-roots.json" || entry.name === "__pycache__") continue;
        const file = path.join(directory, entry.name);
        if (!expectedCore.has(installationKey(file)) && /\.(?:py|js|html|md|json)$/.test(entry.name)) conflict(file, "Неизвестный публичный ресурс legacy runtime сохранён");
      }
    }
    walk(binding.schemaRoot, (file, relative, kind) => {
      if (kind !== "file" || !resources.has(`${prefix}${relative}`)) conflict(file, "Состав legacy-схемы не подтверждён поставленным inventory");
    });
    const generations = matchingLegacyGenerations([...core.values()].map(({ source, bytes }) => ({ source, bytes })));
    if (!generations.length) conflict(binding.root, "Критические файлы и общие ресурсы не принадлежат одной известной legacy-генерации");
    const descriptors = clientTargets({ scope: "local", project: binding.storeRoot, clients, skillsDirs, agentsDirs, env });
    const bundle = JSON.parse(fs.readFileSync(path.join(payloadDir, "docs", "workflow-carriers.json"), "utf8"));
    const carrierHashes = legacyCarrierHashes(bundle);
    const generation = inventory.generations.find((item) => generations.includes(item.id));
    const inspectNative = (file, source, purpose, clientId) => {
      const item = read(file, source, purpose, clientId);
      if (!item) return;
      const hashes = purpose === "workflow" ? carrierHashes.get(`${clientId}/${source}`) : new Set(generation?.files.find((entry) => entry.source === source)?.sha256 ?? []);
      if (!hashes?.has(item.sha256)) conflict(file, "Клиентский файл не совпадает с точным известным предшественником");
      else natives.push(item);
    };
    for (const client of descriptors) {
      const expected = new Map();
      for (const source of resources.keys()) {
        const roots = source.startsWith("skills/") ? client.skillsRoots : source.startsWith("agents/") ? client.agentsRoots : [];
        const tail = source.slice(source.indexOf("/") + 1);
        for (const root of roots) expected.set(installationKey(path.join(root, tail)), { file: path.join(root, tail), source, purpose: source.startsWith("skills/") ? "skill" : "agent" });
      }
      for (const entry of bundle.legacyCatalog.filter((item) => item.clientId === client.id)) {
        const tail = client.id === "claude" && entry.kind === "command" ? entry.relativePath.replace(/^opsx\//, "") : entry.relativePath;
        const roots = entry.kind === "command" ? client.commandsRoot ? [client.commandsRoot] : [] : client.skillsRoots;
        const source = `${entry.kind === "command" ? "commands" : "skills"}/${tail}`;
        for (const root of roots) expected.set(installationKey(path.join(root, tail)), { file: path.join(root, tail), source, purpose: "workflow" });
      }
      for (const item of expected.values()) inspectNative(item.file, item.source, item.purpose, client.id);
      for (const root of client.skillsRoots) {
        if (!fs.existsSync(root)) continue;
        installationPath(root, { directory: true });
        for (const entry of fs.readdirSync(root, { withFileTypes: true })) if (/^(?:symphysis|openspec)-/.test(entry.name)) {
          const candidate = path.join(root, entry.name);
          if (!entry.isDirectory() || entry.isSymbolicLink()) { conflict(candidate, "Каталог клиентского скилла имеет неизвестный тип"); continue; }
          walk(candidate, (file) => { if (!expected.has(installationKey(file))) conflict(file, "Неизвестный файл клиентского скилла сохранён"); });
        }
      }
      for (const root of client.agentsRoots) {
        if (!fs.existsSync(root)) continue;
        installationPath(root, { directory: true });
        for (const entry of fs.readdirSync(root, { withFileTypes: true })) if (/^symphysis-.*\.(?:md|toml)$/.test(entry.name) && !expected.has(installationKey(path.join(root, entry.name)))) conflict(path.join(root, entry.name), "Неизвестный клиентский агент сохранён");
      }
      if (client.commandsRoot && fs.existsSync(client.commandsRoot)) {
        walk(client.commandsRoot, (file, relative) => { if ((client.id === "claude" || /^opsx-/.test(relative)) && !expected.has(installationKey(file))) conflict(file, "Неизвестная native-команда сохранена"); });
      }
    }
    result.clients = clone(descriptors);
    result.generation = generations[0] ?? null;
    const publicFiles = [...core.values(), ...natives].map(({ bytes, ...file }) => file);
    const unique = new Map();
    for (const file of publicFiles) {
      const key = installationKey(file.path);
      const previous = unique.get(key);
      if (previous && (previous.source !== file.source || previous.sha256 !== file.sha256)) conflict(file.path, "Одна цель имеет неоднозначную принадлежность ресурсам");
      else unique.set(key, file);
    }
    result.files = [...unique.values()];
    if (result.conflicts.length) return result;
    const facts = { ...binding, generation: result.generation, files: clone(result.files), clients: clone(descriptors) };
    const proof = Object.freeze({ format: 1, kind: "trusted-legacy-source", generation: facts.generation });
    capabilities.set(proof, { binding, facts });
    return { ...result, ready: true, proof };
  } catch (error) { conflict(sourceContext?.runtime?.root ?? null, error.message); return result; }
}

/** JSON lookalikes, a different store and inode changes cannot reuse a proof. */
export function legacySourceEvidence(proof, sourceContext) {
  const saved = capabilities.get(proof);
  if (!saved) return null;
  const binding = sourceBinding(sourceContext);
  if (JSON.stringify(binding) !== JSON.stringify(saved.binding)) return null;
  for (const file of saved.facts.files) assertInstallationSnapshot(file.path, file.snapshot);
  return clone(saved.facts);
}
