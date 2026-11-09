import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { createRuntimeFixture } from "./runtime-fixture.js";
import { installationHash } from "../lib/installation-plan.js";

export function installationFixture(t, scope = "global") {
  const f = createRuntimeFixture(path.join(os.tmpdir(), "symphysis-installation-tests"));
  t.after(() => f.cleanup());
  const store = f.store("store-a", { dataOnly: true });
  const other = f.store("store-b", { dataOnly: true });
  const root = scope === "global" ? f.userDir : path.join(store.root, ".symphysis");
  const runtimeRoot = scope === "global" ? path.join(root, "runtime") : root;
  const clients = [{ id: "claude", skillsRoot: f.clientRoots.claude.skills, agentsRoot: f.clientRoots.claude.agents }];
  const request = { scope, root, runtimeRoot, storeRoot: scope === "local" ? store.root : null,
    schemaDirectory: f.at("user-data", "openspec", "schemas"), sourceVersion: "0.1.0-fixture", openspecPin: "1.16.1+symphysis.5", clients,
    bootstrap: { command: process.execPath, args: [fileURLToPath(import.meta.url)] }, files: [] };
  const file = (source, bytes, properties = {}) => {
    let target = path.join(runtimeRoot, source);
    if (scope === "local" && source.startsWith("openspec/")) target = path.join(store.root, source);
    if (scope === "local" && source.startsWith("skills/")) target = path.join(clients[0].skillsRoot, source.slice(7));
    if (properties.projection && source.startsWith("skills/")) target = path.join(clients[0].skillsRoot, source.slice(7));
    if (properties.projection && source.startsWith("openspec/schemas/")) target = path.join(request.schemaDirectory, source.slice("openspec/schemas/".length));
    return { path: target, source, purpose: source.startsWith("tools/") ? "tool" : source.startsWith("docs/") ? "doc" : source.startsWith("skills/") ? "skill" : "schema", bytes: Buffer.from(bytes), ...properties };
  };
  const version = (number) => {
    const files = [file("tools/demo.py", `# runtime ${number}\n`), file("docs/terms.md", `# terms ${number}\n`),
      file("openspec/schemas/symphysis/schema.yaml", `name: symphysis\nversion: ${number}\n`),
      file("skills/symphysis-brainstorm/SKILL.md", `# skill ${number}\n`, scope === "local" ? { clientId: "claude" } : {})];
    if (scope === "global") files.push(file("skills/symphysis-brainstorm/SKILL.md", `# skill ${number}\n`, { projection: true, clientId: "claude" }),
      file("openspec/schemas/symphysis/schema.yaml", `name: symphysis\nversion: ${number}\n`, { projection: true }));
    return { ...request, files };
  };
  return { f, store, other, root, runtimeRoot, request, file, version };
}

export function installationFiles(root) {
  const result = [];
  const walk = (folder, prefix = "") => {
    for (const entry of fs.readdirSync(folder, { withFileTypes: true }).sort((a, b) => a.name.localeCompare(b.name))) {
      const rel = `${prefix}/${entry.name}`;
      if (entry.isSymbolicLink()) result.push([rel, fs.readlinkSync(path.join(folder, entry.name))]);
      else if (entry.isDirectory()) walk(path.join(folder, entry.name), rel);
      else result.push([rel, installationHash(fs.readFileSync(path.join(folder, entry.name)))]);
    }
  };
  walk(root);
  return result;
}
