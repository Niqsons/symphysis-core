import fs from "node:fs";
import { createHash } from "node:crypto";

export const LEGACY_INVENTORY_URL = new URL("./data/legacy-inventory.json", import.meta.url);
const SHA = /^[a-f0-9]{64}$/;
const allowedSource = (source) => typeof source === "string" && !/[\\:\0]/.test(source)
  && !source.split("/").some((part) => !part || part === "." || part === "..")
  && !["symphysis.yaml", "journal-roots.json"].includes(source.split("/").at(-1))
  && /^(?:tools\/[^/]+|docs\/[^/]+\.md|agents\/symphysis-[^/]+-driver\.md|skills\/symphysis-[^/]+\/.+|openspec\/schemas\/symphysis\/.+)$/.test(source);

/** A shipped hash registry is evidence; a user-supplied plan cannot add hashes. */
export function validateLegacyInventory(value) {
  if (!value || value.format !== 1 || !Array.isArray(value.generations) || !value.generations.length) throw new Error("Legacy inventory format is unsupported");
  const ids = new Set();
  for (const generation of value.generations) {
    if (!generation || !/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(generation.id ?? "") || ids.has(generation.id) || !Array.isArray(generation.sourceCommits) || !generation.sourceCommits.length || generation.sourceCommits.some((commit) => !/^[a-f0-9]{40}$/.test(commit)) || !Array.isArray(generation.files) || !generation.files.length) throw new Error("Legacy generation is unsupported");
    ids.add(generation.id);
    const sources = new Set();
    for (const file of generation.files) {
      if (!file || !allowedSource(file.source) || sources.has(file.source) || !Array.isArray(file.sha256) || !file.sha256.length || file.sha256.some((hash) => !SHA.test(hash)) || new Set(file.sha256).size !== file.sha256.length) throw new Error("Legacy inventory has an unsafe or ambiguous resource");
      sources.add(file.source);
    }
    for (const required of ["tools/journal.py", "tools/journal_cli.py", "openspec/schemas/symphysis/schema.yaml"]) if (!sources.has(required)) throw new Error("Legacy generation has no critical resource");
  }
  return value;
}

let cached;
export function getLegacyInventory() {
  cached ??= validateLegacyInventory(JSON.parse(fs.readFileSync(LEGACY_INVENTORY_URL, "utf8")));
  return structuredClone(cached);
}

export function knownLegacyFile(source, bytes) {
  if (!allowedSource(source)) return null;
  const hash = createHash("sha256").update(bytes).digest("hex");
  const generation = getLegacyInventory().generations.find((entry) => entry.files.some((file) => file.source === source && file.sha256.includes(hash)));
  return generation ? { generation: generation.id, sha256: hash } : null;
}

export function matchingLegacyGenerations(files) {
  if (!Array.isArray(files) || !files.length || files.some((file) => !allowedSource(file.source))) return [];
  const hashes = new Map(files.map((file) => [file.source, createHash("sha256").update(file.bytes).digest("hex")]));
  if (hashes.size !== files.length || ["tools/journal.py", "tools/journal_cli.py", "openspec/schemas/symphysis/schema.yaml"].some((source) => !hashes.has(source))) return [];
  return getLegacyInventory().generations.filter((generation) => [...hashes].every(([source, hash]) => generation.files.some((file) => file.source === source && file.sha256.includes(hash)))).map((generation) => generation.id);
}
