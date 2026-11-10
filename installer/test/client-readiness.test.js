import { test } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import os from "node:os";
import { createHash } from "node:crypto";
import { evaluateClientReadiness } from "../lib/client-readiness.js";

const base = process.platform === "win32" ? "X:/codex-tmp" : os.tmpdir();

test("client readiness separates every client, native workflow and session proof", () => {
  const root = fs.mkdtempSync(path.join(base, "client-readiness-"));
  const manifest = { clients: [{ id: "claude" }, { id: "codex" }], files: [] };
  const add = (clientId, source, purpose) => {
    const target = path.join(root, clientId, source);
    fs.mkdirSync(path.dirname(target), { recursive: true });
    fs.writeFileSync(target, `${clientId}: ${source}`);
    manifest.files.push({ clientId, source, purpose, path: target, sha256: createHash("sha256").update(fs.readFileSync(target)).digest("hex") });
    return target;
  };
  for (const id of ["claude", "codex"]) {
    add(id, "skills/symphysis-brainstorm/SKILL.md", "skill");
    add(id, `agents/driver.${id === "codex" ? "toml" : "md"}`, "agent");
    for (const workflow of ["new", "continue", "apply", "sync", "archive"]) {
      add(id, id === "claude" ? `commands/${workflow}.md` : `skills/openspec-${workflow}-${workflow === "sync" ? "specs" : "change"}/SKILL.md`, "workflow");
    }
  }
  let results = evaluateClientReadiness(manifest);
  assert.deepEqual(results.map(({ files, workflow, discovery, sessionVerification }) => [files, workflow, discovery, sessionVerification]),
    [["ready", "ready", "unconfirmed", "unconfirmed"], ["ready", "ready", "unconfirmed", "unconfirmed"]]);
  const second = manifest.files.find((file) => file.clientId === "codex" && file.source.includes("archive"));
  fs.unlinkSync(second.path);
  results = evaluateClientReadiness(manifest);
  assert.equal(results[0].filesystem, "ready");
  assert.equal(results[1].files, "missing");
  assert.equal(results[1].workflow, "missing");
  assert.equal(results[1].missing[0].path, second.path);
  fs.writeFileSync(second.path, "user edit");
  assert.equal(evaluateClientReadiness(manifest)[1].workflow, "conflict");
});

test("an omitted workflow and a client with no managed files remain incomplete", () => {
  const results = evaluateClientReadiness({ clients: [{ id: "opencode" }], files: [] });
  assert.equal(results[0].files, "missing");
  assert.equal(results[0].workflow, "missing");
  assert.deepEqual(results[0].missingWorkflows, ["new", "continue", "apply", "sync", "archive"]);
  assert.equal(results[0].discovery, "unconfirmed");
});
