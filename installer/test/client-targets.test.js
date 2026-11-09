import { test } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { createRuntimeFixture } from "../test-support/runtime-fixture.js";
import { clientTargets, ClientTargetError } from "../lib/client-targets.js";

function fixture(t) {
  const f = createRuntimeFixture(path.join(os.tmpdir(), "symphysis-client-target-tests"));
  const project = f.at("uncreated-project");
  const home = f.at("profile");
  t.after(() => f.cleanup());
  return { f, project, home };
}
const usage = (error) => error instanceof ClientTargetError && error.exitCode === 2;

test("local descriptors name each native client and keep targets independent", (t) => {
  const { f, project } = fixture(t);
  const descriptors = clientTargets({ scope: "local", project, clients: ["claude", "codex", "opencode"], env: f.env });
  assert.deepEqual(descriptors.map((item) => item.id), ["claude", "codex", "opencode"]);
  const [claude, codex, opencode] = descriptors;
  assert.equal(claude.skillsRoot, path.join(project, ".claude", "skills"));
  assert.equal(claude.agentsRoot, path.join(project, ".claude", "agents"));
  assert.equal(claude.commandsRoot, path.join(project, ".claude", "commands", "opsx"));
  assert.equal(codex.skillsRoot, path.join(project, ".agents", "skills"));
  assert.equal(codex.agentsRoot, path.join(project, ".codex", "agents"));
  assert.equal(codex.commandsRoot, null);
  assert.equal(codex.agentFormat, "codex-toml");
  assert.equal(codex.workflowCarrier, "skills");
  assert.equal(opencode.skillsRoot, path.join(project, ".opencode", "skills"));
  assert.equal(opencode.agentsRoot, path.join(project, ".opencode", "agents"));
  assert.equal(opencode.commandsRoot, path.join(project, ".opencode", "commands"));
  assert.equal(opencode.agentFormat, "opencode-v2-md");
  assert.equal(claude.agentFormat, "claude-md");
  for (const item of descriptors) {
    assert.deepEqual(item.requiredWorkflows, ["new", "continue", "apply", "sync", "archive"]);
    assert.deepEqual(item.skillsRoots, [item.skillsRoot]);
    assert.deepEqual(item.agentsRoots, [item.agentsRoot]);
  }
  assert.equal(fs.existsSync(project), false);
});

test("global defaults use each client's native root rather than the symphysis home", (t) => {
  const { f, home } = fixture(t);
  const [claude, codex, opencode] = clientTargets({ scope: "global", clients: ["claude", "codex", "opencode"], env: { SYMPHYSIS_HOME: f.at("unrelated-runtime"), APPDATA: f.at("unrelated-roaming") }, home });
  assert.equal(claude.skillsRoot, path.join(home, ".claude", "skills"));
  assert.equal(claude.agentsRoot, path.join(home, ".claude", "agents"));
  assert.equal(claude.commandsRoot, path.join(home, ".claude", "commands", "opsx"));
  assert.equal(codex.skillsRoot, path.join(home, ".agents", "skills"));
  assert.equal(codex.agentsRoot, path.join(home, ".codex", "agents"));
  assert.equal(codex.commandsRoot, null);
  assert.equal(opencode.configRoot, path.join(home, ".config", "opencode"));
  assert.equal(opencode.commandsRoot, path.join(home, ".config", "opencode", "commands"));
  assert.equal(fs.existsSync(path.join(home, ".claude")), false);
  assert.equal(fs.existsSync(path.join(home, ".agents")), false);
  assert.equal(fs.existsSync(path.join(home, ".config")), false);
});

test("explicit config-home overrides are selected per client", (t) => {
  const { f, home } = fixture(t);
  const [claude, codex, opencode] = clientTargets({ scope: "global", clients: ["claude", "codex", "opencode"], env: f.env, home });
  assert.equal(claude.configRoot, f.env.CLAUDE_CONFIG_DIR);
  assert.equal(codex.configRoot, f.env.CODEX_HOME);
  assert.equal(codex.skillsRoot, path.join(home, ".agents", "skills"));
  assert.equal(codex.agentsRoot, path.join(f.env.CODEX_HOME, "agents"));
  assert.equal(opencode.configRoot, f.env.OPENCODE_CONFIG_DIR);
  const [xdg] = clientTargets({ scope: "global", clients: ["opencode"], env: { XDG_CONFIG_HOME: f.at("alternate-config") }, home });
  assert.equal(xdg.configRoot, path.join(f.at("alternate-config"), "opencode"));
});

test("client IDs are explicit, default to Claude and deduplicate without directory inference", (t) => {
  const { f, project } = fixture(t);
  const [implicit] = clientTargets({ project, skillsDirs: [".opencode/skills"], env: f.env });
  assert.equal(implicit.id, "claude");
  assert.equal(implicit.skillsRoot, path.join(project, ".opencode", "skills"));
  assert.equal(implicit.agentsRoot, path.join(project, ".opencode", "agents"));
  assert.equal(implicit.legacyTargets, true);
  assert.equal(implicit.commandsRoot, path.join(project, ".claude", "commands", "opsx"));
  assert.deepEqual(clientTargets({ project, clients: ["codex", "claude", "codex"], env: f.env }).map((item) => item.id), ["codex", "claude"]);
  assert.equal(clientTargets({ project, clients: [], env: f.env })[0].id, "claude");
  assert.throws(() => clientTargets({ project, clients: ["unknown"], env: f.env }), usage);
  const [explicit] = clientTargets({ project, clients: ["claude"], skillsDirs: [".opencode/skills"], env: f.env });
  assert.equal(explicit.agentsRoot, path.join(project, ".claude", "agents"));
  assert.equal(explicit.legacyTargets, false);
});

test("repeated skill and agent overrides remain independent arrays for one client", (t) => {
  const { f, project } = fixture(t);
  const [descriptor] = clientTargets({ project, clients: ["codex"], skillsDirs: ["custom-a/skills", "custom-b/skills"], agentsDirs: ["drivers"], env: f.env });
  assert.deepEqual(descriptor.skillsRoots, [path.join(project, "custom-a", "skills"), path.join(project, "custom-b", "skills")]);
  assert.deepEqual(descriptor.agentsRoots, [path.join(project, "drivers")]);
  assert.equal(descriptor.skillsRoot, null);
  assert.equal(descriptor.agentsRoot, path.join(project, "drivers"));
  assert.equal(descriptor.commandsRoot, null);
  const [reversed] = clientTargets({ project, skillsDirs: ["skills"], agentsDirs: ["agents-a", "agents-b"], env: f.env });
  assert.equal(reversed.skillsRoot, path.join(project, "skills"));
  assert.equal(reversed.agentsRoot, null);
  assert.equal(reversed.agentsRoots.length, 2);
  const [deduped] = clientTargets({ project, clients: ["claude", "claude"], skillsDirs: ["skills", "./skills"], env: f.env });
  assert.deepEqual(deduped.skillsRoots, [path.join(project, "skills")]);
  const [legacy] = clientTargets({ project, skillsDirs: ["custom-a/skills", "custom-b/skills"], env: f.env });
  assert.deepEqual(legacy.agentsRoots, [path.join(project, "custom-a", "agents"), path.join(project, "custom-b", "agents")]);
  assert.equal(legacy.agentsRoot, null);
});

test("native agent defaults never follow a moved skills directory", (t) => {
  const { f, project, home } = fixture(t);
  for (const scope of ["local", "global"]) for (const id of ["claude", "codex", "opencode"]) {
    const moved = f.at("moved", id, "skills");
    const [descriptor] = clientTargets({ scope, project, clients: [id], skillsDirs: [moved], env: f.env, home });
    const base = scope === "local" ? path.join(project, id === "claude" ? ".claude" : id === "codex" ? ".codex" : ".opencode") : id === "claude" ? f.env.CLAUDE_CONFIG_DIR : id === "codex" ? f.env.CODEX_HOME : f.env.OPENCODE_CONFIG_DIR;
    assert.equal(descriptor.skillsRoot, moved);
    assert.equal(descriptor.agentsRoot, path.join(base, "agents"));
    assert.notEqual(descriptor.agentsRoot, path.join(path.dirname(moved), "agents"));
  }
});

test("multiple clients reject ambiguous path overrides before target construction", (t) => {
  const { f, project } = fixture(t);
  for (const override of [{ skillsDirs: ["skills"] }, { agentsDirs: ["agents"] }]) assert.throws(() => clientTargets({ project, clients: ["claude", "codex"], ...override, env: f.env }), usage);
});

test("global overrides and selected config homes must be fully absolute", (t) => {
  const { f, home } = fixture(t);
  const relatives = ["relative", ...(process.platform === "win32" ? ["\\relative", "/relative", "X:relative"] : [])];
  for (const value of relatives) {
    for (const key of ["skillsDirs", "agentsDirs"]) assert.throws(() => clientTargets({ scope: "global", [key]: [value], env: {}, home }), usage);
    for (const [id, key] of [["claude", "CLAUDE_CONFIG_DIR"], ["codex", "CODEX_HOME"], ["opencode", "OPENCODE_CONFIG_DIR"], ["opencode", "XDG_CONFIG_HOME"]]) {
      assert.throws(() => clientTargets({ scope: "global", clients: [id], skillsDirs: [f.at("custom-skills")], agentsDirs: [f.at("custom-agents")], env: { [key]: value }, home }), usage);
    }
  }
  assert.throws(() => clientTargets({ scope: "global", env: {}, home: "relative" }), usage);
});

test("unselected client configuration cannot invalidate a selected independent installation", (t) => {
  const { f, home, project } = fixture(t);
  assert.equal(clientTargets({ scope: "global", clients: ["claude"], env: { CODEX_HOME: "relative", OPENCODE_CONFIG_DIR: "relative", XDG_CONFIG_HOME: "relative" }, home })[0].id, "claude");
  assert.equal(clientTargets({ scope: "local", project, clients: ["codex"], env: { CODEX_HOME: "relative" } })[0].agentsRoot, path.join(project, ".codex", "agents"));
  const explicit = f.at("explicit-opencode");
  assert.equal(clientTargets({ scope: "global", clients: ["opencode"], env: { OPENCODE_CONFIG_DIR: explicit, XDG_CONFIG_HOME: "relative" }, home })[0].configRoot, explicit);
});

test("malformed descriptor options are usage errors and do not mutate input", (t) => {
  const { f, project } = fixture(t);
  for (const options of [null, [], { scope: "other" }, {}, { project, clients: "codex" }, { project, clients: [7] }, { project, skillsDirs: "skills" }, { project, agentsDirs: [""] }, { project, env: null }]) assert.throws(() => clientTargets(options), usage);
  const options = { scope: "local", project, clients: ["codex", "codex"], skillsDirs: ["custom"], agentsDirs: [], env: f.env };
  const original = structuredClone(options);
  clientTargets(options);
  assert.deepEqual(options, original);
});
