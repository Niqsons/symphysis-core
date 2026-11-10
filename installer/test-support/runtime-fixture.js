import fs from "node:fs";
import path from "node:path";
import { createHash } from "node:crypto";
import { stringify } from "yaml";

const idPattern = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;
const samplePayload = {
  "tools/journal.py": "# synthetic fixture: journal entrypoint\n",
  "tools/step_help.py": "# synthetic fixture: help entrypoint\n",
  "tools/trace_graph.py": "# synthetic fixture: trace entrypoint\n",
  "tools/anchor_refs.py": "# synthetic fixture: anchors entrypoint\n",
  "tools/sync_check.py": "# synthetic fixture: sync result checker entrypoint\n",
  "tools/symphysis_config.py": "# synthetic fixture: config entrypoint\n",
  "tools/journal_render.py": "# synthetic fixture: independent journal contract\nCONTRACT = 1\n",
  "docs/terms.md": "# Fixture terms\n",
  "openspec/schemas/symphysis/schema.yaml": "name: symphysis\nversion: 1\ndescription: Synthetic fixture\nartifacts: []\n",
  "skills/symphysis-brainstorm/SKILL.md": "---\nname: symphysis-brainstorm\ndescription: Synthetic fixture\n---\nFixture only.\n",
  "agents/symphysis-research-driver.md": "Synthetic fixture only.\n",
};

function inside(base, candidate) {
  const relative = path.relative(base, candidate);
  return relative !== "" && relative !== ".." && !relative.startsWith(`..${path.sep}`) && !path.isAbsolute(relative);
}

function noLinks(target) {
  let current = path.parse(target).root;
  for (const part of target.slice(current.length).split(path.sep).filter(Boolean)) {
    current = path.join(current, part);
    const stat = fs.lstatSync(current, { throwIfNoEntry: false });
    if (stat?.isSymbolicLink()) throw new Error(`Fixture path crosses a link: ${current}`);
    if (!stat) break;
  }
}

/** Synthetic, filesystem-only fixtures. Explicit base only; no installer, git or user-profile discovery. */
export function createRuntimeFixture(baseDir) {
  if (!path.isAbsolute(baseDir)) throw new Error("Fixture base must be absolute");
  const base = path.resolve(baseDir);
  if (base === path.parse(base).root) throw new Error("Fixture base cannot be a filesystem root");
  noLinks(base);
  fs.mkdirSync(base, { recursive: true });
  const root = fs.mkdtempSync(path.join(base, "symphysis-runtime-"));
  const at = (...parts) => {
    const target = path.resolve(root, ...parts);
    if (!inside(root, target)) throw new Error("Fixture path escapes its root");
    noLinks(target);
    return target;
  };
  const write = (target, content) => {
    const checked = at(target);
    fs.mkdirSync(path.dirname(checked), { recursive: true });
    fs.writeFileSync(checked, content);
    return checked;
  };
  const json = (target, value) => write(target, `${JSON.stringify(value, null, 2)}\n`);
  const home = at("profile");
  const userDir = at("user-data", "symphysis");
  const clientRoots = {
    claude: { skills: at("clients", "claude", "skills"), agents: at("clients", "claude", "agents"), commands: at("clients", "claude", "commands", "opsx") },
    codex: { skills: at("profile", ".agents", "skills"), agents: at("clients", "codex", "agents") },
    opencode: { skills: at("clients", "opencode", "skills"), agents: at("clients", "opencode", "agents"), commands: at("clients", "opencode", "commands") },
  };
  const overrides = {
    HOME: home, USERPROFILE: home, HOMEDRIVE: path.parse(home).root.slice(0, -1), HOMEPATH: home.slice(path.parse(home).root.length - 1),
    APPDATA: at("profile", "AppData", "Roaming"), LOCALAPPDATA: at("profile", "AppData", "Local"),
    XDG_CONFIG_HOME: at("config"), XDG_DATA_HOME: at("user-data"), XDG_CACHE_HOME: at("cache"), XDG_STATE_HOME: at("state"),
    CODEX_HOME: at("clients", "codex"), CLAUDE_CONFIG_DIR: at("clients", "claude"), OPENCODE_CONFIG_DIR: at("clients", "opencode"),
    SYMPHYSIS_HOME: userDir, TEMP: at("temp"), TMP: at("temp"), TMPDIR: at("temp"),
    OPENSPEC_TELEMETRY: "0", OPENSPEC_NO_UPDATE_CHECK: "1", OPENSPEC_NO_COMPLETIONS: "1",
  };
  const overridden = new Set(Object.keys(overrides).map((key) => key.toLowerCase()));
  const drop = new Set(["symphysis_openspec", "opencode_config", "opencode_config_content", "symphysis_context", "symphysis_runtime_context"]);
  const env = Object.fromEntries(Object.entries(process.env).filter(([key]) => !overridden.has(key.toLowerCase()) && !drop.has(key.toLowerCase())));
  Object.assign(env, overrides);
  for (const name of ["profile", "config", "user-data", "cache", "state", "temp", "clients/claude", "clients/codex", "clients/opencode"]) fs.mkdirSync(at(name), { recursive: true });
  const registered = {};

  function store(id, { change = "same-change", dataOnly = false, declaration = true } = {}) {
    if (!idPattern.test(id) || !idPattern.test(change)) throw new Error("Fixture store/change id must be kebab-case");
    const storeRoot = at("stores", id);
    const changeRoot = at(storeRoot, "openspec", "changes", change);
    fs.mkdirSync(at(storeRoot, "openspec", "specs"), { recursive: true });
    fs.mkdirSync(changeRoot, { recursive: true });
    write(at(storeRoot, "openspec", "config.yaml"), "schema: symphysis\n");
    write(at(storeRoot, ".openspec-store", "store.yaml"), stringify({ version: 1, id }));
    write(at(changeRoot, ".openspec.yaml"), "schema: symphysis\ncreated: 2026-11-09\n");
    write(at(changeRoot, "intent.md"), `# Intent\nSynthetic fixture ${id}.\n`);
    const journal = json(at(changeRoot, "decisions.json"), { title: `Fixture ${id}`, source: "decisions.json", records: [] });
    if (declaration) json(at(storeRoot, "openspec", "symphysis.json"), { format: 1, runtimeApi: 1, schemaApi: 1 });
    if (dataOnly) json(at(storeRoot, ".symphysis", "tools", "journal-roots.json"), { "": "<root>/.." });
    registered[id] = { backend: { type: "git", local_path: storeRoot.replaceAll(path.sep, "/") } };
    write(at("user-data", "openspec", "stores", "registry.yaml"), stringify({ version: 1, stores: registered }));
    return { id, root: storeRoot, change, changeRoot, journal };
  }

  function pointer(name, storeId) {
    if (!idPattern.test(name) || !registered[storeId]) throw new Error("Fixture pointer needs a name and registered store");
    const source = at("sources", name);
    write(at(source, "openspec", "config.yaml"), stringify({ store: storeId }));
    return source;
  }

  function payload(scope, { store: selectedStore, files = samplePayload, payloadDir, generation = "fixture-generation", manifest = undefined, legacy = false } = {}) {
    if (!["local", "global"].includes(scope)) throw new Error("Fixture scope must be local or global");
    const storeRoot = selectedStore?.root ?? selectedStore;
    if (scope === "local" && !storeRoot) throw new Error("Local fixture payload needs a store");
    const runtimeRoot = scope === "global" ? at(userDir, "runtime") : at(storeRoot, ".symphysis");
    const manifestPath = scope === "global" ? at(userDir, "install-manifest.json") : at(runtimeRoot, "install-manifest.json");
    let entries;
    if (payloadDir) {
      if (!path.isAbsolute(payloadDir)) throw new Error("Fixture payloadDir must be absolute");
      noLinks(payloadDir);
      entries = [];
      const read = (dir, prefix = "") => {
        for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
          if (entry.isSymbolicLink()) throw new Error("Fixture source payload contains a link");
          const rel = prefix ? `${prefix}/${entry.name}` : entry.name;
          if (entry.isDirectory()) read(path.join(dir, entry.name), rel);
          else if (entry.isFile()) entries.push([rel, fs.readFileSync(path.join(dir, entry.name))]);
        }
      };
      read(payloadDir);
    } else entries = Object.entries(files);
    const installed = [];
    for (const [source, content] of entries) {
      if (path.isAbsolute(source) || source.split(/[\\/]/).some((part) => part === "..")) throw new Error("Fixture payload member escapes its root");
      let target;
      if (scope === "global") target = at(runtimeRoot, source);
      else if (source.startsWith("openspec/")) target = at(storeRoot, source);
      else if (source.startsWith("skills/")) target = at(storeRoot, ".claude", source);
      else if (source.startsWith("agents/")) target = at(storeRoot, ".claude", source);
      else target = at(runtimeRoot, source);
      write(target, content);
      const purpose = source.startsWith("tools/") ? "tool" : source.startsWith("docs/") ? "doc" : source.startsWith("openspec/") ? "schema" : source.split("/")[0].replace(/s$/, "");
      installed.push({ path: target, sha256: createHash("sha256").update(content).digest("hex"), source, purpose });
    }
    const value = manifest ?? { format: 1, scope, generation, sourceVersion: "0.1.0-fixture", bootstrapApi: 1, runtimeApi: 1, schemaApi: 1, files: installed, clients: [] };
    if (!legacy) json(manifestPath, value);
    return { root: runtimeRoot, runtimeRoot, toolsRoot: at(runtimeRoot, "tools"), docsRoot: at(runtimeRoot, "docs"), schemaRoot: scope === "global" ? at(runtimeRoot, "openspec", "schemas", "symphysis") : at(storeRoot, "openspec", "schemas", "symphysis"), manifestPath: legacy ? null : manifestPath, manifest: legacy ? null : value, files: installed };
  }

  function cleanup() {
    noLinks(root);
    const inspect = (dir) => {
      for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
        if (entry.isSymbolicLink()) throw new Error("Refusing recursive fixture cleanup through a link");
        if (entry.isDirectory()) inspect(path.join(dir, entry.name));
      }
    };
    inspect(root);
    fs.rmSync(root, { recursive: true });
  }
  return { root, userDir, clientRoots, env, at, write, json, store, pointer, payload, cleanup };
}
