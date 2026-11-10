import { test } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";

const directory = new URL("./fixtures/runtime-contract/", import.meta.url);
const read = (name) => JSON.parse(fs.readFileSync(new URL(name, directory), "utf8"));
const schema = read("resolve.schema.json");
const resolver = read("cases.json");
const launcher = read("launch-cases.json");

// Deliberately limited to keywords used in this fixture schema. This checks
// fixture consistency; product implementations are exercised in adapter tests.
function matches(value, rule) {
  if (rule.$ref) return matches(value, schema.$defs[rule.$ref.split("/").at(-1)]);
  if (rule.anyOf && !rule.anyOf.some((part) => matches(value, part))) return false;
  if (rule.allOf && !rule.allOf.every((part) => matches(value, part))) return false;
  if (rule.if && !matches(value, matches(value, rule.if) ? rule.then : (rule.else ?? {}))) return false;
  if (Object.hasOwn(rule, "const") && value !== rule.const) return false;
  if (rule.enum && !rule.enum.includes(value)) return false;
  if (rule.type) {
    const types = Array.isArray(rule.type) ? rule.type : [rule.type];
    const valid = types.some((type) => ({
      null: value === null,
      object: value !== null && typeof value === "object" && !Array.isArray(value),
      array: Array.isArray(value),
      integer: Number.isInteger(value),
      string: typeof value === "string",
      boolean: typeof value === "boolean",
    })[type]);
    if (!valid) return false;
  }
  if (typeof value === "number" && rule.minimum !== undefined && value < rule.minimum) return false;
  if (typeof value === "string") {
    if (rule.minLength !== undefined && value.length < rule.minLength) return false;
    if (rule.pattern && !new RegExp(rule.pattern).test(value)) return false;
  }
  if (Array.isArray(value)) {
    if (rule.minItems !== undefined && value.length < rule.minItems) return false;
    if (rule.items && !value.every((item) => matches(item, rule.items))) return false;
  } else if (value !== null && typeof value === "object") {
    if (rule.required?.some((key) => !Object.hasOwn(value, key))) return false;
    for (const [key, item] of Object.entries(value)) {
      const child = rule.properties?.[key] ?? rule.additionalProperties;
      if (child === false || (child && !matches(item, child))) return false;
    }
  }
  return true;
}

const response = (contract) => JSON.parse(JSON.stringify(resolver.responseTemplate).replace('"$journalContract"', String(contract)));

function mutate(value, mutation) {
  const locate = (pointer) => {
    const keys = pointer.split("/").slice(1);
    const key = keys.pop();
    return [keys.reduce((item, segment) => item[segment], value), key];
  };
  for (const [pointer, item] of Object.entries(mutation.set ?? {})) {
    const [parent, key] = locate(pointer);
    parent[key] = item;
  }
  for (const pointer of mutation.remove ?? []) {
    const [parent, key] = locate(pointer);
    delete parent[key];
  }
  return value;
}

test("resolver examples validate without reserving the journal contract", () => {
  for (const contract of [17, 913]) assert.ok(matches(response(contract), schema));
  for (const item of resolver.invalidResponses) {
    assert.equal(matches(mutate(response(17), item), schema), false, item.id);
  }
});

test("blocked keeps selected runtime and unknown APIs; legacy is representable", () => {
  const blocked = response(17);
  blocked.status = "blocked";
  blocked.compatibility.status = "incompatible";
  blocked.runtime.runtimeApi = 999;
  blocked.runtime.journalContract = null;
  blocked.diagnostics = [{ code: "declaration-incompatible", message: "Incompatible store", action: "Run explicit initialization or migration" }];
  assert.ok(matches(blocked, schema));
  const legacy = response(17);
  legacy.scope = "local";
  legacy.runtime.legacy = true;
  legacy.runtime.generation = "legacy-local";
  legacy.runtime.manifestPath = null;
  legacy.runtime.sourceVersion = null;
  legacy.compatibility.declarationPath = null;
  assert.ok(matches(legacy, schema));
  assert.ok(matches({ ...blocked, scope: null, runtime: null, resources: null, store: null }, schema));
});

test("path schema accepts native absolute paths and refuses cwd-dependent values", () => {
  for (const item of ["/fixture/store", "X:/fixture/store", "X:\\fixture\\store", "\\\\server\\share\\fixture"]) assert.ok(matches(item, schema.$defs.absolutePath), item);
  for (const item of ["", ".", "../store", "X:store", "tools/journal.py"]) assert.equal(matches(item, schema.$defs.absolutePath), false, item);
});

test("conformance matrix distinguishes local, data-only, global and refusal", () => {
  assert.equal(resolver.format, 1);
  assert.equal(new Set(resolver.cases.map((item) => item.id)).size, resolver.cases.length);
  for (const { id, input, expected } of resolver.cases) {
    assert.equal(expected.writes, 0, id);
    assert.equal(expected.exitCode, expected.status === "ready" ? 0 : 2, id);
    if (expected.status === "blocked") assert.match(expected.diagnosticCode, /^[a-z][a-z0-9-]+$/, id);
    if (["managed", "legacy", "damaged", "bad-manifest"].includes(input.local) && expected.scope !== undefined) assert.equal(expected.scope, "local", id);
    if (input.local === "data-only" && input.global === "managed") assert.equal(expected.scope, "global", id);
  }
  for (const id of ["local-only", "global-only", "both-local-first", "legacy-local-first", "damaged-local-no-fallback", "no-installed-runtime", "data-only-map-is-not-runtime", "global-incompatible-declaration", "global-missing-declaration", "missing-local-resource-not-global", "pointer-source", "same-change-store-a", "same-change-store-b", "late-store-cannot-bypass", "late-schema-cannot-bypass"]) assert.ok(resolver.cases.some((item) => item.id === id), id);
});

test("launch fixtures preserve argv and require dispatcher child lifetime", () => {
  assert.equal(launcher.format, 1);
  for (const item of launcher.launchCases) {
    const { expected } = item;
    assert.equal(expected.execution, "dispatcher");
    assert.equal(expected.lease, "child-lifetime");
    assert.ok(matches(expected.command, schema.$defs.absolutePath));
    assert.ok(matches(expected.cwd, schema.$defs.absolutePath));
    assert.ok(expected.args.every((arg) => typeof arg === "string"));
    assert.deepEqual(expected.args.slice(-item.argv.length), item.argv, item.id);
    const prefix = [...item.launcher.prefixArgs, "--project", item.source];
    if (item.store) prefix.push("--store", item.store);
    prefix.push(item.tool);
    assert.deepEqual(expected.args.slice(0, -item.argv.length), prefix, item.id);
  }
});

test("discovery and handshake carry refusal cases for every host adapter", () => {
  for (const group of [launcher.discoveryCases, launcher.handshakeCases, launcher.launchCases]) assert.equal(new Set(group.map((item) => item.id)).size, group.length);
  for (const id of ["missing-bootstrap", "relative-explicit-no-fallback", "missing-explicit-no-fallback", "js-needs-node", "relative-node-no-fallback", "relative-path-entry-ignored"]) assert.ok(launcher.discoveryCases.find((item) => item.id === id)?.expected.diagnosticCode, id);
  for (const id of ["old-cli-no-resolve", "malformed-json", "empty-json", "wrong-store", "wrong-journal-contract", "blocked-exit-zero", "ready-exit-two", "timeout"]) assert.match(launcher.handshakeCases.find((item) => item.id === id)?.expected ?? "", /^reject-/, id);
});
