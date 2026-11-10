import { test, after } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { createRuntimeFixture } from "../test-support/runtime-fixture.js";
import { previewInstallation, applyInstallationReview } from "../lib/installation-review.js";
import { installManaged, DEFAULT_PAYLOAD } from "../lib/managed-install.js";
import { workflowVariantContent } from "../scripts/build-workflow-carriers.js";
import { createInstallationPlan, prepareInstallationPlan } from "../lib/installation-plan.js";
import { runManagementCommand } from "../lib/management-cli.js";
import { spawnTool } from "../lib/openspec-bin.js";
import { applyInstallationPlan, recoverInstallation } from "../lib/installation-transaction.js";
import { spawnSync } from "node:child_process";

const base = process.platform === "win32" ? "X:/codex-tmp" : "/tmp/codex-tmp";
const fork = fileURLToPath(new URL("../../upstream/openspec/bin/openspec.js", import.meta.url));
const fixtures = [];
after(() => { for (const fixture of fixtures) fixture.cleanup(); });
function fixture() { const value = createRuntimeFixture(base); value.env.SYMPHYSIS_OPENSPEC = fork; fixtures.push(value); return value; }
const options = (f) => ({ scope: "global", env: f.env, sourceRoot: f.at("not-a-clone"), clients: ["claude"] });
function knownCarrier(f) {
  const bundle = JSON.parse(fs.readFileSync(path.join(DEFAULT_PAYLOAD, "docs", "workflow-carriers.json"), "utf8"));
  const entry = bundle.legacyCatalog.find((entry) => entry.clientId === "claude" && entry.kind === "command" && entry.id === "continue");
  const content = workflowVariantContent(entry, entry.variants[0]);
  const file = path.join(f.clientRoots.claude.commands, "continue.md");
  fs.mkdirSync(path.dirname(file), { recursive: true }); fs.writeFileSync(file, content);
  return { file, content };
}

test("known native predecessor requires explicit review and confirm before the first global install", () => {
  const f = fixture(); const carrier = knownCarrier(f);
  assert.throws(() => installManaged(undefined, { ...options(f), force: true }), /ownership/);
  const { preview } = previewInstallation(undefined, options(f));
  assert.equal(preview.ready, true, JSON.stringify(preview.conflicts));
  assert.ok(preview.adoptions.some((entry) => entry.path === carrier.file));
  assert.equal(fs.readFileSync(carrier.file, "utf8"), carrier.content);
  assert.equal(fs.existsSync(path.join(f.userDir, "runtime")), false);
  assert.throws(() => applyInstallationReview(preview, options(f)), /--confirm/);
  const applied = applyInstallationReview(preview, { ...options(f), confirm: true });
  assert.equal(applied.manifest.scope, "global");
  assert.match(fs.readFileSync(carrier.file, "utf8"), /Symphysis preflight/);
  assert.ok(applied.manifest.files.some((entry) => entry.path === carrier.file));
});

test("a JSON-shaped adoption proof has no installation authority", () => {
  const f = fixture(); const carrier = knownCarrier(f);
  const { preview, prepared } = previewInstallation(undefined, options(f));
  assert.equal(preview.ready, true);
  const data = prepareInstallationPlan(prepared.plan);
  const files = data.operations.filter((operation) => operation.owned && operation.action !== "remove").map((operation) => ({ path: operation.path, source: operation.source, purpose: operation.purpose, bytes: operation.bytes, projection: operation.projection, clientId: operation.clientId }));
  const fake = createInstallationPlan({ ...data.request, files, adoptionProof: JSON.parse(JSON.stringify({ format: 1, kind: "trusted-predecessor-adoption", files: preview.adoptions })) });
  assert.equal(fake.ready, false);
  assert.ok(fake.conflicts.some((conflict) => conflict.path === carrier.file));
  assert.equal(fs.readFileSync(carrier.file, "utf8"), carrier.content);
});

test("changed predecessor or target environment invalidates the saved review before any write", () => {
  for (const change of ["file", "environment", "json"]) {
    const f = fixture(); const carrier = knownCarrier(f);
    const { preview } = previewInstallation(undefined, options(f));
    if (change === "file") fs.writeFileSync(carrier.file, "user edit\n");
    if (change === "environment") f.env.CLAUDE_CONFIG_DIR = f.at("new-native-root");
    if (change === "json") preview.files[0].afterHash = "0".repeat(64);
    assert.throws(() => applyInstallationReview(preview, { ...options(f), confirm: true }), /после preview|review/);
    assert.equal(fs.existsSync(path.join(f.userDir, "runtime")), false);
    assert.equal(fs.readFileSync(carrier.file, "utf8"), change === "file" ? "user edit\n" : carrier.content);
  }
});

test("unknown native contents remain a conflict even in explicit review", () => {
  const f = fixture(); const carrier = knownCarrier(f); fs.writeFileSync(carrier.file, "foreign\n");
  const { preview } = previewInstallation(undefined, options(f));
  assert.equal(preview.ready, false);
  assert.ok(preview.conflicts.some((conflict) => conflict.path === carrier.file));
  assert.throws(() => applyInstallationReview(preview, { ...options(f), confirm: true }), /конфликт/);
  assert.equal(fs.readFileSync(carrier.file, "utf8"), "foreign\n");
});

test("CLI preview writes only explicit --out and apply rejects all overrides before confirmed adoption", async () => {
  const f = fixture(); const carrier = knownCarrier(f); const output = [];
  const io = { cwd: f.root, env: f.env, stdout: { write: (value) => output.push(value) }, stderr: { write: (value) => output.push(value) } };
  assert.equal(await runManagementCommand(["install", "--scope", "global", "--preview"], io), 0);
  const json = JSON.parse(output.join("")); assert.equal(json.ready, true); output.length = 0;
  assert.equal(fs.existsSync(path.join(f.userDir, "runtime")), false);
  const file = f.at("review.json");
  assert.equal(await runManagementCommand(["install", "--scope", "global", "--preview", "--out", file], io), 0);
  assert.ok(fs.existsSync(file));
  assert.equal(await runManagementCommand(["install", "--apply-plan", file, "--confirm", "--scope", "global"], io), 2);
  assert.equal(await runManagementCommand(["install", "--apply-plan", file], io), 2);
  assert.equal(fs.readFileSync(carrier.file, "utf8"), carrier.content);
  assert.equal(await runManagementCommand(["install", "--apply-plan", file, "--confirm"], io), 0, output.join(""));
  assert.match(fs.readFileSync(carrier.file, "utf8"), /Symphysis preflight/);
});

test("local review accepts only one shipped common generation before creating current ownership", () => {
  const repository = fileURLToPath(new URL("../../", import.meta.url));
  const commit = "a19a4272fcce49c3cbee1aec6feeb4193748947c";
  for (const changed of [false, true]) {
    const f = fixture(); const store = f.store(`old-local-${changed}`, { declaration: false });
    for (const entry of ["cli/journal.py", "cli/journal_cli.py", "decisions/journal_model.py", "decisions/journal_render.py", "roots/roots.py", "openspec-run/openspec_run.py", "trace/trace_graph.py", "anchors/anchor_refs.py", "step-help/step_help.py", "settings/symphysis_config.py", "openspec/schemas/symphysis/schema.yaml"]) {
      const result = spawnTool("git", ["-C", repository, "show", `${commit}:${entry}`], { env: f.env, encoding: null }); assert.equal(result.status, 0);
      f.write(entry.endsWith("schema.yaml") ? path.join(store.root, entry) : path.join(store.root, ".symphysis", "tools", path.basename(entry)), Buffer.from(result.stdout));
    }
    f.write(path.join(store.root, ".symphysis", "tools", "symphysis-version.txt"), "0.1.0+a19a427\n");
    const journal = path.join(store.root, ".symphysis", "tools", "journal.py");
    if (changed) fs.appendFileSync(journal, "\n# user change\n");
    const before = fs.readFileSync(journal);
    const { preview } = previewInstallation(store.root, { ...options(f), scope: "local" });
    assert.equal(preview.ready, !changed, JSON.stringify(preview.conflicts));
    assert.equal(fs.existsSync(path.join(store.root, ".symphysis", "install-manifest.json")), false);
    if (changed) {
      assert.throws(() => applyInstallationReview(preview, { ...options(f), scope: "local", confirm: true }), /конфликт/);
      assert.deepEqual(fs.readFileSync(journal), before);
    } else {
      assert.ok(preview.adoptions.some((entry) => entry.kind === "known-product-generation"));
      const applied = applyInstallationReview(preview, { ...options(f), scope: "local", confirm: true });
      assert.equal(applied.manifest.scope, "local");
    }
  }
});

test("retired known schema recovery uses the reviewed current schema root, preserving its predecessor bytes", () => {
  const f = fixture();
  const repository = fileURLToPath(new URL("../../", import.meta.url));
  const pin = JSON.parse(fs.readFileSync(path.join(repository, "installer", "package.json"), "utf8")).symphysis.openspecPin;
  const runtimeRoot = path.join(f.userDir, "runtime");
  const request = { scope: "global", root: f.userDir, runtimeRoot, storeRoot: null, schemaDirectory: f.at("schema-old"), sourceVersion: "fixture", openspecPin: pin, clients: [], bootstrap: { command: process.execPath, args: [path.join(repository, "installer", "bin", "symphysis.js")] } };
  const sources = [["cli/journal.py", "tools/journal.py", "tool"], ["cli/journal_cli.py", "tools/journal_cli.py", "tool"], ["openspec/schemas/symphysis/schema.yaml", "openspec/schemas/symphysis/schema.yaml", "schema"]];
  const files = sources.map(([original, source, purpose]) => {
    const result = spawnTool("git", ["-C", repository, "show", `a19a4272fcce49c3cbee1aec6feeb4193748947c:${original}`], { env: f.env, encoding: null }); assert.equal(result.status, 0);
    return { source, purpose, path: path.join(runtimeRoot, source), bytes: Buffer.from(result.stdout) };
  });
  applyInstallationPlan(createInstallationPlan({ ...request, files }));
  const changedRequest = { ...request, schemaDirectory: f.at("schema-new") };
  const predecessor = path.join(changedRequest.schemaDirectory, "symphysis", "schema.yaml");
  f.write(predecessor, files[2].bytes);
  const data = f.json(f.at("retired-input.json"), { request: changedRequest, files: files.map((file) => ({ ...file, bytes: file.bytes.toString("base64") })), bundle: path.join(DEFAULT_PAYLOAD, "docs", "workflow-carriers.json") });
  const worker = f.write(f.at("retired-worker.mjs"), `import fs from 'node:fs';
import {createInstallationPlan} from ${JSON.stringify(new URL("../lib/installation-plan.js", import.meta.url).href)};
import {createPredecessorAdoptionProof} from ${JSON.stringify(new URL("../lib/predecessor-adoption.js", import.meta.url).href)};
import {applyInstallationPlan} from ${JSON.stringify(new URL("../lib/installation-transaction.js", import.meta.url).href)};
const input=JSON.parse(fs.readFileSync(process.argv[2],'utf8')); const files=input.files.map(file=>({...file,bytes:Buffer.from(file.bytes,'base64')}));
const proof=createPredecessorAdoptionProof({request:input.request,files,bundle:JSON.parse(fs.readFileSync(input.bundle,'utf8'))});
if(!proof.retiredFiles.length)throw new Error('Expected trusted retired native schema');
const plan=createInstallationPlan({...input.request,files,adoptionProof:proof,removeFiles:proof.retiredFiles.map(file=>file.path)});
if(!plan.ready)throw new Error(JSON.stringify(plan.conflicts));
applyInstallationPlan(plan,{fault(event){if(event.name==='target-renamed'&&event.index===0)process.exit(73);}});
`);
  const child = spawnSync(process.execPath, [worker, data], { env: f.env, encoding: "utf8" });
  assert.equal(child.status, 73, child.stderr);
  const pending = JSON.parse(fs.readFileSync(path.join(f.userDir, ".install-transaction.json"), "utf8"));
  assert.equal(pending.operations[0].predecessor, true);
  assert.equal(recoverInstallation({ root: f.userDir, scope: "global" }).action, "rolled-back");
  assert.deepEqual(fs.readFileSync(predecessor), files[2].bytes);
  assert.equal(JSON.parse(fs.readFileSync(path.join(f.userDir, "install-manifest.json"), "utf8")).schemaDirectory, request.schemaDirectory);
});

test("configured custom workflows are selected from the shipped catalog without changing the profile", () => {
  const f = fixture();
  const config = f.write(f.at("config", "openspec", "config.json"), '{"profile":"custom","workflows":["onboard"],"telemetry":{"enabled":false},"foreign":"keep"}\n');
  const before = fs.readFileSync(config);
  const { preview } = previewInstallation(undefined, options(f));
  assert.equal(preview.ready, true, JSON.stringify(preview.conflicts));
  assert.ok(preview.files.some((file) => file.source === "commands/onboard.md"));
  assert.ok(preview.files.some((file) => file.source === "commands/continue.md"));
  assert.ok(!preview.files.some((file) => file.source === "commands/propose.md"));
  applyInstallationReview(preview, { ...options(f), confirm: true });
  assert.deepEqual(fs.readFileSync(config), before);
  assert.ok(fs.existsSync(path.join(f.clientRoots.claude.commands, "onboard.md")));
});
