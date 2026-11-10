import fs from "node:fs";
import path from "node:path";
import { parseDocument, isMap, isSeq, isScalar } from "yaml";
import { InstallationError, installationHash, installationSnapshot, installationPath } from "./installation-plan.js";

export const SETTINGS_CONTENT = `# Личная настройка symphysis: в git проекта не идёт. Показать состав: symphysis config
consequences:
  failure_branches: true
  assumptions: true
edge_probe:
  enabled: true
drivers:
  attack: true
  probes: false
  consequences: false
  research: true
attack:
  context-compliance: true
  claim-authority: true
  claim-extraction: true
  coverage: true
  scenario-run: true
  trace-link: true
  rule-compliance: true
`;
export const ROOTS_CONTENT = '{"": "<root>/.."}\n';
export const MANAGEMENT_IGNORE_ENTRIES = [
  "symphysis.yaml", ".symphysis/tools/journal-roots.json", "tools/journal-roots.json",
  ".symphysis/install-manifest.json", ".symphysis/.install-*", ".symphysis/.leases/",
  ".symphysis/store-init.json", ".symphysis/.store-init-*",
  ".symphysis/migration.json", ".symphysis/.migration-*",
  ".symphysis-install-*", ".symphysis-init-*", ".symphysis-migrate-*",
];
const fail = (message) => { throw new InstallationError("planning-config-conflict", message); };

/** Validate all structures before changing even the in-memory document. */
export function mergeConfig(existingText, oursText) {
  const doc = parseDocument(existingText);
  const oursDoc = parseDocument(oursText);
  if (doc.errors.length || oursDoc.errors.length) fail("Planning config: неверный YAML; исходный файл сохранён");
  if (!isMap(doc.contents)) fail("Planning config должен быть словарём");
  const ours = oursDoc.toJS();
  const rules = doc.get("rules", true);
  if (rules !== undefined && !isMap(rules)) fail("rules должен быть словарём");
  for (const pair of rules?.items ?? []) if (!isSeq(pair.value) || pair.value.items.some((item) => !isScalar(item) || typeof item.value !== "string")) fail(`rules.${pair.key.value} должен быть списком строк`);
  const operations = doc.get("operations", true);
  if (operations !== undefined && !isMap(operations)) fail("operations должен быть словарём");
  for (const pair of operations?.items ?? []) {
    if (!isMap(pair.value)) fail(`operations.${pair.key.value} должен быть словарём`);
    const guidance = pair.value.get("guidance", true);
    if (guidance !== undefined && (!isSeq(guidance) || guidance.items.some((item) => !isScalar(item) || typeof item.value !== "string"))) fail(`operations.${pair.key.value}.guidance должен быть списком строк`);
  }
  const previous = doc.get("schema") ?? null;
  let changed = previous !== ours.schema;
  if (changed) doc.set("schema", ours.schema);
  const append = (keys, list) => {
    if (!Array.isArray(list)) fail(`Payload ${keys.join(".")}: нужен список`);
    let node = doc.contents;
    for (const key of keys.slice(0, -1)) {
      if (!node.has(key)) { node.set(key, doc.createNode({})); changed = true; }
      node = node.get(key, true);
    }
    const key = keys.at(-1);
    if (!node.has(key)) { node.set(key, doc.createNode(list)); changed = true; return; }
    const seq = node.get(key, true);
    const have = new Set(seq.items.map((item) => item.value));
    for (const item of list) if (!have.has(item)) { seq.add(doc.createNode(item)); have.add(item); changed = true; }
  };
  for (const [key, list] of Object.entries(ours.rules ?? {})) append(["rules", key], list);
  for (const [key, operation] of Object.entries(ours.operations ?? {})) if (operation.guidance) append(["operations", key, "guidance"], operation.guidance);
  return { text: changed ? doc.toString({ lineWidth: 0 }) : existingText, previous, warnings: [] };
}

export function nonOwnedFile(kind, file, bytes) {
  return { kind, path: file, beforeHash: installationSnapshot(file).hash, bytes: Buffer.from(bytes) };
}

/** Only framework planning config is read; existing personal settings/maps are opaque. */
export function planPlanningConfig({ storeRoot, sourceConfig, declaration = false }) {
  const yaml = path.join(storeRoot, "openspec", "config.yaml");
  const yml = path.join(storeRoot, "openspec", "config.yml");
  if (fs.existsSync(yaml) && fs.existsSync(yml)) fail("Есть config.yaml и config.yml; выбери единственный planning config");
  const file = fs.existsSync(yml) ? yml : yaml;
  const before = installationSnapshot(file);
  const merge = before.hash === null ? null : mergeConfig(fs.readFileSync(file, "utf8"), String(sourceConfig));
  const merged = before.hash === null ? Buffer.from(sourceConfig) : Buffer.from(merge.text);
  const message = merge && before.hash !== installationHash(merged) ? merge.previous === null ? "config.yaml уже был: схема установлена symphysis, rules добавлены" : merge.previous !== "symphysis" ? `config.yaml уже был: схема переключена с ${merge.previous} на symphysis, rules добавлены` : "config.yaml уже был: схема symphysis, rules добавлены" : null;
  const operations = [{ kind: "planning-config", path: file, beforeHash: before.hash, bytes: merged, ...(message ? { message } : {}) }];
  for (const [kind, relative, bytes] of [["initial-settings", "symphysis.yaml", SETTINGS_CONTENT], ["initial-roots", ".symphysis/tools/journal-roots.json", ROOTS_CONTENT]]) {
    const target = path.join(storeRoot, relative);
    installationPath(target);
    const existing = fs.lstatSync(target, { throwIfNoEntry: false });
    if (!existing && kind === "initial-roots") {
      const legacy = path.join(storeRoot, "tools", "journal-roots.json");
      installationPath(legacy);
      const legacyState = fs.lstatSync(legacy, { throwIfNoEntry: false });
      if (legacyState && !legacyState.isFile()) fail("tools/journal-roots.json: личная карта занята другим типом объекта");
      if (!legacyState) operations.push(nonOwnedFile(kind, target, bytes));
    }
    else if (!existing) operations.push(nonOwnedFile(kind, target, bytes));
    else if (!existing.isFile()) fail(`${relative}: начальный личный файл занят другим типом объекта`);
  }
  const ignore = path.join(storeRoot, ".gitignore");
  const ignored = fs.existsSync(ignore) ? fs.readFileSync(ignore) : Buffer.alloc(0);
  const lines = ignored.toString("latin1");
  const have = new Set(lines.split(/\r?\n/).map((line) => line.trim()));
  const addedEntries = MANAGEMENT_IGNORE_ENTRIES.filter((entry) => !have.has(entry));
  if (addedEntries.length) {
    const eol = lines.includes("\r\n") ? "\r\n" : "\n";
    const bytes = Buffer.concat([ignored, Buffer.from(`${lines && !lines.endsWith("\n") ? eol : ""}${addedEntries.join(eol)}${eol}`)]);
    operations.push({ ...nonOwnedFile("gitignore-merge", ignore, bytes), addedEntries });
  }
  if (declaration) {
    const target = path.join(storeRoot, "openspec", "symphysis.json");
    const bytes = Buffer.from('{"format":1,"runtimeApi":1,"schemaApi":1}\n');
    const existing = installationSnapshot(target);
    if (existing.hash !== null && existing.hash !== installationHash(bytes)) {
      let value;
      try { value = JSON.parse(fs.readFileSync(target, "utf8")); } catch { fail("Декларация store не является JSON; требуется явное согласование"); }
      if (value.format !== 1 || value.runtimeApi !== 1 || value.schemaApi !== 1) fail("Несовместимая декларация store; требуется явная миграция");
    } else operations.push(nonOwnedFile("store-declaration", target, bytes));
  }
  return operations;
}
