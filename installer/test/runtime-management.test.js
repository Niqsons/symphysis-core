import { test } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { spawnSync } from "node:child_process";
import { createRuntimeFixture } from "../test-support/runtime-fixture.js";
import { installationFiles } from "../test-support/installation-fixture.js";
import { installManaged } from "../lib/managed-install.js";
import { managedNativeArguments } from "../lib/runtime-dispatcher.js";
import { globalConfigPath } from "../lib/global-config.js";

const root = fileURLToPath(new URL("../../", import.meta.url));
const bin = path.join(root, "installer", "bin", "symphysis.js");
function setup(t, scope, { declaration = true } = {}) {
  const f = createRuntimeFixture(path.join(os.tmpdir(), "symphysis-native-management-tests"));
  t.after(() => f.cleanup());
  f.env.SYMPHYSIS_OPENSPEC = path.join(root, "upstream", "openspec", "bin", "openspec.js");
  const store = f.store("store-a", { declaration });
  const other = f.store("store-b");
  const source = f.pointer("source", store.id);
  installManaged(scope === "global" ? undefined : store.root, { scope, clients: ["codex"], env: f.env });
  const cli = (...args) => spawnSync(process.execPath, [bin, "--project", source, "openspec", ...args], { cwd: f.root, env: f.env, encoding: "utf8", timeout: 30000 });
  const manifestFile = scope === "global" ? path.join(f.userDir, "install-manifest.json") : path.join(store.root, ".symphysis", "install-manifest.json");
  return { f, store, other, source, cli, manifestFile, manifest: () => JSON.parse(fs.readFileSync(manifestFile, "utf8")) };
}

test("native management parser validates every argument before any filesystem action", () => {
  assert.deepEqual(managedNativeArguments(["init", "--tools=codex,opencode,codex", "--profile", "custom", "--force", "--no-animation"]).clients, ["codex", "opencode"]);
  assert.deepEqual(managedNativeArguments(["init", "--tools", "all"]).clients, ["claude", "codex", "opencode"]);
  assert.equal(managedNativeArguments(["update", "--dry-run", "--json"]).dryRun, true);
  for (const args of [
    ["init", "--tools", "unsupported"], ["init", "--tools", "none"], ["init", "--tools", "claude,"], ["init", "--tools"], ["init", "--tools", "claude", "--tools=codex"],
    ["init", "--profile", "invented"], ["init", "--language", "Russian"], ["init", "--force=true"], ["init", "one", "two"], ["init", "bad\0name"],
    ["update", "--profile", "core"], ["update", "--tools", "codex"], ["update", "--json"], ["update", "--dry-run", "--dry-run"],
    ["init", "--store", "other"], ["init", "--project=other"], ["update", "--store-path", "other"], ["update", "--schema", "other"],
  ]) assert.throws(() => managedNativeArguments(args), (error) => error.exitCode === 2, JSON.stringify(args));
});

for (const scope of ["local", "global"]) test(`${scope} native update uses the planner, preserves target clients and dry-run writes nothing`, (t) => {
  const state = setup(t, scope);
  const before = installationFiles(state.f.root);
  const preview = state.cli("update", "--dry-run", "--json");
  assert.equal(preview.status, 0, preview.stderr);
  const plan = JSON.parse(preview.stdout);
  assert.equal(plan.operation, "openspec-update"); assert.equal(plan.scope, scope); assert.equal(plan.storeRoot, state.store.root);
  assert.deepEqual(installationFiles(state.f.root), before);
  const applied = state.cli("update", "--force");
  assert.equal(applied.status, 0, applied.stderr);
  assert.deepEqual(state.manifest().clients.map((client) => client.id), ["codex"]);
  for (const entry of state.manifest().files.filter((entry) => entry.purpose === "workflow")) assert.match(fs.readFileSync(entry.path, "utf8"), /\*\*Symphysis preflight/);
  assert.equal(fs.existsSync(path.join(state.source, ".symphysis")), false);
});

test("global native init prevalidates an undeclared selected store and installs the native operation-scoped custom profile", (t) => {
  const state = setup(t, "global", { declaration: false });
  state.f.json(globalConfigPath(state.f.env), { profile: "core", workflows: ["verify", "onboard", "bulk-archive"], enableTelemetry: false });
  const configBefore = fs.readFileSync(globalConfigPath(state.f.env));
  const sourceBefore = installationFiles(state.source), otherBefore = installationFiles(state.other.root);
  const result = state.cli("init", "--tools", "opencode", "--profile", "custom", "--no-animation");
  assert.equal(result.status, 0, result.stderr);
  assert.deepEqual(state.manifest().clients.map((client) => client.id), ["codex", "opencode"]);
  const ids = new Set(state.manifest().files.filter((entry) => entry.purpose === "workflow").map((entry) => path.basename(entry.path)));
  assert.ok(ids.has("opsx-verify.md") && ids.has("opsx-onboard.md") && ids.has("opsx-bulk-archive.md"));
  assert.ok(fs.existsSync(path.join(state.store.root, "openspec", "symphysis.json")));
  assert.ok(fs.existsSync(path.join(state.store.root, ".symphysis", "store-init.json")));
  assert.equal(fs.existsSync(path.join(state.store.root, ".symphysis", "install-manifest.json")), false);
  assert.deepEqual(fs.readFileSync(globalConfigPath(state.f.env)), configBefore);
  assert.deepEqual(installationFiles(state.source), sourceBefore);
  assert.deepEqual(installationFiles(state.other.root), otherBefore);
});

test("local native init remains local and keeps prior independent targets", (t) => {
  const state = setup(t, "local");
  const response = state.cli("init");
  assert.equal(response.status, 0, response.stderr);
  assert.equal(state.manifest().scope, "local");
  assert.deepEqual(state.manifest().clients.map((client) => client.id), ["codex"]);
  assert.equal(fs.existsSync(path.join(state.f.userDir, "install-manifest.json")), false);
});

test("native management refuses late selectors, another target and unsafe force without writing", (t) => {
  const state = setup(t, "global");
  for (const args of [["init", "--store", state.other.id], ["update", state.other.root], ["init", "."], ["experimental"], ["init", "--tools", "none"], ["init", "--profile", "unknown"]]) {
    const before = installationFiles(state.f.root);
    const result = state.cli(...args);
    assert.equal(result.status, 2, `${JSON.stringify(args)}\n${result.stderr}`);
    assert.deepEqual(installationFiles(state.f.root), before);
  }
  const entry = state.manifest().files.find((item) => item.purpose === "workflow");
  fs.appendFileSync(entry.path, "\nUser content\n");
  const before = installationFiles(state.f.root);
  const result = state.cli("update", "--force");
  assert.equal(result.status, 2); assert.match(result.stderr, /resource-missing/);
  assert.deepEqual(installationFiles(state.f.root), before);
});

test("native update cannot initialize a global store as a side effect", (t) => {
  const state = setup(t, "global", { declaration: false });
  const before = installationFiles(state.f.root);
  const response = state.cli("update");
  assert.equal(response.status, 2); assert.match(response.stderr, /declaration-missing/);
  assert.deepEqual(installationFiles(state.f.root), before);
});
