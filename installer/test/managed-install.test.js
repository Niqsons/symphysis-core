import { test, after } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { createRuntimeFixture } from "../test-support/runtime-fixture.js";
import { installManaged, planManagedInstall, DEFAULT_PAYLOAD } from "../lib/managed-install.js";
import { initProject } from "../lib/project-init.js";
import { mergeConfig } from "../lib/planning-config.js";
import { resolveRuntime } from "../lib/runtime-resolver.js";
import { check } from "../lib/check.js";
import { runManagementCommand } from "../lib/management-cli.js";
import { spawnSync } from "node:child_process";

const repository = fileURLToPath(new URL("../../", import.meta.url));
const fork = path.join(repository, "upstream", "openspec", "bin", "openspec.js");
const base = process.platform === "win32" ? "X:/codex-tmp" : "/tmp/codex-tmp";
const fixtures = [];
after(() => { for (const fixture of fixtures) fixture.cleanup(); });
const fixture = () => { const result = createRuntimeFixture(base); result.env.SYMPHYSIS_OPENSPEC = fork; fixtures.push(result); return result; };
const options = (f, extra = {}) => ({ env: f.env, sourceRoot: f.at("no-source"), ...extra });
const bytes = (file) => fs.readFileSync(file);
function withYaml(f) {
  const probe = spawnSync("python", ["-c", "import pathlib,yaml; print(pathlib.Path(yaml.__file__).parent)"], { encoding: "utf8" });
  assert.equal(probe.status, 0, "Этот тест требует доступный в окружении разработчика PyYAML");
  const dependencies = f.at("dependencies");
  fs.cpSync(probe.stdout.trim(), path.join(dependencies, "yaml"), { recursive: true, filter: (file) => !file.includes("__pycache__") && !file.endsWith(".pyc") });
  f.env.PYTHONPATH = dependencies;
}
function tree(root) {
  if (!fs.existsSync(root)) return {};
  return Object.fromEntries(fs.readdirSync(root, { withFileTypes: true }).flatMap((entry) => entry.isDirectory() ? Object.entries(tree(path.join(root, entry.name))).map(([name, value]) => [`${entry.name}/${name}`, value]) : [[entry.name, fs.readFileSync(path.join(root, entry.name)).toString("base64")]]));
}

test("actual payload global install needs no store and never initializes cwd; repeated install preserves Codex targets", () => {
  const f = fixture();
  const source = f.at("source-without-openspec"); fs.mkdirSync(source);
  const before = tree(source);
  const installed = installManaged(undefined, options(f, { scope: "global", clients: ["codex"] }));
  assert.equal(installed.manifest.scope, "global");
  assert.equal(installed.manifest.storeRoot, null);
  assert.deepEqual(installed.manifest.clients.map((client) => client.id), ["codex"]);
  assert.deepEqual(tree(source), before);
  assert.ok(fs.existsSync(path.join(f.clientRoots.codex.agents, "symphysis-research-driver.toml")));
  const repeated = installManaged(undefined, options(f, { scope: "global" }));
  assert.deepEqual(repeated.written, []);
  assert.deepEqual(repeated.manifest.clients.map((client) => client.id), ["codex"]);
  assert.equal(fs.existsSync(path.join(f.clientRoots.claude.skills, "symphysis-brainstorm", "SKILL.md")), false);
});

test("global CLI install from an uninitialized cwd does not require a selected store", () => {
  const f = fixture(); const cwd = f.at("uninitialized"); fs.mkdirSync(cwd);
  const bin = path.join(repository, "installer", "bin", "symphysis.js");
  const result = spawnSync(process.execPath, [bin, "install", "--scope", "global", "--client", "opencode"], { cwd, env: f.env, encoding: "utf8" });
  assert.equal(result.status, 0, result.stderr);
  assert.deepEqual(tree(cwd), {});
  assert.ok(fs.existsSync(path.join(f.userDir, "install-manifest.json")));
});

test("global init follows actual fork pointer planning root and preserves opaque store state on repeat", () => {
  const f = fixture();
  const store = f.store("cloned", { declaration: false });
  const other = f.store("other");
  const source = f.pointer("code", "cloned");
  installManaged(undefined, options(f, { scope: "global", clients: ["claude", "codex", "opencode"] }));
  const sourceBefore = tree(source);
  const otherBefore = tree(other.root);
  const userManifest = bytes(path.join(f.userDir, "install-manifest.json"));
  const result = initProject({ project: source, env: f.env });
  assert.equal(result.storeRoot, store.root);
  assert.equal(fs.existsSync(path.join(store.root, ".symphysis", "install-manifest.json")), false);
  assert.equal(fs.existsSync(path.join(store.root, ".symphysis", "tools", "journal.py")), false);
  assert.ok(fs.existsSync(path.join(store.root, ".symphysis", "store-init.json")));
  assert.deepEqual(tree(source), sourceBefore);
  assert.deepEqual(tree(other.root), otherBefore);
  assert.deepEqual(bytes(path.join(f.userDir, "install-manifest.json")), userManifest);
  const opaque = ["symphysis.yaml", ".symphysis/tools/journal-roots.json", ".symphysis/viewer/draft.txt", "answers/sample.json"];
  for (const relative of opaque) { const target = path.join(store.root, relative); fs.mkdirSync(path.dirname(target), { recursive: true }); fs.writeFileSync(target, `opaque custom ${relative}\r\n`); }
  const beforeRepeat = tree(store.root);
  initProject({ project: source, env: f.env });
  assert.deepEqual(tree(store.root), beforeRepeat);
  assert.equal(resolveRuntime({ project: source, env: f.env }).status, "ready");
});

test("a cloned nearest store initializes without a user registry or local runtime copy", () => {
  const f = fixture(); const store = f.store("unregistered-clone", { declaration: false });
  fs.unlinkSync(f.at("user-data", "openspec", "stores", "registry.yaml"));
  installManaged(undefined, options(f, { scope: "global" }));
  const result = initProject({ project: store.root, env: f.env });
  assert.equal(result.storeRoot, store.root);
  assert.equal(resolveRuntime({ project: store.root, env: f.env }).status, "ready");
  assert.equal(fs.existsSync(path.join(store.root, ".symphysis", "tools", "journal.py")), false);
  assert.equal(fs.existsSync(f.at("user-data", "openspec", "stores", "registry.yaml")), false);
});

test("invalid planning shapes fail before any local/global init write and preserve comments and foreign fields", () => {
  for (const body of ["rules: []\n", "rules:\n  specs: scalar\n", "operations: []\n", "operations:\n  apply: []\n", "operations:\n  apply:\n    guidance: nope\n"]) {
    const f = fixture(); const store = f.store("bad", { declaration: false });
    fs.writeFileSync(path.join(store.root, "openspec", "config.yaml"), body);
    installManaged(undefined, options(f, { scope: "global" }));
    const before = tree(store.root);
    assert.throws(() => initProject({ project: store.root, env: f.env }), /должен|должна/);
    assert.deepEqual(tree(store.root), before);
    assert.throws(() => installManaged(store.root, options(f)), /должен|должна/);
    assert.deepEqual(tree(store.root), before);
  }
  const ours = bytes(path.join(DEFAULT_PAYLOAD, "openspec", "config.symphysis.yaml")).toString();
  const merged = mergeConfig("# keep comment\nschema: spec-driven\nforeign: {answer: 42}\nrules:\n  specs:\n    - mine\n", ours).text;
  assert.match(merged, /# keep comment/); assert.match(merged, /answer: 42/); assert.match(merged, /- mine/);
  assert.equal(mergeConfig(merged, ours).text, merged);
});

test("local remains standalone and global init requires explicit migration even for damaged local", () => {
  const f = fixture(); const store = f.store("local", { declaration: false });
  installManaged(store.root, options(f, { clients: ["codex"] }));
  assert.equal(resolveRuntime({ project: store.root, env: f.env }).scope, "local");
  assert.equal(resolveRuntime({ project: store.root, env: f.env }).status, "ready");
  installManaged(undefined, options(f, { scope: "global" }));
  assert.throws(() => initProject({ project: store.root, env: f.env }), /local/);
  fs.writeFileSync(path.join(store.root, ".symphysis", "tools", "journal.py"), "damaged\n");
  assert.throws(() => initProject({ project: store.root, env: f.env }), /local/);
});

test("local install refuses a native pointer root and broken pointer before any write", () => {
  const f = fixture(); const store = f.store("local-store");
  const source = f.pointer("local-code", "local-store");
  const sourceBefore = tree(source); const storeBefore = tree(store.root);
  assert.throws(() => installManaged(source, options(f)), (error) => error.exitCode === 2 && error.message.includes(store.root));
  assert.deepEqual(tree(source), sourceBefore); assert.deepEqual(tree(store.root), storeBefore);
  fs.writeFileSync(path.join(source, "openspec", "config.yaml"), "store: unknown-store\n");
  const brokenBefore = tree(source);
  assert.throws(() => installManaged(source, options(f)), (error) => error.exitCode === 2);
  assert.deepEqual(tree(source), brokenBefore); assert.deepEqual(tree(store.root), storeBefore);
});

test("filesystem-copy local manifest cannot claim another root's resources", () => {
  const f = fixture(); const first = f.store("first-copy"); const second = f.at("copied-local");
  installManaged(first.root, options(f));
  fs.cpSync(first.root, second, { recursive: true });
  const before = tree(second); const firstBefore = tree(first.root);
  assert.throws(() => installManaged(second, options(f)), /постороннюю цель/);
  assert.deepEqual(tree(second), before); assert.deepEqual(tree(first.root), firstBefore);
});

test("local install requires migration only for an existing declared global store", () => {
  const f = fixture(); const declared = f.store("declared-global"); const ordinary = f.store("ordinary-local", { declaration: false });
  installManaged(undefined, options(f, { scope: "global" }));
  initProject({ project: declared.root, env: f.env });
  const before = tree(declared.root);
  assert.throws(() => installManaged(declared.root, options(f)), (error) => error.code === "migration-required");
  assert.deepEqual(tree(declared.root), before);
  installManaged(ordinary.root, options(f));
  assert.equal(resolveRuntime({ project: ordinary.root, env: f.env }).scope, "local");
  const otherFixture = fixture(); const standalone = otherFixture.store("standalone", { declaration: true });
  installManaged(standalone.root, options(otherFixture));
  assert.equal(resolveRuntime({ project: standalone.root, env: otherFixture.env }).scope, "local");
});

test("force preserves foreign and user-modified resources without partial installation", () => {
  const f = fixture(); const store = f.store("local");
  const foreign = path.join(store.root, ".claude", "skills", "symphysis-brainstorm", "SKILL.md");
  fs.mkdirSync(path.dirname(foreign), { recursive: true }); fs.writeFileSync(foreign, "foreign\n");
  const initial = tree(store.root);
  assert.throws(() => installManaged(store.root, options(f, { force: true })), /ownership/);
  assert.deepEqual(tree(store.root), initial);
  fs.unlinkSync(foreign);
  installManaged(store.root, options(f));
  fs.writeFileSync(foreign, "user modified\n");
  const modified = tree(store.root);
  assert.throws(() => installManaged(store.root, options(f, { force: true })), /ownership/);
  assert.deepEqual(tree(store.root), modified);
});

test("an unknown schema file is reported before publishing a runtime that native preflight would reject", () => {
  const f = fixture();
  const schema = f.at("user-data", "openspec", "schemas", "symphysis");
  fs.mkdirSync(schema, { recursive: true });
  const foreign = path.join(schema, "foreign-template.md"); fs.writeFileSync(foreign, "foreign\n");
  assert.throws(() => installManaged(undefined, options(f, { scope: "global", force: true })), /неизвестный файл схемы сохранён/);
  assert.equal(fs.readFileSync(foreign, "utf8"), "foreign\n");
  assert.equal(fs.existsSync(path.join(f.userDir, "install-manifest.json")), false);
  assert.equal(fs.existsSync(path.join(f.userDir, "runtime")), false);
});

test("global update keeps both stores byte-exact while adding a client and updating old targets", () => {
  const f = fixture(); const first = f.store("first"); const second = f.store("second");
  installManaged(undefined, options(f, { scope: "global", clients: ["codex"] }));
  initProject({ project: first.root, env: f.env }); initProject({ project: second.root, env: f.env });
  const oldFirst = tree(first.root); const oldSecond = tree(second.root);
  const updated = installManaged(undefined, options(f, { scope: "global", clients: ["opencode"] }));
  assert.deepEqual(updated.manifest.clients.map((client) => client.id), ["codex", "opencode"]);
  assert.deepEqual(tree(first.root), oldFirst); assert.deepEqual(tree(second.root), oldSecond);
  assert.equal(resolveRuntime({ project: first.root, env: f.env }).status, "ready");
  assert.equal(resolveRuntime({ project: second.root, env: f.env }).status, "ready");
});

test("management CLI public flags reject ambiguous/relative global destinations and expose actual help", async () => {
  const f = fixture(); const output = []; const io = { cwd: f.root, env: f.env, stdout: { write: (text) => output.push(text) }, stderr: { write: (text) => output.push(text) } };
  for (const args of [["install", "--scope", "global", "--project", f.root], ["install", "--scope", "global", "--store", "x"], ["install", "--scope", "bad"], ["install", "--scope", "global", "--skills-dir", "relative"], ["install", "--client", "claude", "--client", "codex", "--agents-dir", "relative"], ["install", "--project", f.root, "--project", f.root], ["check", "--force"]]) assert.equal(await runManagementCommand(args, io), 2, args.join(" "));
  assert.equal(await runManagementCommand(["--help"], io), 0);
  for (const flag of ["--scope", "--client", "--project", "--store", "--skills-dir", "--agents-dir", "--recover", "--force"]) assert.ok(output.join("").includes(flag));
  assert.equal(fs.existsSync(path.join(f.root, "openspec")), false);
});

test("all client filesystem readiness is reported separately from native session verification", () => {
  const f = fixture(); const store = f.store("checked");
  installManaged(undefined, options(f, { scope: "global", clients: ["claude", "codex", "opencode"] }));
  initProject({ project: store.root, env: f.env });
  fs.unlinkSync(path.join(f.clientRoots.codex.agents, "symphysis-research-driver.toml"));
  const result = check(store.root, options(f, { scope: "global" }));
  assert.equal(result.ok, false);
  assert.equal(result.clients.find((client) => client.id === "codex").filesystem, "incomplete");
  assert.equal(result.clients.find((client) => client.id === "claude").filesystem, "ready");
  assert.ok(result.clients.every((client) => client.discovery === "unconfirmed" && client.sessionVerification === "unconfirmed"));
});

test("healthy global check uses selected runtime and never asks for a local copy", () => {
  const f = fixture(); const store = f.store("healthy");
  withYaml(f);
  fs.unlinkSync(store.journal);
  installManaged(undefined, options(f, { scope: "global", clients: ["claude", "codex", "opencode"] }));
  initProject({ project: store.root, env: f.env });
  const before = tree(store.root);
  const result = check(store.root, options(f, { scope: "global" }));
  assert.equal(result.ok, true, result.findings.join("\n"));
  assert.ok(result.clients.every((client) => client.filesystem === "ready"));
  assert.deepEqual(tree(store.root), before);
  assert.equal(fs.existsSync(path.join(store.root, ".symphysis", "tools", "journal.py")), false);
});

test("check selects the pointer store before considering legacy markers at the source", () => {
  for (const scope of ["local", "global"]) {
    const f = fixture(); withYaml(f); const store = f.store(`target-${scope}`); fs.unlinkSync(store.journal);
    if (scope === "global") { installManaged(undefined, options(f, { scope })); initProject({ project: store.root, env: f.env }); }
    else { installManaged(store.root, options(f)); fs.unlinkSync(path.join(store.root, ".symphysis", "install-manifest.json")); }
    const source = f.pointer(`source-${scope}`, store.id);
    const marker = path.join(source, ".symphysis", "tools", "journal.py"); fs.mkdirSync(path.dirname(marker), { recursive: true }); fs.writeFileSync(marker, 'raise SystemExit("source-must-not-run")\n');
    const checked = check(source, options(f));
    assert.equal(checked.ok, true, checked.findings.join("\n"));
    assert.equal(checked.context.store.root, store.root); assert.equal(checked.context.scope, scope);
    assert.ok(!checked.findings.some((finding) => finding.includes("source-must-not-run")));
    fs.writeFileSync(path.join(source, "openspec", "config.yaml"), "store: missing-store\n");
    const blocked = check(source, options(f));
    assert.equal(blocked.ok, false); assert.equal(blocked.context.runtime, null);
    assert.ok(blocked.findings.some((finding) => finding.includes("missing-store")), blocked.findings.join("\n"));
    assert.ok(!blocked.findings.some((finding) => finding.includes("source-must-not-run")));
  }
});

test("missing PyYAML remains a visible settings dependency diagnostic", () => {
  const f = fixture(); const store = f.store("missing-yaml");
  fs.unlinkSync(store.journal);
  const dependencies = f.at("no-yaml"); fs.mkdirSync(dependencies);
  fs.writeFileSync(path.join(dependencies, "sitecustomize.py"), "import importlib.abc, sys\nclass NoYaml(importlib.abc.MetaPathFinder):\n    def find_spec(self, fullname, path=None, target=None):\n        if fullname == 'yaml' or fullname.startswith('yaml.'):\n            raise ImportError('fixture missing PyYAML')\nsys.meta_path.insert(0, NoYaml())\n");
  f.env.PYTHONPATH = dependencies;
  installManaged(undefined, options(f, { scope: "global" }));
  initProject({ project: store.root, env: f.env });
  const result = check(store.root, options(f, { scope: "global" }));
  assert.equal(result.ok, false);
  assert.ok(result.findings.some((finding) => finding.includes("PyYAML")), result.findings.join("\n"));
});
