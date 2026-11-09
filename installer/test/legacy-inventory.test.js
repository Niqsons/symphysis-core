import { test } from "node:test";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
import { spawnTool } from "../lib/openspec-bin.js";
import { getLegacyInventory, knownLegacyFile, matchingLegacyGenerations, validateLegacyInventory } from "../lib/legacy-inventory.js";
import { buildLegacyInventory, LEGACY_COMMITS } from "../scripts/build-legacy-inventory.js";

const root = fileURLToPath(new URL("../../", import.meta.url));
const blob = (source) => {
  const result = spawnTool("git", ["-C", root, "show", `${LEGACY_COMMITS[0]}:${source}`], { encoding: null });
  assert.equal(result.status, 0);
  return Buffer.from(result.stdout);
};

test("shipped inventory is reproducible from the fixed whitelisted pre-change product blobs", () => {
  assert.deepEqual(buildLegacyInventory(root), getLegacyInventory());
  for (const generation of getLegacyInventory().generations) {
    assert.ok(generation.files.length > 30);
    assert.ok(!generation.files.some((file) => /journal-roots|symphysis\.yaml|(?:^|\/)(?:answers|viewer|sources|tests)\//.test(file.source)));
  }
});

test("known legacy recognition uses exact trusted bytes, including supported Git checkout line endings", () => {
  const original = blob("cli/journal.py");
  assert.ok(knownLegacyFile("tools/journal.py", original));
  const crlf = Buffer.from(original.toString("utf8").replaceAll("\r\n", "\n").replaceAll("\n", "\r\n"));
  assert.ok(knownLegacyFile("tools/journal.py", crlf));
  assert.equal(knownLegacyFile("tools/journal.py", Buffer.concat([original, Buffer.from("\n# user change\n")])), null);
  assert.equal(knownLegacyFile("tools/unknown.py", original), null);
  assert.equal(knownLegacyFile("tools/journal-roots.json", original), null);
  const returned = getLegacyInventory();
  returned.generations[0].files.length = 0;
  assert.ok(knownLegacyFile("tools/journal.py", original));
});

test("a candidate generation needs all critical files and cannot adopt unknown or modified resources", () => {
  const files = [["tools/journal.py", "cli/journal.py"], ["tools/journal_cli.py", "cli/journal_cli.py"],
    ["openspec/schemas/symphysis/schema.yaml", "openspec/schemas/symphysis/schema.yaml"]].map(([source, input]) => ({ source, bytes: blob(input) }));
  assert.ok(matchingLegacyGenerations(files).length);
  assert.deepEqual(matchingLegacyGenerations(files.slice(0, 2)), []);
  assert.deepEqual(matchingLegacyGenerations([...files, { source: "tools/unknown.py", bytes: Buffer.from("custom") }]), []);
  files[0].bytes = Buffer.concat([files[0].bytes, Buffer.from("# changed")]);
  assert.deepEqual(matchingLegacyGenerations(files), []);
});

test("invalid, personal-data and duplicate registry entries fail before matching any file", () => {
  for (const bad of ["format", "personal", "duplicate", "hash", "critical"]) {
    const inventory = getLegacyInventory();
    if (bad === "format") inventory.format = 2;
    if (bad === "personal") inventory.generations[0].files[0].source = "tools/journal-roots.json";
    if (bad === "duplicate") inventory.generations[0].files.push(inventory.generations[0].files[0]);
    if (bad === "hash") inventory.generations[0].files[0].sha256 = ["not a hash"];
    if (bad === "critical") inventory.generations[0].files = inventory.generations[0].files.filter((file) => file.source !== "tools/journal.py");
    assert.throws(() => validateLegacyInventory(inventory));
  }
});
