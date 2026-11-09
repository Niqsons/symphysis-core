import { test } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { createInstallationPlan, installationHash } from "../lib/installation-plan.js";
import { applyInstallationPlan } from "../lib/installation-transaction.js";
import { installationFixture, installationFiles } from "../test-support/installation-fixture.js";

for (const scope of ["local", "global"]) {
  test(`${scope} preview writes nothing; repeat installation keeps generation and bytes`, (t) => {
    const state = installationFixture(t, scope);
    const before = installationFiles(state.f.root);
    const plan = createInstallationPlan(state.version(1));
    assert.equal(plan.ready, true);
    assert.deepEqual(installationFiles(state.f.root), before);
    const first = applyInstallationPlan(plan);
    const installed = installationFiles(state.f.root);
    assert.equal(first.written.at(-1), path.join(state.root, "install-manifest.json"));
    const repeated = applyInstallationPlan(createInstallationPlan(state.version(1)));
    assert.deepEqual(repeated.written, []);
    assert.equal(repeated.generation, first.generation);
    assert.deepEqual(installationFiles(state.f.root), installed);
  });
}

test("force preserves user edits and unknown foreign files before any installation write", (t) => {
  const state = installationFixture(t);
  applyInstallationPlan(createInstallationPlan(state.version(1)));
  const tool = state.version(1).files[0].path;
  fs.writeFileSync(tool, "user edit\n");
  const before = installationFiles(state.f.root);
  const plan = createInstallationPlan({ ...state.version(2), force: true });
  assert.equal(plan.ready, false);
  assert.ok(plan.conflicts.some((item) => item.code === "owned-file-modified"));
  assert.throws(() => applyInstallationPlan(plan), { code: "installation-conflict" });
  assert.deepEqual(installationFiles(state.f.root), before);
  const foreign = state.file("docs/foreign.md", "new trusted bytes\n");
  state.f.write(foreign.path, "foreign bytes\n");
  const next = createInstallationPlan({ ...state.version(1), files: [...state.version(1).files, foreign], force: true });
  assert.ok(next.conflicts.some((item) => item.code === "foreign-file"));
  assert.equal(fs.readFileSync(foreign.path, "utf8"), "foreign bytes\n");
});

test("exact trusted bytes can be registered without rewriting the existing file", (t) => {
  const state = installationFixture(t);
  const request = state.version(1);
  const file = request.files[0];
  state.f.write(file.path, file.bytes);
  const original = fs.statSync(file.path).ino;
  const result = applyInstallationPlan(createInstallationPlan(request));
  assert.ok(result.unchanged.includes(file.path));
  assert.equal(fs.statSync(file.path).ino, original);
  assert.equal(result.manifest.files.find((entry) => entry.path === file.path).sha256, installationHash(file.bytes));
});

test("personal roots/settings and typed config merges never enter the replaceable registry", (t) => {
  const state = installationFixture(t, "local");
  const config = path.join(state.store.root, "openspec", "config.yaml");
  const beforeHash = installationHash(fs.readFileSync(config));
  const settings = state.f.write(path.join(state.store.root, "symphysis.yaml"), "# user settings\n");
  const request = { ...state.version(1), nonOwned: [
    { kind: "planning-config", path: config, beforeHash, bytes: Buffer.from("# kept user comment\nschema: symphysis\n") },
    { kind: "initial-settings", path: settings, beforeHash: installationHash(fs.readFileSync(settings)), bytes: Buffer.from("# default settings\n") },
  ] };
  const result = applyInstallationPlan(createInstallationPlan(request));
  assert.equal(fs.readFileSync(settings, "utf8"), "# user settings\n");
  assert.ok(!result.manifest.files.some((file) => [settings, config].includes(file.path)));
  assert.equal(fs.readFileSync(config, "utf8"), "# kept user comment\nschema: symphysis\n");
  assert.throws(() => createInstallationPlan({ ...state.version(1), files: [state.file("tools/journal-roots.json", "{}\n")] }), /Личные/);
});

test("planner rejects target/source escapes, duplicate targets, personal aliases and JSON plan lookalikes", (t) => {
  const state = installationFixture(t);
  for (const file of [
    { ...state.file("tools/demo.py", "x"), path: state.f.at("foreign.py") },
    { ...state.file("tools/demo.py", "x"), source: "tools/../../foreign.py" },
    { ...state.file("tools/demo.py", "x"), path: "relative.py" },
    { ...state.file("tools/demo.py", "x"), source: "openspec/config.yaml" },
  ]) assert.throws(() => createInstallationPlan({ ...state.version(1), files: [file] }), { code: "installation-plan-invalid" });
  assert.throws(() => createInstallationPlan({ ...state.version(1), files: [state.version(1).files[0], state.version(1).files[0]] }), /Две/);
  const plan = createInstallationPlan(state.version(1));
  assert.throws(() => applyInstallationPlan(JSON.parse(JSON.stringify(plan))), /JSON/);
});

test("preview races invalidate a plan even when replacement file has the same bytes", (t) => {
  const state = installationFixture(t);
  applyInstallationPlan(createInstallationPlan(state.version(1)));
  const tool = state.version(1).files[0].path;
  const plan = createInstallationPlan(state.version(2));
  const original = fs.readFileSync(tool);
  const replacement = path.join(path.dirname(tool), "replacement.py");
  fs.writeFileSync(replacement, original);
  fs.unlinkSync(tool);
  fs.renameSync(replacement, tool);
  assert.throws(() => applyInstallationPlan(plan), { code: "installation-state-changed" });
  assert.equal(fs.existsSync(path.join(state.root, ".install-lock")), false);
});

test("omitted own targets require explicit removal and modified files are not deleted", (t) => {
  const state = installationFixture(t);
  applyInstallationPlan(createInstallationPlan(state.version(1)));
  const request = state.version(2);
  const removed = request.files.shift();
  assert.equal(createInstallationPlan(request).ready, false);
  const clean = createInstallationPlan({ ...request, removeFiles: [removed.path] });
  assert.equal(clean.ready, true);
  applyInstallationPlan(clean);
  assert.equal(fs.existsSync(removed.path), false);
});

test("multiple explicit native roots are independently owned and no directory-name inference is used", (t) => {
  const state = installationFixture(t, "local");
  const first = state.f.at("native-one");
  const second = state.f.at("native-two");
  const request = state.version(1);
  request.clients = [{ id: "claude", skillsRoots: [first, second] }];
  request.files = request.files.filter((file) => !file.source.startsWith("skills/"));
  for (const root of [first, second]) request.files.push({ source: "skills/symphysis-brainstorm/SKILL.md", purpose: "skill", path: path.join(root, "symphysis-brainstorm", "SKILL.md"), clientId: "claude", bytes: Buffer.from("# skill\n") });
  const installed = applyInstallationPlan(createInstallationPlan(request));
  assert.equal(installed.manifest.clients[0].skillsRoots.length, 2);
  assert.equal(installed.manifest.files.filter((file) => file.source.startsWith("skills/")).length, 2);
});

test("a native target alias cannot turn a project's journal into replaceable payload", (t) => {
  const state = installationFixture(t, "local");
  const request = state.version(1);
  const skillsRoot = path.join(state.store.root, "openspec", "changes");
  request.clients = [{ id: "claude", skillsRoot }];
  request.files = [{ source: "skills/same-change/decisions.json", purpose: "skill", clientId: "claude",
    path: state.store.journal, bytes: fs.readFileSync(state.store.journal) }];
  assert.throws(() => createInstallationPlan(request), /Проектные данные/);
});

test("a content edit after preview invalidates confirmation before acquiring a writer", (t) => {
  const state = installationFixture(t);
  applyInstallationPlan(createInstallationPlan(state.version(1)));
  const plan = createInstallationPlan(state.version(2));
  const tool = state.version(1).files[0].path;
  fs.writeFileSync(tool, "user edited after preview\n");
  const before = installationFiles(state.f.root);
  assert.throws(() => applyInstallationPlan(plan), { code: "installation-state-changed" });
  assert.deepEqual(installationFiles(state.f.root), before);
});

test("preview refuses a parent junction and leaves the redirected destination unchanged", (t) => {
  const state = installationFixture(t);
  const tools = path.join(state.runtimeRoot, "tools");
  const foreign = state.f.at("foreign-tools");
  state.f.write(path.join(foreign, "demo.py"), "foreign data\n");
  fs.mkdirSync(state.runtimeRoot, { recursive: true });
  fs.symlinkSync(foreign, tools, process.platform === "win32" ? "junction" : "dir");
  try {
    assert.throws(() => createInstallationPlan(state.version(1)), /reparse|ссылк/);
    assert.equal(fs.readFileSync(path.join(foreign, "demo.py"), "utf8"), "foreign data\n");
  } finally { fs.unlinkSync(tools); }
});
