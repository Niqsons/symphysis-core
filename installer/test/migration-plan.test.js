import { test, after } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { createRuntimeFixture } from "../test-support/runtime-fixture.js";
import { installManaged } from "../lib/managed-install.js";
import { initProject } from "../lib/project-init.js";
import { previewMigration, prepareMigrationPlan } from "../lib/migration-plan.js";
import { spawnTool } from "../lib/openspec-bin.js";
import { runManagementCommand } from "../lib/management-cli.js";

const repository = fileURLToPath(new URL("../../", import.meta.url));
const base = process.platform === "win32" ? "X:/codex-tmp" : "/tmp/codex-tmp";
const commit = "a19a4272fcce49c3cbee1aec6feeb4193748947c";
const fixtures = [];
after(() => { for (const fixture of fixtures) fixture.cleanup(); });
function fixture() { const f = createRuntimeFixture(base); f.env.SYMPHYSIS_OPENSPEC = path.join(repository, "upstream", "openspec", "bin", "openspec.js"); fixtures.push(f); return f; }
const options = (f) => ({ env: f.env, sourceRoot: f.at("not-a-clone") });
function tree(root) {
  return Object.fromEntries(fs.readdirSync(root, { withFileTypes: true }).flatMap((entry) => entry.isDirectory() ? Object.entries(tree(path.join(root, entry.name))).map(([name, value]) => [`${entry.name}/${name}`, value]) : [[entry.name, fs.readFileSync(path.join(root, entry.name)).toString("base64")]]));
}
function local(f) { const store = f.store("local", { declaration: false }); installManaged(store.root, options(f)); return store; }
function global(f) { const store = f.store("global"); installManaged(undefined, { ...options(f), scope: "global" }); initProject({ project: store.root, env: f.env }); return store; }

test("managed local→global preview is read-only and binds both generations and schema removal", () => {
  const f = fixture(); const source = local(f); installManaged(undefined, { ...options(f), scope: "global" });
  const beforeStore = tree(source.root); const beforeUser = tree(f.userDir);
  const preview = previewMigration({ ...options(f), project: source.root, to: "global" });
  assert.equal(preview.ready, true, JSON.stringify(preview.conflicts));
  assert.equal(preview.from, "local"); assert.equal(preview.to, "global");
  assert.ok(preview.sourceGeneration); assert.ok(preview.targetGeneration);
  assert.ok(preview.files.some((file) => file.kind === "source-manifest" && file.action === "remove"));
  assert.ok(preview.files.some((file) => file.source === "openspec/schemas/symphysis/schema.yaml" && file.action === "remove"));
  assert.deepEqual(tree(source.root), beforeStore); assert.deepEqual(tree(f.userDir), beforeUser);
  assert.throws(() => prepareMigrationPlan(preview, options(f)), /--confirm/);
  assert.ok(prepareMigrationPlan(JSON.parse(JSON.stringify(preview)), { ...options(f), confirm: true }).operations.length);
});

test("global→local preview keeps user runtime and assigns the new local generation after confirmation", () => {
  const f = fixture(); const source = global(f); const other = f.store("other"); initProject({ project: other.root, env: f.env });
  const beforeSource = tree(source.root); const beforeOther = tree(other.root); const beforeUser = tree(f.userDir);
  const preview = previewMigration({ ...options(f), project: source.root, to: "local" });
  assert.equal(preview.ready, true, JSON.stringify(preview.conflicts));
  assert.ok(preview.warnings.some((warning) => warning.code === "native-discovery-mixed"));
  const prepared = prepareMigrationPlan(JSON.parse(JSON.stringify(preview)), { ...options(f), confirm: true });
  assert.ok(prepared.preparedLocalPlan); assert.equal(prepared.preparedLocal.manifest.scope, "local");
  assert.deepEqual(tree(source.root), beforeSource); assert.deepEqual(tree(other.root), beforeOther); assert.deepEqual(tree(f.userDir), beforeUser);
});

test("changed file identity, user bytes, or global generation invalidates the preview", () => {
  for (const change of ["bytes", "identity", "global"]) {
    const f = fixture(); const source = local(f); installManaged(undefined, { ...options(f), scope: "global" });
    const preview = previewMigration({ ...options(f), project: source.root, to: "global" }); assert.equal(preview.ready, true);
    const file = path.join(source.root, ".symphysis", "docs", "terms.md");
    if (change === "bytes") fs.appendFileSync(file, "\nuser change\n");
    if (change === "identity") { const replacement = f.at("same-byte-replacement"); fs.writeFileSync(replacement, fs.readFileSync(file)); fs.unlinkSync(file); fs.renameSync(replacement, file); }
    if (change === "global") installManaged(undefined, { ...options(f), scope: "global", clients: ["codex"] });
    const before = tree(source.root);
    assert.throws(() => prepareMigrationPlan(preview, { ...options(f), confirm: true }), /изменилось после preview/);
    assert.deepEqual(tree(source.root), before);
  }
});

test("incompatible source declarations and a remaining flat runtime are explicit preview conflicts", () => {
  const f = fixture(); const source = global(f);
  fs.writeFileSync(path.join(source.root, "openspec", "symphysis.json"), '{"format":1,"runtimeApi":2,"schemaApi":1}\n');
  const blocked = previewMigration({ ...options(f), project: source.root, to: "local" });
  assert.equal(blocked.ready, false); assert.ok(blocked.conflicts.some((conflict) => conflict.code === "declaration-incompatible"));
  const otherFixture = fixture(); const selected = local(otherFixture); installManaged(undefined, { ...options(otherFixture), scope: "global" });
  otherFixture.write(path.join(selected.root, "tools", "journal.py"), "# unknown flat copy\n");
  const mixed = previewMigration({ ...options(otherFixture), project: selected.root, to: "global" });
  assert.equal(mixed.ready, false); assert.ok(mixed.conflicts.some((conflict) => conflict.code === "migration-other-local-copy"));
});

test("known manifest-less legacy preview uses shipped whole-generation evidence and preserves private data", () => {
  for (const flat of [false, true]) {
    const f = fixture(); const source = f.store(`legacy-${flat}`, { declaration: false });
    const runtime = flat ? source.root : path.join(source.root, ".symphysis");
    for (const entry of ["cli/journal.py", "cli/journal_cli.py", "decisions/journal_model.py", "decisions/journal_render.py", "roots/roots.py", "openspec-run/openspec_run.py", "trace/trace_graph.py", "anchors/anchor_refs.py", "step-help/step_help.py", "settings/symphysis_config.py", "openspec/schemas/symphysis/schema.yaml"]) {
      const result = spawnTool("git", ["-C", repository, "show", `${commit}:${entry}`], { encoding: null, env: f.env }); assert.equal(result.status, 0);
      f.write(entry.endsWith("schema.yaml") ? path.join(source.root, entry) : path.join(runtime, "tools", path.basename(entry)), Buffer.from(result.stdout));
    }
    const settings = f.write(path.join(source.root, "symphysis.yaml"), Buffer.from([255, 254]));
    const roots = f.write(path.join(runtime, "tools", "journal-roots.json"), Buffer.from([255, 254]));
    installManaged(undefined, { ...options(f), scope: "global" });
    const originalOpen = fs.openSync;
    fs.openSync = function(file, ...args) { if (typeof file === "string" && [settings, roots].includes(file)) throw new Error("Private initial state must stay opaque"); return originalOpen.call(this, file, ...args); };
    let preview;
    try { preview = previewMigration({ ...options(f), project: source.root, to: "global" }); }
    finally { fs.openSync = originalOpen; }
    assert.equal(preview.ready, true, JSON.stringify(preview.conflicts));
    assert.match(preview.sourceGeneration, /^pre-global-/);
    assert.ok(!preview.files.some((file) => [settings, roots].includes(file.path)));
    if (flat) assert.equal(fs.existsSync(path.join(source.root, ".symphysis", "tools", "journal-roots.json")), false);
    assert.deepEqual(fs.readFileSync(settings), Buffer.from([255, 254])); assert.deepEqual(fs.readFileSync(roots), Buffer.from([255, 254]));
    if (flat) {
      const canonical = f.write(path.join(source.root, ".symphysis", "tools", "journal-roots.json"), Buffer.from([254, 255]));
      const before = tree(source.root);
      fs.openSync = function(file, ...args) { if (typeof file === "string" && [settings, roots, canonical].includes(file)) throw new Error("Ambiguous private maps must stay opaque"); return originalOpen.call(this, file, ...args); };
      let blocked;
      try { blocked = previewMigration({ ...options(f), project: source.root, to: "global" }); }
      finally { fs.openSync = originalOpen; }
      assert.equal(blocked.ready, false);
      assert.ok(blocked.conflicts.some((conflict) => conflict.code === "migration-roots-layout-ambiguous"));
      assert.deepEqual(tree(source.root), before);
    }
  }
});

test("migration CLI serializes a review, freezes selectors and applies both actual-payload directions", async () => {
  for (const to of ["global", "local"]) {
    const f = fixture(); const store = to === "global" ? local(f) : global(f);
    if (to === "global") installManaged(undefined, { ...options(f), scope: "global" });
    const beforeWord = fs.readFileSync(path.join(store.root, "openspec", "changes", "same-change", "intent.md"));
    const output = []; const io = { cwd: f.root, env: f.env, stdout: { write: (value) => output.push(value) }, stderr: { write: (value) => output.push(value) } };
    const review = f.at(`migration-${to}.json`);
    assert.equal(await runManagementCommand(["migrate", "--project", store.root, "--to", to, "--out", review], io), 0, output.join(""));
    assert.equal(await runManagementCommand(["migrate", "--apply-plan", review, "--confirm", "--project", store.root], io), 2);
    assert.equal(await runManagementCommand(["migrate", "--apply-plan", review], io), 2);
    assert.equal(await runManagementCommand(["migrate", "--apply-plan", review, "--confirm"], io), 0, output.join(""));
    assert.equal(fs.existsSync(path.join(store.root, ".symphysis", "install-manifest.json")), to === "local");
    assert.deepEqual(fs.readFileSync(path.join(store.root, "openspec", "changes", "same-change", "intent.md")), beforeWord);
    assert.equal(await runManagementCommand(["migrate", "--recover", "--project", store.root], io), 0, output.join(""));
  }
});
