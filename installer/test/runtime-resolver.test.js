import { test } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { spawnSync } from "node:child_process";
import { createRuntimeFixture } from "../test-support/runtime-fixture.js";
import { resolveRuntime, userDirectory } from "../lib/runtime-resolver.js";

const fork = fileURLToPath(new URL("../../upstream/openspec/bin/openspec.js", import.meta.url));
const bin = fileURLToPath(new URL("../bin/symphysis.js", import.meta.url));
function fixture(t) {
  const value = createRuntimeFixture(path.join(os.tmpdir(), "symphysis-resolver-tests"));
  value.env.SYMPHYSIS_OPENSPEC = fork;
  t.after(() => value.cleanup());
  return value;
}
const resolve = (f, options) => resolveRuntime({ env: f.env, ...options });
const contents = (root) => {
  const value = {};
  const visit = (dir) => { for (const item of fs.readdirSync(dir, { withFileTypes: true })) {
    const file = path.join(dir, item.name);
    if (item.isDirectory()) visit(file);
    else if (item.isFile()) value[path.relative(root, file)] = fs.readFileSync(file).toString("base64");
  } };
  visit(root); return value;
};

test("local-only uses its own runtime without a global declaration or a valid global override", (t) => {
  const f = fixture(t); const store = f.store("store-a", { declaration: false });
  const local = f.payload("local", { store });
  const before = contents(store.root);
  const result = resolveRuntime({ project: store.root, env: { ...f.env, SYMPHYSIS_HOME: "invalid-relative" } });
  assert.equal(result.status, "ready", JSON.stringify(result.diagnostics));
  assert.equal(result.scope, "local");
  assert.equal(result.runtime.root, local.root);
  assert.equal(result.runtime.journalContract, 1);
  assert.equal(result.resources.skills["symphysis-brainstorm"], path.join(store.root, ".claude", "skills", "symphysis-brainstorm", "SKILL.md"));
  assert.equal(result.compatibility.declarationPath, null);
  assert.deepEqual(contents(store.root), before);
});

test("local wins over global, including a legacy installation without a manifest", (t) => {
  const f = fixture(t); f.payload("global");
  for (const legacy of [false, true]) {
    const store = f.store(legacy ? "legacy" : "managed");
    const local = f.payload("local", { store, legacy });
    const result = resolve(f, { project: store.root });
    assert.equal(result.status, "ready", JSON.stringify(result.diagnostics));
    assert.equal(result.scope, "local");
    assert.equal(result.runtime.root, local.root);
    assert.equal(result.runtime.legacy, legacy);
    assert.equal(result.runtime.manifestPath, local.manifestPath);
    if (legacy) assert.equal(result.runtime.generation, "legacy-local");
  }
});

test("a damaged local runtime never borrows the intact global tools", (t) => {
  const f = fixture(t); const store = f.store("store-a");
  const local = f.payload("local", { store }); f.payload("global");
  fs.unlinkSync(path.join(local.toolsRoot, "journal.py"));
  let result = resolve(f, { project: store.root });
  assert.equal(result.status, "blocked"); assert.equal(result.scope, "local");
  assert.equal(result.diagnostics[0].code, "local-damaged");
  assert.equal(result.resources.tools.journal, undefined);
  fs.writeFileSync(local.manifestPath, "{");
  result = resolve(f, { project: store.root });
  assert.equal(result.scope, "local"); assert.equal(result.diagnostics[0].code, "manifest-invalid");
});

test("any known incomplete legacy entrypoint selects local rather than global", (t) => {
  const f = fixture(t); const store = f.store("store-a"); f.payload("global");
  f.write(path.join(store.root, ".symphysis", "tools", "roots.py"), "# incomplete local\n");
  const result = resolve(f, { project: store.root });
  assert.equal(result.scope, "local"); assert.equal(result.status, "blocked");
  assert.equal(result.diagnostics[0].code, "local-damaged");
});

test("data-only roots maps and drafts do not become a local runtime", (t) => {
  const f = fixture(t); const store = f.store("store-a", { dataOnly: true });
  f.write(path.join(store.root, ".symphysis", "viewer", "draft.json"), '{"word":"keep"}\n');
  const global = f.payload("global");
  const before = contents(store.root);
  const result = resolve(f, { project: store.root });
  assert.equal(result.scope, "global"); assert.equal(result.runtime.root, global.root);
  assert.equal(result.store.root, store.root);
  assert.deepEqual(contents(store.root), before);
});

test("the pinned context selects a pointer, nested cwd and explicit store", (t) => {
  const f = fixture(t); const first = f.store("store-a"); const second = f.store("store-b");
  const pointer = f.pointer("source", first.id); f.payload("global");
  const nested = path.join(pointer, "src"); fs.mkdirSync(nested);
  const fromPointer = resolve(f, { project: nested });
  assert.equal(fromPointer.store.root, first.root); assert.equal(fromPointer.store.sourceCwd, nested);
  const explicit = resolve(f, { project: nested, store: second.id });
  assert.equal(explicit.store.root, second.root);
  assert.equal(explicit.store.id, second.id);
  assert.deepEqual(fs.readdirSync(path.join(pointer, "openspec")), ["config.yaml"]);
});

test("an addressed journal selects its store before changing cwd, and explicit conflicts refuse", (t) => {
  const f = fixture(t); const first = f.store("store-a"); const second = f.store("store-b");
  f.payload("global");
  const addressed = resolve(f, { journal: first.journal });
  assert.equal(addressed.store.root, first.root);
  const conflict = resolve(f, { project: second.root, journal: first.journal });
  assert.equal(conflict.status, "blocked"); assert.equal(conflict.diagnostics[0].code, "store-mismatch");
  assert.equal(resolve(f, { journal: f.at("elsewhere.json") }).diagnostics[0].code, "store-mismatch");
});

test("absence and partial global installs are diagnosed without creating an installation", (t) => {
  const f = fixture(t); const store = f.store("store-a", { dataOnly: true });
  const before = contents(f.root);
  let result = resolve(f, { project: store.root });
  assert.equal(result.scope, null); assert.equal(result.diagnostics[0].code, "runtime-missing");
  assert.deepEqual(contents(f.root), before);
  fs.mkdirSync(path.join(f.userDir, "runtime"), { recursive: true });
  result = resolve(f, { project: store.root });
  assert.equal(result.scope, "global"); assert.equal(result.status, "blocked");
  assert.equal(result.diagnostics[0].code, "manifest-invalid");
});

test("a journal junction cannot address another store through a selected store", (t) => {
  const f = fixture(t); const first = f.store("store-a"); const second = f.store("store-b");
  f.payload("local", { store: first });
  const junction = path.join(first.root, "openspec", "changes", "redirect");
  fs.symlinkSync(second.changeRoot, junction, process.platform === "win32" ? "junction" : "dir");
  try {
    for (const file of ["decisions.json", "not-created.json"]) {
      const result = resolve(f, { project: first.root, journal: path.join(junction, file) });
      assert.equal(result.status, "blocked"); assert.equal(result.diagnostics[0].code, "store-mismatch");
    }
  } finally { fs.unlinkSync(junction); }
});

test("unreadable or unknown context JSON does not fall back to cwd", (t) => {
  const f = fixture(t); const store = f.store("store-a"); f.payload("local", { store });
  for (const response of [{ status: 0, stdout: "{}" }, { status: 0, stdout: "{" }, { notFound: true }]) {
    const result = resolveRuntime({ project: store.root, env: f.env, run: () => response });
    assert.equal(result.status, "blocked"); assert.equal(result.runtime, null);
    assert.equal(result.diagnostics[0].code, "planning-root-invalid");
  }
});

test("manifest resources cannot redirect a tool or register personal data", (t) => {
  const f = fixture(t); const store = f.store("store-a"); const local = f.payload("local", { store });
  const foreign = f.write(f.at("foreign.py"), "# keep\n");
  const manifest = structuredClone(local.manifest);
  manifest.files[0].path = foreign;
  f.json(local.manifestPath, manifest);
  assert.equal(resolve(f, { project: store.root }).diagnostics[0].code, "manifest-invalid");
  manifest.files[0].source = "tools/journal-roots.json";
  f.json(local.manifestPath, manifest);
  assert.equal(resolve(f, { project: store.root }).diagnostics[0].code, "manifest-invalid");
  assert.equal(fs.readFileSync(foreign, "utf8"), "# keep\n");
});

test("a file outside the manifest is not an accepted schema or tool", (t) => {
  const f = fixture(t); const store = f.store("store-a"); const local = f.payload("local", { store });
  for (const source of ["tools/journal.py", "openspec/schemas/symphysis/schema.yaml"]) {
    f.json(local.manifestPath, { ...local.manifest, files: local.manifest.files.filter((entry) => entry.source !== source) });
    const result = resolve(f, { project: store.root });
    assert.equal(result.status, "blocked"); assert.equal(result.diagnostics[0].code, "local-damaged");
  }
});

test("CLI discovery and library selection share one local context and stay read-only", (t) => {
  const f = fixture(t); const store = f.store("store-a"); f.payload("local", { store });
  const pointer = f.pointer("source", store.id);
  const before = contents(f.root);
  const expected = resolve(f, { project: pointer });
  for (const args of [["resolve", "--project", pointer, "--json"], ["--project", pointer, "preflight", "--json"]]) {
    const cli = spawnSync(process.execPath, [bin, ...args], { cwd: f.root, env: f.env, encoding: "utf8" });
    assert.equal(cli.status, 0, cli.stderr);
    assert.deepEqual(JSON.parse(cli.stdout), expected);
  }
  assert.deepEqual(contents(f.root), before);
});

test("CLI global discovery gives a structured blocked response without a selected runtime", (t) => {
  const f = fixture(t); const store = f.store("store-a");
  const cli = spawnSync(process.execPath, [bin, "resolve", "--project", store.root, "--json"], { env: f.env, encoding: "utf8" });
  assert.equal(cli.status, 2, cli.stderr);
  const response = JSON.parse(cli.stdout);
  assert.equal(response.status, "blocked"); assert.equal(response.diagnostics[0].code, "runtime-missing");
  assert.equal(response.store.root, store.root);
});

test("global CLI and pointer select one compatible generation without project runtime", (t) => {
  const f = fixture(t); const store = f.store("store-a", { dataOnly: true });
  const global = f.payload("global");
  f.write(f.at("user-data", "openspec", "schemas", "symphysis", "schema.yaml"), fs.readFileSync(path.join(global.schemaRoot, "schema.yaml")));
  const pointer = f.pointer("source", store.id);
  const before = contents(f.root);
  const result = resolve(f, { project: pointer });
  assert.equal(result.status, "ready", JSON.stringify(result.diagnostics));
  assert.equal(result.runtime.root, global.root); assert.equal(result.store.root, store.root);
  assert.equal(result.compatibility.status, "compatible");
  const cli = spawnSync(process.execPath, [bin, "resolve", "--project", pointer, "--json"], { env: f.env, encoding: "utf8" });
  assert.equal(cli.status, 0, cli.stderr); assert.deepEqual(JSON.parse(cli.stdout), result);
  assert.deepEqual(contents(f.root), before);
  assert.equal(fs.existsSync(path.join(store.root, ".symphysis", "tools", "journal.py")), false);
});

test("managed global projections are verified while resource lookup stays canonical", (t) => {
  const f = fixture(t); const store = f.store("store-a"); const global = f.payload("global");
  const manifest = structuredClone(global.manifest);
  const schemaEntry = manifest.files.find((entry) => entry.source.endsWith("schema.yaml"));
  const skillEntry = manifest.files.find((entry) => entry.source.endsWith("SKILL.md"));
  const schemaPath = f.write(f.at("user-data", "openspec", "schemas", "symphysis", "schema.yaml"), fs.readFileSync(schemaEntry.path));
  const skillPath = f.write(path.join(f.clientRoots.codex.skills, "symphysis-brainstorm", "SKILL.md"), fs.readFileSync(skillEntry.path));
  manifest.clients.push({ id: "codex", skillsRoot: f.clientRoots.codex.skills, agentsRoot: f.clientRoots.codex.agents });
  manifest.files.push({ ...schemaEntry, projection: true, path: schemaPath }, { ...skillEntry, projection: true, clientId: "codex", path: skillPath });
  f.json(global.manifestPath, manifest);
  const result = resolve(f, { project: store.root });
  assert.equal(result.status, "ready", JSON.stringify(result.diagnostics));
  assert.equal(result.resources.skills["symphysis-brainstorm"], skillEntry.path);
  fs.writeFileSync(skillPath, "# user edit\n");
  assert.equal(resolve(f, { project: store.root }).status, "blocked");
  assert.equal(fs.readFileSync(skillPath, "utf8"), "# user edit\n");
});

test("user data bases are absolute and independent of client roots", () => {
  const base = path.resolve(os.tmpdir(), "synthetic-profile");
  assert.equal(userDirectory({ SYMPHYSIS_HOME: base }), base);
  assert.equal(userDirectory({ XDG_DATA_HOME: base }), path.join(base, "symphysis"));
  assert.equal(userDirectory({ LOCALAPPDATA: base }, "win32"), path.join(base, "symphysis"));
  assert.equal(userDirectory({}, "linux", base), path.join(base, ".local", "share", "symphysis"));
  for (const name of ["SYMPHYSIS_HOME", "XDG_DATA_HOME", "LOCALAPPDATA"]) assert.throws(() => userDirectory({ [name]: "relative" }, "win32"), /абсолютный/);
});

test("read-only discovery refuses writer and incomplete transaction state before first rename", (t) => {
  for (const scope of ["local", "global"]) {
    const f = fixture(t); const store = f.store("store-a");
    const payload = f.payload(scope, { store });
    const management = scope === "local" ? payload.root : f.userDir;
    for (const name of [".install-lock", ".install-transaction.json"]) {
      const file = f.json(path.join(management, name), { owner: "unconfirmed" });
      const before = fs.readFileSync(file);
      const result = resolve(f, { project: store.root });
      assert.equal(result.status, "blocked"); assert.equal(result.diagnostics[0].code, "installation-busy");
      assert.deepEqual(fs.readFileSync(file), before);
      fs.unlinkSync(file);
    }
  }
});

test("Windows user bases reject current-drive and drive-relative roots", { skip: process.platform !== "win32" }, () => {
  for (const name of ["SYMPHYSIS_HOME", "XDG_DATA_HOME", "LOCALAPPDATA"]) {
    for (const base of ["\\fixture", "/fixture", "X:fixture"]) assert.throws(() => userDirectory({ [name]: base }, "win32"), /абсолютный/);
  }
});

test("Windows context and manifest paths cannot inherit the current drive", { skip: process.platform !== "win32" }, (t) => {
  const f = fixture(t);
  const store = f.store("store-a");
  const local = f.payload("local", { store });
  const contextResult = resolveRuntime({ project: store.root, env: f.env, run: () => ({ status: 0, stdout: JSON.stringify({ root: { role: "openspec_root", source: "nearest", path: store.root.slice(2) } }) }) });
  assert.equal(contextResult.diagnostics[0].code, "planning-root-invalid");
  for (const change of ["file", "client", "bootstrap"]) {
    const manifest = structuredClone(local.manifest);
    if (change === "file") manifest.files[0].path = manifest.files[0].path.slice(2);
    if (change === "client") manifest.clients.push({ id: "claude", skillsRoot: "\\fixture" });
    if (change === "bootstrap") manifest.bootstrap = { command: "\\fixture\\node.exe", args: [] };
    f.json(local.manifestPath, manifest);
    const result = resolve(f, { project: store.root });
    assert.equal(result.scope, "local");
    assert.equal(result.diagnostics[0].code, "manifest-invalid", change);
  }
});
