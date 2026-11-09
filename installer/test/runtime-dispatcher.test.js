import { test } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { createHash } from "node:crypto";
import { spawn, spawnSync } from "node:child_process";
import { once } from "node:events";
import { fileURLToPath } from "node:url";
import { createRuntimeFixture } from "../test-support/runtime-fixture.js";
import { resolveRuntime } from "../lib/runtime-resolver.js";
import { toolArguments } from "../lib/runtime-dispatcher.js";
import { acquireWriter, managementRoot } from "../lib/runtime-leases.js";

const bin = fileURLToPath(new URL("../bin/symphysis.js", import.meta.url));
const fork = process.env.SYMPHYSIS_OPENSPEC || fileURLToPath(new URL("../../upstream/openspec/bin/openspec.js", import.meta.url));
const schema = "name: symphysis\nversion: 1\ndescription: Fixture\nartifacts:\n  - id: intent\n    generates: intent.md\n    description: Intent\n    template: intent.md\n    requires: []\n";
const echo = `import json, os, sys, time
context = json.loads(os.environ['SYMPHYSIS_RUNTIME_CONTEXT'])
with open(context['lease']['file'], encoding='utf-8') as stream:
    lease = json.load(stream)
print(json.dumps({'cwd': os.getcwd(), 'argv': sys.argv[1:], 'store': context['store']['root'], 'runtime': context['runtime']['root'], 'lease': lease['id'] == context['lease']['id'], 'generation': lease['generation']}), flush=True)
if '--wait' in sys.argv: time.sleep(1.5)
if '--code-seven' in sys.argv: sys.exit(7)
`;

function setup(t, scope = "global") {
  const f = createRuntimeFixture(path.join(os.tmpdir(), "symphysis-dispatcher-tests"));
  t.after(() => f.cleanup()); f.env.SYMPHYSIS_OPENSPEC = fork;
  const store = f.store("store-a"); const second = f.store("store-b");
  const payload = f.payload(scope, { store });
  const replace = (source, bytes) => {
    const entry = payload.manifest.files.find((entry) => entry.source === source);
    f.write(entry.path, bytes); entry.sha256 = createHash("sha256").update(bytes).digest("hex");
  };
  for (const name of ["journal.py", "step_help.py", "trace_graph.py", "anchor_refs.py", "symphysis_config.py"]) replace(`tools/${name}`, echo);
  replace("openspec/schemas/symphysis/schema.yaml", schema);
  f.json(payload.manifestPath, payload.manifest);
  if (scope === "global") f.write(f.at("user-data", "openspec", "schemas", "symphysis", "schema.yaml"), schema);
  const cli = (...args) => spawnSync(process.execPath, [bin, ...args], { cwd: f.root, env: f.env, encoding: "utf8", timeout: 15000 });
  return { f, store, second, payload, cli };
}

test("argv normalization keeps literal values, repeated flags and caller-relative paths", () => {
  const base = path.resolve(os.tmpdir(), "source");
  const args = ["apply", "openspec/changes/same-change/decisions.json", "word & 100% \"quote\".md", "--date", "2026-11-09", "--dry-run"];
  const result = toolArguments("journal", args, base);
  assert.deepEqual(result.args, ["apply", path.resolve(base, args[1]), path.resolve(base, args[2]), "--date", "2026-11-09", "--dry-run"]);
  assert.equal(result.journal, result.args[1]);
  assert.deepEqual(args.slice(-3), ["--date", "2026-11-09", "--dry-run"]);
  assert.deepEqual(toolArguments("journal", ["render-html", "j.json", "--attack=a.md", "--attack", "b.md", "--out", "--strict"], base).args.slice(2), ["--attack=" + path.resolve(base, "a.md"), "--attack", path.resolve(base, "b.md"), "--out", "--strict"]);
  assert.deepEqual(toolArguments("help", ["--change", "same-change", "--install-dir", "skills"], base).args, ["--change", "same-change", "--install-dir", path.resolve(base, "skills")]);
  assert.deepEqual(toolArguments("trace", ["check", "same-change", "graph.json"], base).args, ["check", "same-change", path.resolve(base, "graph.json")]);
});

for (const scope of ["local", "global"]) test(`${scope}: journal child uses selected cwd, normalized argv, context and a live lease`, (t) => {
  const { f, store, payload, cli } = setup(t, scope);
  const answer = f.write(f.at("answer & 100% \"quote\".md".replaceAll('"', "'")), "Fixture word\n");
  const response = cli("--project", store.root, "journal", "apply", store.journal, answer, "--date", "2026-11-09", "--dry-run");
  assert.equal(response.status, 0, response.stderr);
  const data = JSON.parse(response.stdout);
  assert.equal(data.cwd.toLowerCase(), store.root.toLowerCase());
  assert.equal(data.store, store.root); assert.equal(data.runtime, payload.root); assert.equal(data.lease, true);
  assert.deepEqual(data.argv, ["apply", store.journal, answer, "--date", "2026-11-09", "--dry-run"]);
  const management = scope === "global" ? f.userDir : payload.root;
  assert.deepEqual(fs.readdirSync(path.join(management, ".leases")), []);
});

test("an addressed global journal keeps two same-name changes separate from another cwd", (t) => {
  const { store, second, cli } = setup(t);
  for (const selected of [store, second]) {
    const response = cli("journal", "view-json", selected.journal);
    assert.equal(response.status, 0, response.stderr);
    const data = JSON.parse(response.stdout);
    assert.equal(data.store, selected.root); assert.equal(data.argv[1], selected.journal);
  }
  const conflict = cli("--project", store.root, "journal", "view-json", second.journal);
  assert.equal(conflict.status, 2); assert.match(conflict.stderr, /store-mismatch/);
});

test("help/trace/anchors dispatch through the same selected runtime", (t) => {
  const { store, payload, cli } = setup(t);
  for (const [tool, argv] of [["help", ["--change", store.change]], ["trace", ["build", store.change, "--format", "mermaid"]], ["anchors", [store.change]]]) {
    const response = cli("--project", store.root, tool, ...argv);
    assert.equal(response.status, 0, response.stderr);
    const data = JSON.parse(response.stdout);
    assert.equal(data.runtime, payload.root); assert.equal(data.store, store.root); assert.equal(data.lease, true);
    assert.deepEqual(data.argv, argv);
  }
});

test("resource reads only the selected named text and unknown identifiers fail explicitly", (t) => {
  const { f, store, payload, cli } = setup(t);
  const text = fs.readFileSync(path.join(payload.docsRoot, "terms.md"), "utf8");
  const response = cli("--project", store.root, "resource", "doc", "terms.md");
  assert.equal(response.status, 0, response.stderr); assert.equal(response.stdout, text);
  for (const id of ["missing.md", "../../elsewhere", path.join(f.root, "arbitrary.md")]) {
    const missing = cli("--project", store.root, "resource", "doc", id);
    assert.equal(missing.status, 2); assert.match(missing.stderr, /resource-missing/); assert.equal(missing.stdout, "");
  }
});

for (const scope of ["local", "global"]) test(`${scope}: journal schema doc returns installed canonical bytes and refuses a changed copy`, (t) => {
  const f = createRuntimeFixture(path.join(os.tmpdir(), "symphysis-schema-resource"));
  t.after(() => f.cleanup()); f.env.SYMPHYSIS_OPENSPEC = fork;
  const store = f.store("store-a");
  const payload = f.payload(scope, { store, payloadDir: fileURLToPath(new URL("../payload/", import.meta.url)) });
  if (scope === "global") fs.cpSync(payload.schemaRoot, f.at("user-data", "openspec", "schemas", "symphysis"), { recursive: true });
  const canonical = fs.readFileSync(new URL("../../decisions/journal.schema.json", import.meta.url));
  const cli = (...args) => spawnSync(process.execPath, [bin, "--project", store.root, ...args], { cwd: f.root, env: f.env, timeout: 20000 });
  const response = cli("resource", "doc", "journal.schema.json");
  assert.equal(response.status, 0, response.stderr.toString());
  assert.deepEqual(response.stdout, canonical);
  const context = resolveRuntime({ project: store.root, env: f.env });
  assert.equal(context.resources.docs["journal.schema.json"], path.join(payload.docsRoot, "journal.schema.json"));
  assert.equal(context.runtime.runtimeApi, 1); assert.equal(context.runtime.schemaApi, 1);
  const journal = cli("journal", "view-json", store.journal);
  assert.equal(journal.status, 0, journal.stderr.toString());
  assert.equal(JSON.parse(journal.stdout).title, "Fixture store-a");
  fs.appendFileSync(path.join(payload.docsRoot, "journal.schema.json"), " ");
  const changed = cli("resource", "doc", "journal.schema.json");
  assert.equal(changed.status, 2); assert.equal(changed.stdout.length, 0);
  assert.match(changed.stderr.toString(), scope === "local" ? /local-damaged/ : /resource-missing/);
  assert.match(changed.stderr.toString(), /docs\/journal\.schema\.json/);
});

test("native OpenSpec runs the pinned fork in the chosen store and preserves its JSON", (t) => {
  const { store, cli } = setup(t);
  const response = cli("--project", store.root, "openspec", "list", "--json");
  assert.equal(response.status, 0, response.stderr);
  assert.equal(JSON.parse(response.stdout).root.path, store.root);
  for (const args of [["new", "change", "must-not-exist", "--store", "store-b"], ["new", "change", "must-not-exist", "--schema", "spec-driven"]]) {
    const blocked = cli("--project", store.root, "openspec", ...args);
    assert.equal(blocked.status, 2); assert.equal(fs.existsSync(path.join(store.root, "openspec", "changes", "must-not-exist")), false);
  }
});

test("blocked compatibility does not launch Python or modify store data", (t) => {
  const { f, store, cli } = setup(t);
  const before = fs.readFileSync(store.journal);
  f.json(path.join(store.root, "openspec", "symphysis.json"), { format: 1, runtimeApi: 900, schemaApi: 1 });
  const response = cli("--project", store.root, "journal", "view-json", store.journal);
  assert.equal(response.status, 2); assert.match(response.stderr, /declaration-incompatible/); assert.equal(response.stdout, "");
  assert.deepEqual(fs.readFileSync(store.journal), before); assert.equal(fs.existsSync(path.join(f.userDir, ".leases")), false);
});

test("the dispatcher returns the child's exit code after releasing its lease", (t) => {
  const { f, store, cli } = setup(t);
  const response = cli("--project", store.root, "journal", "view-json", store.journal, "--code-seven");
  assert.equal(response.status, 7, response.stderr);
  assert.deepEqual(fs.readdirSync(path.join(f.userDir, ".leases")), []);
});

test("a live dispatcher child blocks updates until completion", async (t) => {
  const { f, store } = setup(t);
  const context = resolveRuntime({ project: store.root, env: f.env });
  const child = spawn(process.execPath, [bin, "--project", store.root, "journal", "view-json", store.journal, "--wait"], { cwd: f.root, env: f.env, stdio: ["ignore", "pipe", "pipe"] });
  const closed = once(child, "close");
  let output = ""; child.stdout.on("data", (chunk) => { output += chunk; });
  while (!output.includes("\n")) {
    if (child.exitCode !== null) assert.fail("dispatcher exited before child readiness");
    await new Promise((resolve) => setTimeout(resolve, 20));
  }
  assert.equal(JSON.parse(output.trim()).lease, true);
  assert.throws(() => acquireWriter({ root: managementRoot(context) }), (error) => error.code === "installation-busy");
  const [code] = await closed; assert.equal(code, 0);
  const writer = acquireWriter({ root: managementRoot(context) }); assert.equal(writer.release(), true);
});

test("an IDE control request cancels the actual dispatcher child and releases its lease", async (t) => {
  const { f, store } = setup(t);
  const control = f.at("cancel.json");
  const record = { format: 1, id: "owned-host-operation", token: "a".repeat(64), cancel: false };
  f.json(control, record);
  const child = spawn(process.execPath, [bin, "--project", store.root, "journal", "view-json", store.journal, "--wait"], { cwd: f.root, env: { ...f.env, SYMPHYSIS_CANCEL_FILE: control }, stdio: ["ignore", "pipe", "pipe"] });
  const closed = once(child, "close");
  let output = ""; let errors = "";
  child.stdout.on("data", (chunk) => { output += chunk; }); child.stderr.on("data", (chunk) => { errors += chunk; });
  while (!output.includes("\n")) {
    if (child.exitCode !== null) assert.fail(`dispatcher exited before readiness: ${errors}`);
    await new Promise((resolve) => setTimeout(resolve, 20));
  }
  f.json(control, { ...record, cancel: true });
  const [code] = await closed; assert.equal(code, 130, errors);
  assert.deepEqual(fs.readdirSync(path.join(f.userDir, ".leases")), []);
  assert.equal(fs.existsSync(control), true, "the host owns cleanup of its control file");
});

test("an invalid or already-cancelled control does not launch a tool", (t) => {
  const { f, store, cli } = setup(t);
  const control = f.at("cancel.json");
  for (const [record, expected] of [[{ format: 9 }, 2], [{ format: 1, id: "host", token: "b".repeat(64), cancel: true }, 130]]) {
    f.json(control, record);
    const result = spawnSync(process.execPath, [bin, "--project", store.root, "journal", "view-json", store.journal], { cwd: f.root, env: { ...f.env, SYMPHYSIS_CANCEL_FILE: control }, encoding: "utf8", timeout: 15000 });
    assert.equal(result.status, expected, result.stderr); assert.equal(result.stdout, "");
    assert.deepEqual(fs.readdirSync(path.join(f.userDir, ".leases")), []);
  }
});

test("the actual installed global Python entrypoint accepts the dispatcher lease", (t) => {
  const f = createRuntimeFixture(path.join(os.tmpdir(), "symphysis-dispatcher-installed"));
  t.after(() => f.cleanup()); f.env.SYMPHYSIS_OPENSPEC = fork;
  const store = f.store("store-a");
  const payload = f.payload("global", { payloadDir: fileURLToPath(new URL("../payload/", import.meta.url)) });
  const canonical = path.join(payload.schemaRoot);
  const projection = f.at("user-data", "openspec", "schemas", "symphysis");
  fs.cpSync(canonical, projection, { recursive: true });
  const response = spawnSync(process.execPath, [bin, "--project", store.root, "journal", "view-json", store.journal], { cwd: f.root, env: f.env, encoding: "utf8", timeout: 20000 });
  assert.equal(response.status, 0, response.stderr);
  const data = JSON.parse(response.stdout);
  assert.ok(Number.isInteger(data.contract) && data.contract > 0);
  assert.equal(data.title, "Fixture store-a");
  assert.deepEqual(fs.readdirSync(path.join(f.userDir, ".leases")), []);
  assert.equal(fs.existsSync(path.join(store.root, ".symphysis", "tools", "journal.py")), false);
});

test("read-only store discovery works before choosing or installing a runtime", (t) => {
  const f = createRuntimeFixture(path.join(os.tmpdir(), "symphysis-store-discovery"));
  t.after(() => f.cleanup()); f.env.SYMPHYSIS_OPENSPEC = fork;
  f.store("store-a", { declaration: false }); f.store("store-b", { declaration: false });
  const before = fs.existsSync(f.userDir);
  const response = spawnSync(process.execPath, [bin, "openspec", "store", "list", "--json"], { cwd: f.root, env: f.env, encoding: "utf8", timeout: 15000 });
  assert.equal(response.status, 0, response.stderr);
  assert.deepEqual(JSON.parse(response.stdout).stores.map((entry) => entry.id).sort(), ["store-a", "store-b"]);
  assert.equal(fs.existsSync(path.join(f.root, "openspec")), false);
  assert.equal(fs.existsSync(path.join(f.userDir, "runtime")), false);
  assert.equal(fs.existsSync(f.userDir), before);
});
