import fs from "node:fs";
import path from "node:path";
import { createHash } from "node:crypto";
import { fileURLToPath, pathToFileURL } from "node:url";
import { spawnTool } from "../lib/openspec-bin.js";
import { LEGACY_INVENTORY_URL, validateLegacyInventory } from "../lib/legacy-inventory.js";

export const LEGACY_COMMITS = Object.freeze([
  "a19a4272fcce49c3cbee1aec6feeb4193748947c",
  "f17434beb5dbf68406bc76697b21cab65c91f409",
]);
const TOOLS = ["cli/journal.py", "cli/journal_cli.py", "decisions/journal_model.py", "decisions/journal_render.py", "decisions/journal_apply.py", "decisions/journal.schema.json", "roots/roots.py", "viewer/viewer_render.py", "viewer/playground-template.html", "attack/attack_table.py", "attack/attack_scope.py", "consequences/journal_sites.py", "consequences/journal_consequences.py", "settings/symphysis_config.py", "step-help/step_help.py", "openspec-run/openspec_run.py", "trace/trace_graph.py", "anchors/anchor_refs.py"];
const SHARED = ["skill-shared/terms.md", "skill-shared/driver.md", "decisions/candidate.md", "cli/journal-cli.md", "settings/config.md", "attack/attack-table.md"];
const MODULES = ["attack", "consequences", "decisions", "probes", "research", "viewer"];
const SCHEMA = "openspec/schemas/symphysis/";
const PROVENANCE = /^[ \t]*<!--[ \t]*(?:src|dev)\b[\s\S]*?-->[ \t]*\r?\n?/gm;
const digest = (bytes) => createHash("sha256").update(bytes).digest("hex");

function gitBytes(root, args) {
  const result = spawnTool("git", ["-C", root, ...args], { encoding: null, maxBuffer: 8 * 1024 * 1024 });
  if (result.error || result.status !== 0) throw new Error("Known legacy source objects are unavailable; use the shipped inventory or a full source clone");
  return Buffer.from(result.stdout);
}

function variants(bytes, text) {
  if (!text) return [digest(bytes)];
  const decoded = new TextDecoder("utf-8", { fatal: true }).decode(bytes);
  const lf = decoded.replaceAll("\r\n", "\n");
  return [...new Set([digest(bytes), digest(Buffer.from(lf)), digest(Buffer.from(lf.replaceAll("\n", "\r\n")))])].sort();
}

/** Read only whitelisted product blobs from fixed commits; never check out old code. */
export function buildLegacyInventory(root) {
  const generations = [];
  for (const commit of LEGACY_COMMITS) {
    const read = (name) => gitBytes(root, ["show", `${commit}:${name}`]);
    const names = gitBytes(root, ["ls-tree", "-r", "--name-only", "-z", commit, "--", SCHEMA.slice(0, -1), ...MODULES]).toString("utf8").split("\0").filter(Boolean);
    const files = new Map();
    const add = (source, bytes, text = true) => {
      if (files.has(source)) throw new Error("Legacy product has duplicate flat resources");
      files.set(source, variants(bytes, text));
    };
    for (const name of TOOLS) add(`tools/${path.posix.basename(name)}`, read(name));
    for (const name of SHARED) add(`docs/${path.posix.basename(name)}`, Buffer.from(read(name).toString("utf8").replace(PROVENANCE, "")));
    add("docs/THIRD-PARTY-NOTICES.md", read("installer/THIRD-PARTY-NOTICES.md"));
    for (const name of names) {
      if (name.startsWith(SCHEMA)) {
        const relative = name.slice(SCHEMA.length);
        if (relative.split("/").includes("tests") || ["README.md", "config.symphysis.yaml"].includes(relative)) continue;
        add(name, read(name));
      } else {
        const skill = /^[^/]+\/skills\/(symphysis-[^/]+\/.+)$/.exec(name);
        const agent = /^[^/]+\/agents\/(symphysis-[^/]+-driver\.md)$/.exec(name);
        if (skill && !skill[1].split("/").some((part) => ["sources", "tests", "TRANSLATION-NOTES.md"].includes(part))) add(`skills/${skill[1]}`, Buffer.from(read(name).toString("utf8").replace(PROVENANCE, "")));
        if (agent) add(`agents/${agent[1]}`, Buffer.from(read(name).toString("utf8").replace(PROVENANCE, "")));
      }
    }
    const previousPackage = JSON.parse(read("installer/package.json").toString("utf8"));
    const dependencyRoot = path.join(root, "installer/node_modules/mermaid");
    const installedDependency = JSON.parse(fs.readFileSync(path.join(dependencyRoot, "package.json"), "utf8"));
    if (previousPackage.devDependencies?.mermaid !== installedDependency.version) throw new Error("Known legacy Mermaid dependency is unavailable");
    add("tools/mermaid.min.js", fs.readFileSync(path.join(dependencyRoot, "dist/mermaid.min.js")), false);
    add("tools/mermaid.LICENSE", fs.readFileSync(path.join(dependencyRoot, "LICENSE")), false);
    const version = `${previousPackage.version}+${commit.slice(0, 7)}\n`;
    add("tools/symphysis-version.txt", Buffer.from(version));
    // A package installed outside a source clone intentionally had no git suffix.
    files.set("tools/symphysis-version.txt", [...new Set([...files.get("tools/symphysis-version.txt"), ...variants(Buffer.from(`${previousPackage.version}\n`), true)])].sort());
    generations.push({ id: `pre-global-${commit.slice(0, 7)}`, sourceCommits: [commit], mermaidVersion: installedDependency.version,
      files: [...files].sort(([first], [second]) => first.localeCompare(second, "en")).map(([source, sha256]) => ({ source, sha256 })) });
  }
  return validateLegacyInventory({ format: 1, generations });
}

if (process.argv[1] && import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href) {
  const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
  const output = fileURLToPath(LEGACY_INVENTORY_URL);
  const text = `${JSON.stringify(buildLegacyInventory(root), null, 2)}\n`;
  if (process.argv.includes("--write")) {
    fs.mkdirSync(path.dirname(output), { recursive: true });
    fs.writeFileSync(output, text);
    console.log("Known legacy inventory generated");
  } else {
    if (fs.readFileSync(output, "utf8") !== text) throw new Error("Shipped legacy inventory differs from known source blobs");
    console.log("Known legacy inventory verified");
  }
}
