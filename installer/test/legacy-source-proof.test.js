import { test } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { createRuntimeFixture } from "../test-support/runtime-fixture.js";
import { spawnTool, runOpenspec } from "../lib/openspec-bin.js";
import { createLegacySourceProof, legacySourceEvidence } from "../lib/legacy-source-proof.js";
import { resolveMigrationContext } from "../lib/runtime-resolver.js";
import { workflowVariantContent } from "../scripts/build-workflow-carriers.js";

const root = fileURLToPath(new URL("../../", import.meta.url));
const commit = "a19a4272fcce49c3cbee1aec6feeb4193748947c";
const sources = ["cli/journal.py", "cli/journal_cli.py", "decisions/journal_model.py", "decisions/journal_render.py", "roots/roots.py", "openspec-run/openspec_run.py", "trace/trace_graph.py", "anchors/anchor_refs.py", "step-help/step_help.py", "settings/symphysis_config.py"];
const blobs = new Map();
function blob(source) {
  if (!blobs.has(source)) {
    const result = spawnTool("git", ["-C", root, "show", `${commit}:${source}`], { encoding: null });
    assert.equal(result.status, 0, "Whitelisted known product blob is required");
    blobs.set(source, Buffer.from(result.stdout));
  }
  return blobs.get(source);
}
function fixture(t, { flat = false, complete = false } = {}) {
  const f = createRuntimeFixture(path.join(os.tmpdir(), "symphysis-legacy-proof-tests"));
  t.after(() => f.cleanup());
  f.env.SYMPHYSIS_OPENSPEC = path.join(root, "upstream", "openspec", "bin", "openspec.js");
  const store = f.store("store-a");
  const runtime = flat ? store.root : path.join(store.root, ".symphysis");
  const schemaRoot = path.join(store.root, "openspec", "schemas", "symphysis");
  for (const source of complete ? sources : sources.slice(0, 2)) f.write(path.join(runtime, "tools", path.basename(source)), blob(source));
  f.write(path.join(schemaRoot, "schema.yaml"), blob("openspec/schemas/symphysis/schema.yaml"));
  const context = { scope: "local", store: { root: store.root, sourceCwd: store.root }, runtime: { legacy: true, manifestPath: null, root: runtime, toolsRoot: path.join(runtime, "tools"), docsRoot: path.join(runtime, "docs"), schemaRoot, generation: "legacy-local" } };
  return { f, store, runtime, context, options: { env: f.env } };
}

for (const flat of [false, true]) test(`typed legacy source proof recognizes exact shared generation in flat=${flat} layout`, (t) => {
  const state = fixture(t, { flat });
  const result = createLegacySourceProof(state.context, state.options);
  assert.equal(result.ready, true, JSON.stringify(result.conflicts));
  assert.equal(result.files.length, 3);
  const facts = legacySourceEvidence(result.proof, state.context);
  assert.equal(facts.storeRoot, state.store.root); assert.equal(facts.root, state.runtime);
  assert.ok(facts.generation.startsWith("pre-global-"));
  facts.files.length = 0;
  assert.equal(legacySourceEvidence(result.proof, state.context).files.length, 3);
  assert.equal(legacySourceEvidence({ ...result.proof }, state.context), null);
  const elsewhere = fixture(t);
  assert.equal(legacySourceEvidence(result.proof, elsewhere.context), null);
});

for (const flaw of ["critical-missing", "changed", "unknown-tool", "unknown-schema", "schema-link"]) test(`legacy source ${flaw} stays unowned and preserved`, (t) => {
  const state = fixture(t);
  if (flaw === "critical-missing") fs.unlinkSync(path.join(state.runtime, "tools", "journal_cli.py"));
  if (flaw === "changed") fs.appendFileSync(path.join(state.runtime, "tools", "journal.py"), "\n# custom\n");
  if (flaw === "unknown-tool") state.f.write(path.join(state.runtime, "tools", "custom_helper.py"), "# foreign\n");
  if (flaw === "unknown-schema") state.f.write(path.join(state.context.runtime.schemaRoot, "unknown.md"), "foreign\n");
  let link;
  if (flaw === "schema-link") { const foreign = state.f.at("foreign"); fs.mkdirSync(foreign); link = path.join(state.context.runtime.schemaRoot, "foreign"); fs.symlinkSync(foreign, link, process.platform === "win32" ? "junction" : "dir"); }
  try {
    const result = createLegacySourceProof(state.context, state.options);
    assert.equal(result.ready, false); assert.equal(result.proof, null); assert.ok(result.conflicts.length);
    assert.ok(fs.existsSync(path.join(state.runtime, "tools", "journal.py")));
  } finally { if (link) fs.unlinkSync(link); }
});

test("source capabilities reject changed bytes and same-byte inode replacement after minting", (t) => {
  const state = fixture(t);
  const first = createLegacySourceProof(state.context, state.options);
  const file = path.join(state.runtime, "tools", "journal.py");
  const replacement = state.f.write(state.f.at("replacement"), fs.readFileSync(file));
  fs.unlinkSync(file); fs.renameSync(replacement, file);
  assert.throws(() => legacySourceEvidence(first.proof, state.context), /измен|changed/i);
  const next = createLegacySourceProof(state.context, state.options);
  fs.appendFileSync(file, "\n# user change\n");
  assert.throws(() => legacySourceEvidence(next.proof, state.context), /измен|changed/i);
});

test("proof reads only public product candidates and preserves unrelated skills", (t) => {
  const state = fixture(t);
  const map = state.f.write(path.join(state.runtime, "tools", "journal-roots.json"), Buffer.from([255, 254]));
  const settings = state.f.write(path.join(state.store.root, "symphysis.yaml"), Buffer.from([255, 254]));
  state.f.write(path.join(state.store.root, ".claude", "skills", "custom-skill", "SKILL.md"), "unrelated\n");
  const original = fs.openSync;
  fs.openSync = function(file, ...args) { if (typeof file === "string" && [map, settings].includes(file)) throw new Error("Private data must not be opened"); return original.call(this, file, ...args); };
  t.after(() => { fs.openSync = original; });
  const result = createLegacySourceProof(state.context, state.options);
  assert.equal(result.ready, true, JSON.stringify(result.conflicts));
  assert.ok(!result.files.some((file) => [map, settings].includes(file.path)));
});

test("explicit native client files need exact known predecessor hashes, including CRLF", (t) => {
  const state = fixture(t);
  const bundle = JSON.parse(fs.readFileSync(path.join(root, "installer", "payload", "docs", "workflow-carriers.json"), "utf8"));
  const entry = bundle.legacyCatalog.find((item) => item.clientId === "codex" && item.id === "continue");
  const file = state.f.write(path.join(state.store.root, ".agents", "skills", entry.relativePath), workflowVariantContent(entry, entry.variants[0]).replace(/\r?\n/g, "\r\n"));
  const result = createLegacySourceProof(state.context, { ...state.options, clients: ["codex"] });
  assert.equal(result.ready, true, JSON.stringify(result.conflicts));
  assert.ok(result.files.some((item) => item.path === file && item.clientId === "codex" && item.purpose === "workflow"));
  fs.appendFileSync(file, "\nUser change\n");
  assert.equal(createLegacySourceProof(state.context, { ...state.options, clients: ["codex"] }).ready, false);
});

for (const flat of [false, true]) test(`a known manifest-less source enables a management-only global preview with one native root, flat=${flat}`, (t) => {
  const state = fixture(t, { complete: true, flat });
  const global = state.f.payload("global");
  state.f.write(state.f.at("user-data", "openspec", "schemas", "symphysis", "schema.yaml"), fs.readFileSync(path.join(global.schemaRoot, "schema.yaml")));
  let minted;
  const calls = [];
  const options = { project: state.store.root, to: "global", env: state.f.env, run(args, options) { calls.push(args); return runOpenspec(args, options); }, schemaRemovalProof(source) { minted = createLegacySourceProof(source, state.options); return minted.proof; } };
  const result = resolveMigrationContext(options);
  assert.equal(minted.ready, true, JSON.stringify(minted.conflicts));
  assert.equal(result.operationReady, true, JSON.stringify(result.diagnostics));
  assert.equal(result.sourceContext.status, "blocked"); assert.equal(result.candidateContext.status, "blocked");
  assert.equal(calls.filter((args) => args[0] === "context").length, 1);
  const forged = resolveMigrationContext({ ...options, schemaRemovalProof() { return { ...minted.proof }; } });
  assert.equal(forged.operationReady, false); assert.ok(forged.diagnostics.some((issue) => issue.code === "migration-ownership-unconfirmed"));
});
