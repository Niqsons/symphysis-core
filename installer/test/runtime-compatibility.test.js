import { test } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { createHash } from "node:crypto";
import { checkRuntimeCompatibility, userSchemaDirectory } from "../lib/runtime-compatibility.js";
import { forkPin, runOpenspec } from "../lib/openspec-bin.js";
import { createRuntimeFixture } from "../test-support/runtime-fixture.js";

const fork = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..", "upstream", "openspec", "bin", "openspec.js");
const requiresFork = { skip: !fs.existsSync(fork) };
const hash = (content) => createHash("sha256").update(content).digest("hex");
const schema = (name) => `name: ${name}\nversion: 1\ndescription: Synthetic fixture\nartifacts:\n  - id: proposal\n    generates: proposal.md\n    description: Proposal\n    template: proposal.md\n    requires: []\n`;

test("Windows native schema bases require an explicit drive or UNC share", { skip: process.platform !== "win32" }, () => {
  for (const base of ["\\fixture", "/fixture", "X:fixture"]) {
    assert.throws(() => userSchemaDirectory({ XDG_DATA_HOME: base }), /абсолютной/);
    assert.throws(() => userSchemaDirectory({ LOCALAPPDATA: base }), /абсолютной/);
    assert.throws(() => userSchemaDirectory({ USERPROFILE: base }), /абсолютной/);
  }
});

test("malformed context paths refuse before any fork or store read", () => {
  let calls = 0;
  const diagnostics = checkRuntimeCompatibility({
    scope: "global", store: { root: "relative", sourceCwd: "relative" },
    runtime: { root: "relative", toolsRoot: "relative", docsRoot: "relative", schemaRoot: "relative", manifestPath: null },
    resources: { schema: { name: "symphysis", path: "relative" } },
  }, { run: () => { calls++; throw new Error("Must not run"); } });
  assert.equal(diagnostics[0].code, "runtime-incompatible");
  assert.equal(calls, 0);
});

function setup(t, scope = "global", { declaration = true, legacy = false } = {}) {
  const f = createRuntimeFixture(path.join(os.tmpdir(), "symphysis-compatibility-tests"));
  t.after(() => f.cleanup());
  f.env.SYMPHYSIS_OPENSPEC = fork;
  const store = f.store("store-a", { declaration });
  const payload = f.payload(scope, { store, legacy });
  const file = path.join(payload.schemaRoot, "schema.yaml");
  f.write(file, schema("symphysis"));
  if (!legacy) {
    payload.manifest.files.find((entry) => entry.path === file).sha256 = hash(fs.readFileSync(file));
    payload.manifest.openspecPin = forkPin().openspecPin;
    f.json(payload.manifestPath, payload.manifest);
  }
  if (scope === "global") f.write(f.at("user-data", "openspec", "schemas", "symphysis", "schema.yaml"), fs.readFileSync(file));
  const context = {
    format: 1, status: "ready", scope,
    store: { root: store.root, sourceCwd: store.root, id: null },
    runtime: { root: payload.root, toolsRoot: payload.toolsRoot, docsRoot: payload.docsRoot, schemaRoot: payload.schemaRoot, manifestPath: payload.manifestPath, generation: legacy ? "legacy-local" : payload.manifest.generation, legacy, sourceVersion: payload.manifest?.sourceVersion ?? null, bootstrapApi: 1, runtimeApi: 1, schemaApi: 1, journalContract: 1 },
    resources: { schema: { name: "symphysis", path: payload.schemaRoot } },
    compatibility: { status: "unconfirmed", declarationPath: null }, diagnostics: [], clients: [],
  };
  return { f, store, payload, context };
}

function snapshot(root) {
  const result = [];
  const walk = (dir, prefix = "") => {
    for (const entry of fs.readdirSync(dir, { withFileTypes: true }).sort((a, b) => a.name.localeCompare(b.name))) {
      const name = `${prefix}/${entry.name}`;
      if (entry.isSymbolicLink()) result.push([name, fs.readlinkSync(path.join(dir, entry.name))]);
      else if (entry.isDirectory()) { result.push([name, "directory"]); walk(path.join(dir, entry.name), name); }
      else result.push([name, hash(fs.readFileSync(path.join(dir, entry.name)))]);
    }
  };
  walk(root);
  return result;
}

function check(state, options = {}) {
  const { f, context } = state;
  const before = snapshot(f.root);
  const unchangedContext = structuredClone(context);
  delete unchangedContext.compatibility;
  const diagnostics = checkRuntimeCompatibility(context, { env: f.env, ...options });
  assert.deepEqual(snapshot(f.root), before, "preflight must not write any fixture file");
  const after = structuredClone(context);
  delete after.compatibility;
  assert.deepEqual(after, unchangedContext, "only compatibility may be changed");
  for (const item of diagnostics) assert.ok(item.code && item.message && item.action);
  return diagnostics;
}

for (const scope of ["local", "global"]) {
  test(`${scope}: actual pinned schema and version pass without writes`, requiresFork, (t) => {
    const state = setup(t, scope, { declaration: scope === "global" });
    const calls = [];
    const diagnostics = check(state, { change: state.store.change, run: (args, options) => { calls.push({ args, options }); return runOpenspec(args, options); } });
    assert.deepEqual(diagnostics, []);
    assert.equal(state.context.compatibility.status, "compatible");
    assert.ok(calls.some(({ args }) => args[0] === "status"));
    assert.ok(calls.every(({ options }) => options.cwd === state.store.root && options.env === state.f.env));
    assert.equal(fs.existsSync(path.join(state.store.changeRoot, "proposal.md")), false, "status works before the first planned artifact");
  });
}

test("legacy local does not require a global declaration or global runtime", requiresFork, (t) => {
  const state = setup(t, "local", { declaration: false, legacy: true });
  assert.deepEqual(check(state, { change: state.store.change }), []);
  assert.equal(state.context.compatibility.declarationPath, null);
});

for (const [label, declaration, expected] of [
  ["missing", undefined, "declaration-missing"],
  ["invalid-json", "{broken", "declaration-incompatible"],
  ["unknown-format", { format: 2, runtimeApi: 1, schemaApi: 1 }, "declaration-incompatible"],
  ["unknown-runtime-api", { format: 1, runtimeApi: 2, schemaApi: 1 }, "declaration-incompatible"],
  ["unknown-schema-api", { format: 1, runtimeApi: 1, schemaApi: 2 }, "declaration-incompatible"],
  ["null", null, "declaration-incompatible"],
]) {
  test(`global declaration ${label} refuses without writes`, requiresFork, (t) => {
    const state = setup(t, "global", { declaration: false });
    const file = path.join(state.store.root, "openspec", "symphysis.json");
    if (typeof declaration === "string") state.f.write(file, declaration);
    else if (declaration !== undefined) state.f.json(file, declaration);
    assert.equal(check(state)[0].code, expected);
    assert.equal(state.context.compatibility.status, label === "missing" ? "unconfirmed" : "incompatible");
  });
}

for (const api of ["bootstrapApi", "runtimeApi", "schemaApi"]) {
  test(`unknown selected ${api} refuses both scopes`, requiresFork, (t) => {
    for (const scope of ["local", "global"]) {
      const state = setup(t, scope);
      state.context.runtime[api] = 2;
      assert.equal(check(state)[0].code, "runtime-incompatible");
    }
  });
}

test("manifest pin incompatible with bootstrap and actual wrong fork version refuse", requiresFork, (t) => {
  const state = setup(t);
  const manifest = { ...state.payload.manifest, openspecPin: "0.0.0+foreign" };
  state.f.json(state.payload.manifestPath, manifest);
  assert.equal(check(state)[0].code, "runtime-incompatible");
  state.f.json(state.payload.manifestPath, state.payload.manifest);
  const wrongFork = state.f.write(state.f.at("wrong-fork.js"), 'console.log("0.0.0+foreign");\n');
  state.f.env.SYMPHYSIS_OPENSPEC = wrongFork;
  assert.equal(check(state)[0].code, "fork-incompatible");
});

test("missing, shadowed and changed user schemas refuse without deleting the conflict", requiresFork, (t) => {
  const state = setup(t);
  const user = state.f.at("user-data", "openspec", "schemas", "symphysis", "schema.yaml");
  fs.unlinkSync(user);
  assert.equal(check(state)[0].code, "schema-source-conflict");
  state.f.write(user, `${schema("symphysis")}# foreign\n`);
  assert.equal(check(state)[0].code, "schema-source-conflict");
  state.f.write(user, schema("symphysis"));
  const project = state.f.write(path.join(state.store.root, "openspec", "schemas", "symphysis", "schema.yaml"), schema("symphysis"));
  assert.equal(check(state)[0].code, "schema-source-conflict");
  assert.ok(fs.existsSync(project));
});

test("project shadow in the store is detected even when original cwd is a pointer", requiresFork, (t) => {
  const state = setup(t);
  state.context.store.sourceCwd = state.f.pointer("source-a", state.store.id);
  state.f.write(path.join(state.store.root, "openspec", "schemas", "symphysis", "schema.yaml"), schema("symphysis"));
  assert.equal(check(state)[0].code, "schema-source-conflict");
});

test("metadata overrides config; a foreign existing schema and an overriding late schema refuse", requiresFork, (t) => {
  const state = setup(t);
  state.f.write(path.join(state.store.root, "openspec", "config.yaml"), "schema: spec-driven\n");
  assert.deepEqual(check(state, { change: state.store.change }), []);
  state.f.write(path.join(state.store.changeRoot, ".openspec.yaml"), "schema: spec-driven\n");
  assert.equal(check(state, { change: state.store.change })[0].code, "schema-source-conflict");
  assert.equal(check(state, { tool: "openspec", args: ["status", "--change", state.store.change, "--schema", "symphysis"] })[0].code, "schema-source-conflict");
});

test("new checks config, explicit schema and yaml/yml precedence without creating a change", requiresFork, (t) => {
  const state = setup(t);
  const args = ["new", "change", "new-change"];
  assert.deepEqual(check(state, { tool: "openspec", args }), []);
  assert.deepEqual(check(state, { tool: "openspec", args: ["new", "change", "--schema", "symphysis", "--goal", "fixture goal", "new-change"] }), []);
  state.f.write(path.join(state.store.root, "openspec", "config.yml"), "schema: spec-driven\n");
  assert.deepEqual(check(state, { tool: "openspec", args }), []);
  fs.unlinkSync(path.join(state.store.root, "openspec", "config.yaml"));
  assert.equal(check(state, { tool: "openspec", args })[0].code, "schema-source-conflict");
  assert.deepEqual(check(state, { tool: "openspec", args: [...args, "--schema=symphysis"] }), []);
  assert.equal(check(state, { tool: "openspec", args: [...args, "--schema=other-schema"] })[0].code, "schema-source-conflict");
  assert.equal(fs.existsSync(path.join(state.store.root, "openspec", "changes", "new-change")), false);
});

test("late store cannot redirect the selected root; repeated selectors and traversal refuse", requiresFork, (t) => {
  const state = setup(t);
  const second = state.f.store("store-b");
  for (const args of [
    ["new", "change", "x", "--store", second.id],
    ["new", "change", "x", `--store=${second.id}`],
    ["new", "change", "x", "--store-path", second.root],
    ["new", "change", "x", "--store", state.store.id, "--store", state.store.id],
    ["new", "change", "x", "--schema", "symphysis", "--schema", "symphysis"],
    ["status", "--change", "../../other"],
  ]) assert.equal(check(state, { tool: "openspec", args })[0].code, "selector-conflict");
  assert.deepEqual(check(state, { tool: "openspec", args: ["new", "change", "x", "--store", state.store.id] }), []);
});

test("archived journal validates its own metadata and does not require active status", requiresFork, (t) => {
  const state = setup(t);
  const archive = state.f.at(state.store.root, "openspec", "changes", "archive", "2026-11-09-old-change");
  const journal = state.f.json(path.join(archive, "decisions.json"), { title: "Archive fixture", source: "decisions.json", records: [] });
  const metadata = state.f.write(path.join(archive, ".openspec.yaml"), "schema: symphysis\n");
  const run = (args, options) => {
    assert.notEqual(args[0], "status", "archive checker must not invent an active change");
    return runOpenspec(args, options);
  };
  assert.deepEqual(check(state, { tool: "journal", journal, run }), []);
  fs.unlinkSync(metadata);
  assert.deepEqual(check(state, { tool: "journal", journal, run }), []);
  state.f.write(metadata, "schema: spec-driven\n");
  assert.equal(check(state, { tool: "journal", journal, run })[0].code, "schema-source-conflict");
});

test("a schema-less metadata file is invalid under pinned status, unlike no metadata file", requiresFork, (t) => {
  const state = setup(t);
  state.f.write(path.join(state.store.changeRoot, ".openspec.yaml"), "created: 2026-11-09\n");
  const actual = runOpenspec(["status", "--change", state.store.change, "--json"], { cwd: state.store.root, env: state.f.env });
  assert.notEqual(actual.status, 0);
  assert.equal(check(state, { change: state.store.change })[0].code, "schema-source-conflict");
});

test("malformed planning config refuses new before any native write", requiresFork, (t) => {
  const state = setup(t);
  state.f.write(path.join(state.store.root, "openspec", "config.yaml"), "schema: [broken\n");
  assert.equal(check(state, { tool: "openspec", args: ["new", "change", "new-change"] })[0].code, "schema-source-conflict");
});

test("a change junction cannot redirect status or journal reads outside the store", requiresFork, (t) => {
  const state = setup(t);
  const foreign = state.f.at("foreign-change");
  state.f.write(path.join(foreign, ".openspec.yaml"), "schema: symphysis\n");
  const journal = state.f.json(path.join(foreign, "decisions.json"), { title: "Foreign fixture", source: "decisions.json", records: [] });
  const link = path.join(state.store.root, "openspec", "changes", "redirected-change");
  fs.symlinkSync(foreign, link, process.platform === "win32" ? "junction" : "dir");
  try {
    assert.equal(check(state, { change: "redirected-change" })[0].code, "selector-conflict");
    assert.equal(check(state, { journal: path.join(link, path.basename(journal)) })[0].code, "selector-conflict");
  } finally { fs.unlinkSync(link); }
});

for (const scope of ["local", "global"]) for (const metadata of [false, true]) test(`${scope}: an existing Unicode/space directory uses real native status with metadata=${metadata}`, requiresFork, (t) => {
  const state = setup(t, scope);
  const name = "изменение один";
  const directory = path.join(state.store.root, "openspec", "changes", name);
  fs.renameSync(state.store.changeRoot, directory);
  if (!metadata) fs.unlinkSync(path.join(directory, ".openspec.yaml"));
  const calls = [];
  const run = (args, options) => { calls.push(args); return runOpenspec(args, options); };
  const journal = path.join(directory, "decisions.json");
  assert.deepEqual(check(state, { tool: "journal", args: ["view-json", journal], journal, run }), []);
  assert.deepEqual(check(state, { tool: "openspec", args: ["instructions", "apply", "--change", name, "--json"], run }), []);
  assert.ok(calls.some((args) => args[0] === "status" && args[2] === name));
  const actual = runOpenspec(["instructions", "apply", "--change", name, "--json"], { cwd: state.store.root, env: state.f.env });
  assert.equal(actual.status, 0, actual.stderr);
  assert.equal(JSON.parse(actual.stdout).schemaName, "symphysis");
  assert.equal(check(state, { tool: "openspec", args: ["new", "change", name] })[0].code, "selector-conflict");
  for (const invalid of ["..", "../outside", "nested/name", "nested\\name", "C:relative", "bad\0name"]) assert.equal(check(state, { change: invalid })[0].code, "selector-conflict");
});

test("a registered schema projection agrees with canonical bytes and its native target", requiresFork, (t) => {
  const state = setup(t);
  const canonical = state.payload.manifest.files.find((entry) => entry.source === "openspec/schemas/symphysis/schema.yaml");
  const projection = { ...canonical, path: state.f.at("user-data", "openspec", "schemas", "symphysis", "schema.yaml"), projection: true };
  state.payload.manifest.files.push(projection);
  state.f.json(state.payload.manifestPath, state.payload.manifest);
  assert.deepEqual(check(state), []);
  projection.path = state.f.at("foreign-schema.yaml");
  state.f.json(state.payload.manifestPath, state.payload.manifest);
  assert.equal(check(state)[0].code, "schema-source-conflict");
});

test("malformed JSON, relative native schema base and a changed generation refuse", requiresFork, (t) => {
  const state = setup(t);
  assert.equal(check(state, { run: (args, options) => args[0] === "schema" ? { status: 0, stdout: "not-json", stderr: "" } : runOpenspec(args, options) })[0].code, "schema-source-conflict");
  state.f.env.XDG_DATA_HOME = "relative";
  assert.equal(check(state)[0].code, "schema-source-conflict");
  state.context.runtime.generation = "stale-generation";
  assert.equal(check(state)[0].code, "runtime-incompatible");
});
