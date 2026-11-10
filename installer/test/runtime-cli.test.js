import { test } from "node:test";
import assert from "node:assert/strict";
import { runRuntimeCommand } from "../lib/runtime-cli.js";

test("ambiguous or empty public selectors refuse before runtime or child discovery", async () => {
  for (const args of [
    ["--project", "first", "--project", "second", "journal", "check", "decisions.json"],
    ["--store", "first", "--store", "second", "openspec", "new", "change", "example"],
    ["resolve", "--project", "first", "--project", "second", "--json"],
    ["preflight", "--change", "first", "--change", "second"],
    ["--project=", "journal", "check", "decisions.json"],
    ["resolve", "--project="],
    ["--store=", "help"],
  ]) {
    let stdout = "", stderr = "";
    const code = await runRuntimeCommand(args, {
      env: { PATH: "" }, stdout: { write: (value) => { stdout += value; } }, stderr: { write: (value) => { stderr += value; } },
    });
    assert.equal(code, 2, JSON.stringify(args));
    assert.equal(stdout, "");
    assert.match(stderr, /указан повторно|нужно непустое значение/);
    assert.doesNotMatch(stderr, /planning-root|fork-missing|runtime-missing/);
  }
});
