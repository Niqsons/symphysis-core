import { test } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import os from "node:os";
import { gzipSync, gunzipSync } from "node:zlib";
import { fileURLToPath } from "node:url";
import { createHash } from "node:crypto";
import { buildWorkflowCarriers, guardWorkflowBody, REQUIRED_WORKFLOWS, selectWorkflowCarriers, validateWorkflowBundle, workflowVariantContent, writeWorkflowCarriers } from "../scripts/build-workflow-carriers.js";
import { workflowArchiveEntries } from "../scripts/workflow-archive.js";
import { expectedPayload, syncPayload, hasSources } from "../scripts/sync-payload.js";
import { makeClone } from "../test-support/clone.js";
import { createRuntimeFixture } from "../test-support/runtime-fixture.js";
import { runOpenspec } from "../lib/openspec-bin.js";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const pkg = JSON.parse(fs.readFileSync(path.join(ROOT, "installer", "package.json"), "utf8"));
const archive = fs.readFileSync(path.join(ROOT, pkg.symphysis.openspecSource));
const tempBase = path.join(os.tmpdir(), "symphysis-workflow-tests");
const fixture = (t) => { const f = createRuntimeFixture(tempBase); t.after(() => f.cleanup()); return f; };

function tar(entries) {
  const blocks = [];
  for (const entry of entries) {
    const bytes = entry.bytes ?? Buffer.alloc(0);
    const header = Buffer.alloc(512);
    let name = entry.name;
    let prefix = "";
    if (Buffer.byteLength(name) > 100) { const split = name.lastIndexOf("/"); prefix = name.slice(0, split); name = name.slice(split + 1); }
    header.write(name, 0, 100, "utf8");
    header.write("0000600\0", 100); header.write("0000000\0", 108); header.write("0000000\0", 116);
    header.write(bytes.length.toString(8).padStart(11, "0") + "\0", 124);
    header.write("00000000000\0", 136); header.fill(32, 148, 156);
    header.write(entry.type ?? (entry.directory ? "5" : "0"), 156);
    if (entry.link) header.write(entry.link, 157);
    header.write("ustar\0", 257); header.write("00", 263); header.write(prefix, 345, 155, "utf8");
    const checksum = header.reduce((sum, byte) => sum + byte, 0);
    header.write(checksum.toString(8).padStart(6, "0") + "\0 ", 148);
    blocks.push(header, bytes, Buffer.alloc((512 - bytes.length % 512) % 512));
  }
  return gzipSync(Buffer.concat([...blocks, Buffer.alloc(1024)]));
}

function archiveRoot(f, mutate) {
  const root = f.at("build-root");
  const entries = workflowArchiveEntries(archive);
  if (mutate) mutate(entries);
  f.json(path.join(root, "installer", "package.json"), { symphysis: { openspecPin: pkg.symphysis.openspecPin, openspecSource: "vendor/pinned.tgz" } });
  f.write(path.join(root, "vendor", "pinned.tgz"), tar(entries));
  return root;
}

test("real pinned archive produces reproducible native carriers for all required workflows and three clients", async () => {
  const first = await buildWorkflowCarriers({ root: ROOT, tempBase });
  const second = await buildWorkflowCarriers({ root: ROOT, tempBase });
  assert.deepEqual(second, first);
  assert.equal(first.pin, pkg.symphysis.openspecPin);
  assert.equal(first.archiveSha256, createHash("sha256").update(archive).digest("hex"));
  assert.ok(first.workflows.includes("propose") && first.workflows.includes("explore") && first.workflows.includes("update"));
  assert.ok(REQUIRED_WORKFLOWS.every((id) => first.workflows.includes(id)));
  assert.equal(first.files.length, first.workflows.length * 3);
  assert.equal(first.catalog.length, first.profiles.all.length * 3);
  assert.match(first.licenses[0].text, /Copyright \(c\) 2024 OpenSpec Contributors/);
  for (const file of first.catalog) {
    const content = workflowVariantContent(file, file.variants.at(-1));
    const body = content.slice(content.indexOf("**Symphysis preflight"));
    assert.match(body, /before.*Write.*Edit|no Write, Edit/s);
    assert.match(body, /preflight.*--change <name>/s);
    assert.match(body, /symphysis openspec store list --json/);
    const unwrapped = body.replace(/symphysis(?: --(?:store|project) (?:"[^"]+"|<[^>]+>))* openspec /g, "GUARDED ");
    assert.doesNotMatch(unwrapped, /\bopenspec (?:new|status|instructions|list|show|validate|archive|doctor|context|schemas|schema|init|update|store|config|templates)\b/);
    for (const example of body.split("`")) if (!example.includes("\n") && example.startsWith("symphysis openspec ")) assert.ok(!example.includes(" --store "), "inline store selectors belong to the bootstrap prefix");
    assert.doesNotMatch(body, /append the flag/);
    assert.doesNotMatch(content, /Bash\(\*\)|Bash\(openspec:\*\)/);
    if (file.clientId !== "opencode") assert.match(content, /allowed-tools: Bash\(symphysis:\*\)/);
    if (file.clientId === "codex") {
      assert.equal(file.kind, "skill");
      assert.doesNotMatch(body, /\/opsx[:\-]/);
      assert.match(file.relativePath, /^openspec-.*\/SKILL\.md$/);
    } else if (file.clientId === "opencode") {
      assert.doesNotMatch(body, /\/opsx:/);
      assert.match(file.relativePath, /^opsx-.*\.md$/);
    } else assert.match(file.relativePath, /^opsx\/.*\.md$/);
    assert.ok(body.includes("openspec/"), "data paths remain OpenSpec paths");
  }
});

test("native core/custom profiles select every prebuilt workflow without runtime generation or lost requirements", async () => {
  const bundle = await buildWorkflowCarriers({ root: ROOT, tempBase });
  const before = structuredClone(bundle);
  assert.deepEqual(selectWorkflowCarriers(bundle).workflows, bundle.workflows);
  assert.deepEqual(bundle.profiles.dependencies["bulk-archive"], ["sync"]);
  for (const id of bundle.profiles.all) {
    const selection = selectWorkflowCarriers(bundle, { profile: "custom", workflows: [id] });
    assert.ok(selection.workflows.includes(id));
    assert.ok(REQUIRED_WORKFLOWS.every((required) => selection.workflows.includes(required)));
    assert.equal(selection.files.length, selection.workflows.length * 3);
    for (const clientId of ["claude", "codex", "opencode"]) assert.equal(selection.files.filter((file) => file.clientId === clientId && file.id === id).length, 1);
  }
  assert.deepEqual(selectWorkflowCarriers(bundle, { profile: "custom" }).workflows, [...REQUIRED_WORKFLOWS]);
  assert.deepEqual(selectWorkflowCarriers(bundle, { profile: "custom", workflows: ["onboard", "verify", "onboard"] }).workflows, [...REQUIRED_WORKFLOWS, "onboard", "verify"]);
  for (const options of [{ profile: "unknown" }, { profile: "custom", workflows: "verify" }, { profile: "custom", workflows: ["unknown"] }, { profile: "custom", workflows: [null] }]) assert.throws(() => selectWorkflowCarriers(bundle, options), /Unknown native/);
  assert.deepEqual(bundle, before);
  for (const corruption of ["missing-catalog", "missing-client", "dependency", "selection-drift"]) {
    const invalid = structuredClone(bundle);
    if (corruption === "missing-catalog") delete invalid.catalog;
    if (corruption === "missing-client") invalid.catalog.pop();
    if (corruption === "dependency") invalid.profiles.dependencies.archive = ["unknown"];
    if (corruption === "selection-drift") invalid.files[0].content += "\nextra";
    assert.throws(() => validateWorkflowBundle(invalid), /catalog|carrier|differs/);
  }
  for (const corruption of ["invalid-hex", "index-range", "odd-bytes", "expanded-limit", "variant-hash", "fragment-type"]) {
    const invalid = structuredClone(bundle);
    const entry = invalid.legacyCatalog[0];
    const variant = entry.variants[0];
    if (corruption === "invalid-hex") variant.lines = "not canonical hex!";
    if (corruption === "index-range") variant.lines = gzipSync(Buffer.from([255, 255])).toString("hex");
    if (corruption === "odd-bytes") variant.lines = gzipSync(Buffer.from([0])).toString("hex");
    if (corruption === "expanded-limit") variant.lines = gzipSync(Buffer.alloc(20002)).toString("hex");
    if (corruption === "variant-hash") variant.sha256 = "0".repeat(64);
    if (corruption === "fragment-type") entry.fragments[0] = null;
    assert.throws(() => validateWorkflowBundle(invalid), undefined, corruption);
  }
});

test("all conditional variants reference only selected workflows and legacy bytes match real native init", async (t) => {
  const bundle = await buildWorkflowCarriers({ root: ROOT, tempBase });
  for (const file of bundle.catalog) for (const variant of file.variants) {
    const selected = new Set([...REQUIRED_WORKFLOWS, file.id, ...variant.selected]);
    const content = workflowVariantContent(file, variant);
    const body = content.slice(content.indexOf("**Symphysis preflight"));
    assert.doesNotMatch(body, /\[\[opsx:/);
    assert.doesNotMatch(body.replace(/symphysis openspec /g, "GUARDED "), /\bopenspec (?:new|status|instructions|archive|update|init|store|schema|validate)\b/);
    for (const match of body.matchAll(/\/opsx[:\-]([a-z-]+)/g)) assert.ok(selected.has(match[1]), `${file.id}: ${match[0]}`);
    for (const match of body.matchAll(/(?:\$|\/)(openspec-[a-z-]+)/g)) assert.ok(bundle.catalog.some((candidate) => candidate.clientId === "codex" && selected.has(candidate.id) && candidate.relativePath.startsWith(`${match[1]}/`)), `${file.id}: ${match[0]}`);
  }
  const f = fixture(t);
  const project = f.at("native-project"); fs.mkdirSync(project);
  const result = runOpenspec(["init", project, "--tools", "claude,codex,opencode", "--profile", "core", "--no-animation", "--no-copilot-cloud"], { cwd: project, env: { ...f.env, SYMPHYSIS_OPENSPEC: path.join(ROOT, "upstream", "openspec", "bin", "openspec.js") }, timeout: 30000 });
  assert.equal(result.status, 0, `${result.stdout}\n${result.stderr}`);
  const roots = { claude: { skill: ".claude/skills", command: ".claude/commands" }, codex: { skill: ".agents/skills" }, opencode: { skill: ".opencode/skills", command: ".opencode/commands" } };
  let checked = 0;
  for (const file of bundle.legacyCatalog.filter((entry) => bundle.profiles.core.includes(entry.id))) {
    const variant = file.variants.find((item) => file.conditions.every((id) => item.selected.includes(id) === bundle.profiles.core.includes(id)));
    const target = path.join(project, roots[file.clientId][file.kind], file.relativePath);
    const content = workflowVariantContent(file, variant);
    assert.equal(fs.readFileSync(target, "utf8"), content, `${file.clientId}/${file.kind}/${file.id}`);
    assert.equal(variant.sha256, createHash("sha256").update(fs.readFileSync(target)).digest("hex"));
    assert.equal(file.legacy, true); assert.equal(file.readOnly, true);
    assert.doesNotMatch(content, /\*\*Symphysis preflight/);
    checked++;
  }
  assert.equal(checked, bundle.profiles.core.length * 5);
});

test("custom selected additions preserve required workflows and resolve every native cross-reference", async () => {
  const bundle = await buildWorkflowCarriers({ root: ROOT, tempBase, workflowIds: ["onboard", "verify"] });
  assert.deepEqual(bundle.workflows, [...REQUIRED_WORKFLOWS, "onboard", "verify"]);
  const skillNames = new Set(bundle.files.filter((file) => file.clientId === "codex").map((file) => file.relativePath.split("/")[0]));
  for (const file of bundle.files) {
    const body = file.content.slice(file.content.indexOf("**Symphysis preflight"));
    assert.doesNotMatch(body, /(?<!symphysis )\bopenspec --(?:version|help)\b/);
    assert.doesNotMatch(body, /Get-Command openspec\b/);
    for (const match of file.content.matchAll(/\/opsx[:\-]([a-z-]+)/g)) assert.ok(bundle.workflows.includes(match[1]), `${file.id}: ${match[0]}`);
    for (const match of file.content.matchAll(/(?:\$|\/)(openspec-[a-z-]+)/g)) assert.ok(skillNames.has(match[1]), `${file.id}: ${match[0]}`);
  }
  await assert.rejects(buildWorkflowCarriers({ root: ROOT, tempBase, workflowIds: ["invented-workflow"] }), /Unknown requested/);
});

test("compiler rejects a changed package pin, generator export or allowed-tools format without publishing an asset", async (t) => {
  for (const mutation of ["pin", "export", "allowed-tools"]) {
    const f = fixture(t);
    const root = archiveRoot(f, (entries) => {
      if (mutation === "pin") {
        const entry = entries.find((entry) => entry.name === "package/package.json");
        const value = JSON.parse(entry.bytes.toString()); value.version = "0.0.0-foreign";
        entry.bytes = Buffer.from(JSON.stringify(value));
      } else {
        const entry = entries.find((entry) => entry.name.endsWith(mutation === "export" ? "/shared/skill-generation.js" : "/shared/allowed-tools.js"));
        entry.bytes = Buffer.from(entry.bytes.toString().replaceAll(mutation === "export" ? "getSkillTemplates" : "Bash(openspec:*)", mutation === "export" ? "renamedSkillTemplates" : "Bash(*)"));
      }
    });
    await assert.rejects(writeWorkflowCarriers({ root, tempBase }), /version\/format|exports changed|allowed-tools/);
    assert.equal(fs.existsSync(path.join(root, "installer", "generated", "workflow-carriers.json")), false);
  }
});

test("tar validation rejects traversal, Windows aliases, links, duplicate names and bad checksums", () => {
  for (const entry of [
    { name: "package/../outside.js" }, { name: "/absolute.js" }, { name: "package/C:drive.js" },
    { name: "package/dir\\escape.js" }, { name: "package/NUL.txt" },
    { name: "package/symlink", type: "2", link: "../../outside" },
    { name: "package/hardlink", type: "1", link: "package/package.json" },
    { name: "package/pax", type: "x" },
  ]) assert.throws(() => workflowArchiveEntries(tar([entry])));
  assert.throws(() => workflowArchiveEntries(tar([{ name: "package/a" }, { name: "package/A" }])), /Duplicate/);
  const broken = Buffer.from(archive); broken[20] ^= 1;
  assert.throws(() => workflowArchiveEntries(broken));
  const badHeader = gunzipSync(tar([{ name: "package/a" }])); badHeader[100] ^= 1;
  assert.throws(() => workflowArchiveEntries(gzipSync(badHeader)), /checksum/);
  assert.throws(() => guardWorkflowBody("pinned marker disappeared", "expected store guidance"), /marker changed/);
});

test("generated bundle publication is idempotent and payload carries verified JSON bytes", async (t) => {
  const f = fixture(t);
  const root = archiveRoot(f);
  const first = await writeWorkflowCarriers({ root, tempBase });
  assert.equal(first.changed, true);
  const before = fs.statSync(first.path).mtimeMs;
  assert.equal((await writeWorkflowCarriers({ root, tempBase })).changed, false);
  assert.equal(fs.statSync(first.path).mtimeMs, before);
  const clone = f.at("source-clone");
  makeClone(clone, { git: false });
  assert.equal(hasSources(clone), true);
  const asset = path.join(clone, "installer", "generated", "workflow-carriers.json");
  assert.deepEqual(expectedPayload(clone).get("docs/workflow-carriers.json"), fs.readFileSync(asset));
  const destination = f.at("payload");
  syncPayload(destination, clone);
  assert.deepEqual(fs.readFileSync(path.join(destination, "docs", "workflow-carriers.json")), fs.readFileSync(asset));
  const invalid = JSON.parse(fs.readFileSync(asset)); invalid.format = 2;
  f.json(asset, invalid);
  await assert.rejects(async () => syncPayload(destination, clone), /metadata\/pin/);
  assert.equal(fs.existsSync(path.join(destination, "tools", "journal.py")), true, "bad source asset does not erase payload");
});

test("bundle validation rejects unsupported metadata and non-native targets", async () => {
  const bundle = await buildWorkflowCarriers({ root: ROOT, tempBase });
  const invalid = structuredClone(bundle);
  invalid.files[0].relativePath = "../outside.md";
  assert.throws(() => validateWorkflowBundle(invalid), /carrier/);
  assert.throws(() => validateWorkflowBundle(bundle, { pin: "foreign-pin" }), /metadata\/pin/);
});
