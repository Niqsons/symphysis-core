#!/usr/bin/env node
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { createHash, randomUUID } from "node:crypto";
import { gzipSync, gunzipSync } from "node:zlib";
import { parseArgs } from "node:util";
import { fileURLToPath, pathToFileURL } from "node:url";
import { extractWorkflowArchive, removeWorkflowBuildTree, workflowArchiveEntries, workflowBuildPath } from "./workflow-archive.js";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
export const REQUIRED_WORKFLOWS = Object.freeze(["new", "continue", "apply", "sync", "archive"]);
const lf = (text) => text.replace(/\r\n?/g, "\n");
const hash = (bytes) => createHash("sha256").update(bytes).digest("hex");
const STORE_GUIDANCE = "**Store selection:** Select the requested source/store before any write. For a named store, discover ids with `symphysis openspec store list --json`. Put a selected `--store <id>` before the `openspec` or `preflight` subcommand: `symphysis --store <id> openspec ...`. Keep this bootstrap selector on all applicable follow-ups. In the inherited prose below, adding or keeping a store flag means this bootstrap prefix; normalize printed native hints the same way. Without an explicit store, use the selected source and its native planning root.";
const GUARD = `**Symphysis preflight — before the workflow (MUST):**
1. Select the requested source/store using the store-selection rule below. Store listing is the read-only discovery exception; it does not authorize writes.
2. After selection, run \`symphysis [--project <source>] [--store <id>] preflight\`. If an existing change has been selected, include \`--change <name>\` and repeat preflight whenever the selected change/store changes.
3. Continue only after exit 0. A refusal means STOP, report its diagnostic and explicit init/migration action, and perform no Write, Edit, artifact creation or other modifying action. Do not change configuration to bypass the refusal.
4. Execute OpenSpec through \`symphysis [--project <source>] [--store <id>] openspec ...\`. Common selectors precede \`openspec\`; move any trailing store selector from examples or printed native hints into that prefix. A successful resolve or copied skill file does not replace preflight.

`;

function replaceOnce(text, before, after, label) {
  if (text.split(before).length !== 2) throw new Error(`Pinned ${label} marker changed`);
  return text.replace(before, after);
}

/** Bridge our fork's sync sequencing to the managed runtime selected by preflight.
 * Source: docs/skills-canon.md section 12; merging fork-symphysis-flow with global-user-install.
 * Older pins do not have this fragment and retain their original guarded workflow.
 */
function guardSyncTools(body) {
  if (!body.includes('python "<toolsHome>/')) return body;
  const tools = /^   - From the invocation directory, find the nearest ancestor containing `\.symphysis\/tools\/`[^\n]*\n/m.exec(body)?.[0];
  if (!tools) throw new Error("Pinned Symphysis tools marker changed");
  const prefix = 'symphysis --project "<source>" [--store "<id>"] ';
  let text = replaceOnce(body, tools,
    '   - Use the same absolute source directory and optional store id selected for preflight as `<source>` and `<id>`. Run `' + prefix + 'resolve --change "<name>" --json`. A blocked resolve/preflight MUST stop this workflow before writes; it is not a nonblocking graph error. Require the returned `store.root` to denote the same planning root as the status JSON, comparing path identity. Keep `runtime.toolsRoot` as `toolsHome` for inline coordination. Use only the returned selected runtime; do not search caller directories, borrow another installation or install tools here.\n',
    "Symphysis tools");
  const graph = /^   - Set the Python command's working directory[^\n]*\n   - If `<toolsHome>\/journal-roots\.json`[^\n]*\n   - Otherwise,[^\n]*\n/m.exec(text)?.[0];
  if (!graph) throw new Error("Pinned Symphysis graph recipe changed");
  text = replaceOnce(text, graph,
    '   - You MUST run `' + prefix + 'trace freeze "<name>"`. The dispatcher supplies the selected store\'s roots and sets the tool cwd to `planningHome.root`; do not use a roots map from the caller or the runtime directory. Keep the same source/store prefix before every tool command.\n',
    "Symphysis graph recipe");
  for (const [file, command] of [["trace_graph.py", "trace"], ["anchor_refs.py", "anchors"], ["sync_check.py", "sync-check"]]) {
    text = text.replaceAll('python "<toolsHome>/' + file + '"', prefix + command);
  }
  if (text.includes('python "<toolsHome>/')) throw new Error("Pinned Symphysis tool command changed");
  return text;
}

/** Only trusted pinned CLI token boundaries are rewritten; openspec/ paths remain data paths. */
export function guardWorkflowBody(body, storeGuidance) {
  const marker = "@@SYMPHYSIS_STORE_SELECTION@@";
  if (body.includes(marker)) throw new Error("Pinned workflow contains a reserved builder marker");
  let text = replaceOnce(lf(body), lf(storeGuidance), marker, "store-selection");
  const commands = ["--version", "--help", "new", "status", "instructions", "list", "show", "validate", "archive", "doctor", "context", "schemas", "schema", "view", "init", "update", "store", "config", "templates", "change", "spec", "completion", "feedback"];
  text = text.replace(new RegExp(`\\bopenspec (?=(?:${commands.join("|")})\\b)`, "g"), "symphysis openspec ");
  text = text.replaceAll("Get-Command openspec ", "Get-Command symphysis ");
  text = text.replaceAll('symphysis openspec context --json --store "<store-id>"', 'symphysis --store "<store-id>" openspec context --json');
  text = text.replaceAll('and append `--store "<id>"` only for a registered standalone store.', 'and use the selected bootstrap `--store "<id>"` prefix only for a registered standalone store.');
  return GUARD + guardSyncTools(text.replace(marker, STORE_GUIDANCE));
}

function guardPermissions(content, expected) {
  const lines = lf(content).split("\n");
  const end = lines.indexOf("---", 1);
  if (lines[0] !== "---" || end < 0) throw new Error("Pinned formatter frontmatter changed");
  const permissions = lines.slice(1, end).filter((line) => line.startsWith("allowed-tools:"));
  if (permissions.length !== 1 || permissions[0] !== `allowed-tools: ${expected}` || expected !== "Bash(openspec:*)") throw new Error("Pinned allowed-tools format changed");
  lines[lines.indexOf(permissions[0])] = "allowed-tools: Bash(symphysis:*)";
  return lines.join("\n");
}

function checkModuleClosure(packageRoot, entrypoints) {
  const checked = new Set();
  const walk = (relative) => {
    const file = path.resolve(packageRoot, relative);
    const local = path.relative(packageRoot, file);
    if (local.startsWith("..") || path.isAbsolute(local) || !file.endsWith(".js")) throw new Error("Pinned generator import escapes package");
    if (checked.has(file)) return;
    checked.add(file);
    const text = fs.readFileSync(file, "utf8");
    if (/\bimport\s*\(/.test(text)) throw new Error("Unexpected dynamic generator import");
    const imports = /^\s*(?:import|export)\b[^;]*?\bfrom\s*["']([^"']+)["']/gm;
    for (const match of text.matchAll(imports)) {
      if (["path", "node:path"].includes(match[1])) continue;
      if (!match[1].startsWith(".")) throw new Error("Unexpected external generator dependency");
      walk(path.relative(packageRoot, path.resolve(path.dirname(file), match[1])));
    }
    if (/^\s*import\s*["']/m.test(text)) throw new Error("Unexpected side-effect generator import");
  };
  entrypoints.forEach(walk);
}

export function validateWorkflowBundle(value, { pin } = {}) {
  if (!value || value.format !== 1 || typeof value.pin !== "string" || (pin !== undefined && value.pin !== pin) || !/^[a-f0-9]{64}$/.test(value.archiveSha256 ?? "") || value.profile !== "symphysis" || !Array.isArray(value.workflows) || !Array.isArray(value.files) || !Array.isArray(value.licenses)) throw new Error("Invalid generated workflow bundle metadata/pin");
  const profiles = value.profiles;
  const ids = (items) => Array.isArray(items) && items.every((id) => typeof id === "string" && /^[a-z][a-z-]*$/.test(id)) && new Set(items).size === items.length;
  if (!profiles || !ids(profiles.all) || !ids(profiles.core) || !ids(profiles.required) || JSON.stringify(profiles.required) !== JSON.stringify(REQUIRED_WORKFLOWS) || [...profiles.core, ...profiles.required, ...value.workflows].some((id) => !profiles.all.includes(id)) || !profiles.dependencies || Array.isArray(profiles.dependencies) || typeof profiles.dependencies !== "object" || Object.keys(profiles.dependencies).some((id) => !profiles.all.includes(id) || !ids(profiles.dependencies[id]) || profiles.dependencies[id].some((dependency) => dependency === id || !profiles.all.includes(dependency))) || !Array.isArray(value.catalog)) throw new Error("Invalid generated workflow profile catalog");
  if (!REQUIRED_WORKFLOWS.every((id) => value.workflows.includes(id)) || new Set(value.workflows).size !== value.workflows.length) throw new Error("Incomplete generated workflow profile");
  validateCarrierSet(value.catalog, profiles.all, { variants: true });
  validateCarrierSet(value.legacyCatalog, profiles.all, { variants: true, legacy: true });
  validateCarrierSet(value.files, value.workflows);
  for (const file of value.files) if (!selectedFiles(value.catalog, value.workflows).some((candidate) => JSON.stringify(candidate) === JSON.stringify(file))) throw new Error("Generated workflow selection differs from its trusted catalog");
  return value;
}

function validateCarrierSet(files, workflows, { variants = false, legacy = false } = {}) {
  if (!Array.isArray(files)) throw new Error("Missing generated workflow catalog");
  const keys = new Set();
  for (const file of files) {
    const content = variants && file?.variants?.length ? workflowVariantContent(file, file.variants.at(-1)) : file?.content;
    if (!file || !["claude", "codex", "opencode"].includes(file.clientId) || !["skill", "command"].includes(file.kind) || !workflows.includes(file.id) || typeof file.relativePath !== "string" || /[\\:\0]/.test(file.relativePath) || file.relativePath.split("/").some((part) => !part || part === "." || part === "..") || typeof content !== "string" || (!legacy && !content.includes("**Symphysis preflight"))) throw new Error("Invalid generated workflow carrier");
    const key = `${file.clientId}/${file.relativePath}`;
    if (keys.has(key)) throw new Error("Duplicate generated workflow target");
    if (file.kind === "skill" ? (!legacy && file.clientId !== "codex") || !/^openspec-[a-z-]+\/SKILL\.md$/.test(file.relativePath) : file.clientId === "codex" || (file.clientId === "claude" ? !/^opsx\/[a-z-]+\.md$/.test(file.relativePath) : !/^opsx-[a-z-]+\.md$/.test(file.relativePath))) throw new Error("Generated carrier has a non-native target");
    if (variants) {
      if (file.sha256 !== hash(Buffer.from(content)) || !Array.isArray(file.conditions) || new Set(file.conditions).size !== file.conditions.length || file.conditions.length > 10 || file.conditions.some((id) => !workflows.includes(id) || id === file.id) || file.lineEncoding !== "gzip-uint16le-hex" || !Array.isArray(file.fragments) || file.fragments.length > 65536 || file.fragments.some((fragment) => typeof fragment !== "string" || fragment.length > 65536) || !Array.isArray(file.variants) || file.variants.length !== 2 ** file.conditions.length || (legacy && (file.legacy !== true || file.readOnly !== true))) throw new Error("Invalid generated carrier variants");
      const selections = new Set();
      for (const variant of file.variants) {
        const content = workflowVariantContent(file, variant);
        if (!Array.isArray(variant.selected) || variant.selected.some((id) => !file.conditions.includes(id)) || new Set(variant.selected).size !== variant.selected.length || variant.sha256 !== hash(Buffer.from(content)) || (!legacy && !content.includes("**Symphysis preflight")) || content.includes("[[opsx:")) throw new Error("Invalid generated carrier variant");
        const key = file.conditions.map((id) => variant.selected.includes(id) ? "1" : "0").join("");
        if (selections.has(key)) throw new Error("Duplicate generated carrier variant");
        selections.add(key);
      }
    }
    keys.add(key);
  }
  for (const clientId of ["claude", "codex", "opencode"]) for (const id of workflows) if (files.filter((file) => file.clientId === clientId && file.id === id).length !== (legacy && clientId !== "codex" ? 2 : 1)) throw new Error("Missing per-client workflow carrier");
}

function selectedFiles(catalog, workflows) {
  return catalog.filter((file) => workflows.includes(file.id)).map((file) => {
    const { clientId, kind, id, relativePath, conditions, variants } = file;
    const variant = variants.find((item) => conditions.every((condition) => item.selected.includes(condition) === workflows.includes(condition)));
    if (!variant) throw new Error("Missing generated carrier selection");
    return { clientId, kind, id, relativePath, content: workflowVariantContent(file, variant) };
  });
}

/** Expand trusted prebuilt line fragments; no templates or instructions execute. */
export function workflowVariantContent(file, variant) {
  if (file.lineEncoding !== "gzip-uint16le-hex" || !Array.isArray(file.fragments) || file.fragments.length > 65536 || typeof variant.lines !== "string" || variant.lines.length > 49152) throw new Error("Invalid generated carrier fragments");
  const compressed = Buffer.from(variant.lines, "hex");
  if (compressed.toString("hex") !== variant.lines) throw new Error("Invalid generated carrier fragment indices");
  const bytes = gunzipSync(compressed, { maxOutputLength: 20000 });
  if (bytes.length % 2) throw new Error("Invalid generated carrier fragment indices");
  const lines = [];
  let size = 0;
  for (let offset = 0; offset < bytes.length; offset += 2) {
    const fragment = file.fragments[bytes.readUInt16LE(offset)];
    if (typeof fragment !== "string" || fragment.length > 65536 || (size += fragment.length) > 500000) throw new Error("Invalid generated carrier fragment index or size");
    lines.push(fragment);
  }
  return lines.join("");
}

/** Select only prebuilt trusted carriers; this never imports runtime generators. */
export function selectWorkflowCarriers(bundle, { profile = "core", workflows } = {}) {
  validateWorkflowBundle(bundle);
  if (!["core", "custom"].includes(profile)) throw new Error("Unknown native workflow profile; expected core or custom");
  const selected = profile === "core" ? bundle.profiles.core : workflows ?? [];
  if (!Array.isArray(selected) || selected.some((id) => typeof id !== "string" || !bundle.profiles.all.includes(id))) throw new Error("Unknown native custom workflow");
  const result = [...bundle.profiles.required];
  const add = (id, visiting = new Set()) => {
    if (visiting.has(id)) throw new Error("Cyclic native workflow dependencies");
    visiting.add(id);
    for (const dependency of bundle.profiles.dependencies[id] ?? []) add(dependency, visiting);
    visiting.delete(id);
    if (!result.includes(id)) result.push(id);
  };
  for (const id of selected) add(id);
  return { profile, workflows: result, files: selectedFiles(bundle.catalog, result) };
}

export async function buildWorkflowCarriers({ root = ROOT, tempBase = os.tmpdir(), workflowIds } = {}) {
  root = workflowBuildPath(root);
  const metadata = JSON.parse(fs.readFileSync(path.join(root, "installer", "package.json"), "utf8")).symphysis;
  if (!metadata || typeof metadata.openspecPin !== "string" || !/^vendor\/[^/\\]+\.tgz$/.test(metadata.openspecSource ?? "")) throw new Error("Invalid pinned archive metadata");
  const archivePath = workflowBuildPath(path.join(root, metadata.openspecSource));
  const archive = fs.readFileSync(archivePath);
  const entries = workflowArchiveEntries(archive);
  const version = JSON.parse(entries.find((entry) => entry.name === "package/package.json")?.bytes.toString("utf8") ?? "null");
  if (version?.version !== metadata.openspecPin || version?.type !== "module") throw new Error("Pinned archive package version/format mismatch");
  const base = workflowBuildPath(tempBase);
  fs.mkdirSync(base, { recursive: true });
  const staging = fs.mkdtempSync(path.join(base, "symphysis-workflows-"));
  try {
    const packageRoot = extractWorkflowArchive(entries, staging);
    const modulePaths = ["dist/core/shared/skill-generation.js", "dist/core/command-generation/generator.js", "dist/core/command-generation/adapters/claude.js", "dist/core/command-generation/adapters/opencode.js", "dist/utils/command-references.js", "dist/core/profiles.js", "dist/core/shared/allowed-tools.js", "dist/core/templates/workflows/store-selection.js", "dist/core/templates/skill-templates.js", "dist/core/command-generation/invocation.js"];
    checkModuleClosure(packageRoot, modulePaths);
    const [shared, generator, claude, opencode, references, profiles, allowed, selection, templates, invocation] = await Promise.all(modulePaths.map((relative) => import(pathToFileURL(path.join(packageRoot, relative)).href)));
    for (const [source, names] of [[shared, ["getSkillTemplates", "getCommandContents", "generateSkillContent"]], [generator, ["generateCommand"]], [references, ["getTransformerForTool"]]]) if (names.some((name) => typeof source[name] !== "function")) throw new Error("Pinned generator exports changed");
    if (!Array.isArray(profiles.CORE_WORKFLOWS) || !Array.isArray(profiles.ALL_WORKFLOWS) || typeof profiles.getProfileWorkflows !== "function" || typeof selection.STORE_SELECTION_GUIDANCE !== "string") throw new Error("Pinned workflow profile/store-selection exports changed");
    const workflows = [...new Set([...REQUIRED_WORKFLOWS, ...(workflowIds ?? profiles.CORE_WORKFLOWS)])];
    if (workflows.some((id) => !profiles.ALL_WORKFLOWS.includes(id))) throw new Error("Unknown requested pinned workflow");
    const all = [...profiles.ALL_WORKFLOWS];
    const dependencies = Object.fromEntries(all.map((id) => [id, [...profiles.getProfileWorkflows("custom", [id])].filter((dependency) => dependency !== id)]));
    const skills = shared.getSkillTemplates(all);
    const commands = shared.getCommandContents(all);
    if (skills.length !== all.length || commands.length !== all.length) throw new Error("Pinned workflow generation omitted selected templates");
    const transform = references.getTransformerForTool("codex", "skills", "skills-invocable", undefined);
    if (typeof transform !== "function") throw new Error("Pinned Codex skill transformer changed");
    const rawSkills = Object.entries(templates).filter(([name, factory]) => /^get.*SkillTemplate$/.test(name) && typeof factory === "function").map(([, factory]) => factory());
    const rawCommands = Object.entries(templates).filter(([name, factory]) => /^getOpsx.*CommandTemplate$/.test(name) && typeof factory === "function").map(([, factory]) => factory());
    const files = [], legacyFiles = [];
    const variantEntry = (base, rawBody, render, legacy = false) => {
      const conditions = [...new Set([...rawBody.matchAll(/\[\[opsx:if-workflow ([a-z-]+)\]\]/g)].map((match) => match[1]))].filter((id) => id !== base.id && (legacy || !REQUIRED_WORKFLOWS.includes(id)));
      if (conditions.length > 10 || conditions.some((id) => !all.includes(id))) throw new Error("Pinned optional workflow conditions changed");
      const fragments = [], indexes = new Map();
      let content;
      const variants = Array.from({ length: 2 ** conditions.length }, (_, mask) => {
        const selected = conditions.filter((_, index) => mask & (2 ** index));
        content = render([...new Set([...(legacy ? [] : REQUIRED_WORKFLOWS), base.id, ...selected])]);
        const lines = (content.match(/[^\n]*\n|[^\n]+$/g) ?? []).map((line) => {
          if (!indexes.has(line)) { indexes.set(line, fragments.length); fragments.push(line); }
          return indexes.get(line);
        });
        if (fragments.length > 65536 || lines.length > 10000) throw new Error("Pinned workflow exceeds fragment limits");
        const indices = Buffer.alloc(lines.length * 2);
        lines.forEach((index, offset) => indices.writeUInt16LE(index, offset * 2));
        return { selected, lines: gzipSync(indices, { level: 9 }).toString("hex"), sha256: hash(Buffer.from(content)) };
      });
      return { ...base, sha256: hash(Buffer.from(content)), conditions, fragments, lineEncoding: "gzip-uint16le-hex", variants, ...(legacy ? { legacy: true, readOnly: true } : {}) };
    };
    for (const skill of skills) {
      const matches = rawSkills.filter((template) => template.name === skill.template.name);
      if (matches.length !== 1) throw new Error("Pinned raw skill template mapping changed");
      const base = { clientId: "codex", kind: "skill", id: skill.workflowId, relativePath: `${skill.dirName}/SKILL.md` };
      const render = (selected, guarded, toolTransform) => {
        const template = shared.getSkillTemplates(selected).find((entry) => entry.workflowId === skill.workflowId)?.template;
        if (!template) throw new Error("Pinned selected skill template missing");
        const content = shared.generateSkillContent(template, metadata.openspecPin, (body) => {
          const text = guarded ? guardWorkflowBody(body, selection.STORE_SELECTION_GUIDANCE) : body;
          return toolTransform ? toolTransform(text) : text;
        });
        return guarded ? guardPermissions(content, allowed.OPENSPEC_CLI_ALLOWED_TOOLS) : content;
      };
      files.push(variantEntry(base, matches[0].instructions, (selected) => render(selected, true, transform)));
      legacyFiles.push(variantEntry(base, matches[0].instructions, (selected) => render(selected, false, transform), true));
      for (const [clientId, adapter] of [["claude", claude.claudeAdapter], ["opencode", opencode.opencodeAdapter]]) {
        const nativeTransform = references.getTransformerForTool(clientId, "both", "adapter-backed", invocation.getInvocationForAdapter(adapter));
        legacyFiles.push(variantEntry({ ...base, clientId }, matches[0].instructions, (selected) => render(selected, false, nativeTransform), true));
      }
    }
    for (const [clientId, adapter, prefix] of [["claude", claude.claudeAdapter, ".claude/commands/"], ["opencode", opencode.opencodeAdapter, ".opencode/commands/"]]) {
      if (adapter?.toolId !== clientId || typeof adapter.formatFile !== "function" || typeof adapter.getFilePath !== "function") throw new Error("Pinned command adapter exports changed");
      for (const command of commands) {
        const matches = rawCommands.filter((template) => template.name === command.name);
        if (matches.length !== 1) throw new Error("Pinned raw command template mapping changed");
        const generatedPath = adapter.getFilePath(command.id).replaceAll("\\", "/");
        if (!generatedPath.startsWith(prefix)) throw new Error("Pinned command adapter path changed");
        const base = { clientId, kind: "command", id: command.id, relativePath: generatedPath.slice(prefix.length) };
        const render = (selected, guarded) => {
          const chosen = shared.getCommandContents(selected).find((entry) => entry.id === command.id);
          if (!chosen) throw new Error("Pinned selected command template missing");
          const generated = generator.generateCommand({ ...chosen, body: guarded ? guardWorkflowBody(chosen.body, selection.STORE_SELECTION_GUIDANCE) : chosen.body }, adapter);
          return guarded && clientId === "claude" ? guardPermissions(generated.fileContent, allowed.OPENSPEC_CLI_ALLOWED_TOOLS) : lf(generated.fileContent);
        };
        files.push(variantEntry(base, matches[0].content, (selected) => render(selected, true)));
        legacyFiles.push(variantEntry(base, matches[0].content, (selected) => render(selected, false), true));
      }
    }
    const license = entries.find((entry) => entry.name === "package/LICENSE")?.bytes;
    if (!license || !license.toString("utf8").includes("MIT License")) throw new Error("Pinned archive MIT attribution is missing");
    const catalog = files.sort((a, b) => `${a.clientId}/${a.relativePath}`.localeCompare(`${b.clientId}/${b.relativePath}`, "en"));
    return validateWorkflowBundle({ format: 1, pin: metadata.openspecPin, archiveSha256: hash(archive), profile: "symphysis", workflows,
      profiles: { core: [...profiles.CORE_WORKFLOWS], required: [...REQUIRED_WORKFLOWS], all, dependencies }, catalog,
      legacyCatalog: legacyFiles.sort((a, b) => `${a.clientId}/${a.relativePath}`.localeCompare(`${b.clientId}/${b.relativePath}`, "en")),
      files: selectedFiles(catalog, workflows), licenses: [{ name: "OpenSpec", license: "MIT", text: lf(license.toString("utf8")) }] });
  } finally { removeWorkflowBuildTree(staging); }
}

export async function writeWorkflowCarriers(options = {}) {
  const root = path.resolve(options.root ?? ROOT);
  const bundle = await buildWorkflowCarriers({ ...options, root });
  const file = workflowBuildPath(path.join(root, "installer", "generated", "workflow-carriers.json"));
  const bytes = Buffer.from(`${JSON.stringify(bundle, null, 2)}\n`);
  const changed = !fs.existsSync(file) || !fs.readFileSync(file).equals(bytes);
  if (changed) {
    fs.mkdirSync(path.dirname(file), { recursive: true });
    const temporary = workflowBuildPath(path.join(path.dirname(file), `.workflow-carriers-${randomUUID()}.tmp`));
    try { fs.writeFileSync(temporary, bytes, { flag: "wx" }); fs.renameSync(temporary, file); }
    finally { if (fs.existsSync(temporary)) fs.unlinkSync(temporary); }
  }
  return { bundle, path: file, changed };
}

if (process.argv[1] && import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href) {
  try {
    const { values } = parseArgs({ options: { root: { type: "string" }, help: { type: "boolean", short: "h" } } });
    if (values.help) process.stdout.write("Build guarded workflow carriers from the pinned vendor archive.\nUsage: node installer/scripts/build-workflow-carriers.js [--root <absolute-root>]\n");
    else { const result = await writeWorkflowCarriers({ root: values.root ?? ROOT }); process.stdout.write(`workflow carriers: ${result.bundle.files.length}, pin ${result.bundle.pin}\n`); }
  } catch (error) { process.stderr.write(`${error.message}\n`); process.exitCode = 1; }
}
