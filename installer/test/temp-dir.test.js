import { test } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath, pathToFileURL } from "node:url";

const helper = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "test-support", "temp-dir.js");

test("временный каталог снимается при выходе процесса, и по кириллическому пути", () => {
  const code = `
    import fs from "node:fs";
    import path from "node:path";
    import { tempDir } from ${JSON.stringify(pathToFileURL(helper).href)};
    const dir = tempDir("symphysis-снятие-");
    fs.mkdirSync(path.join(dir, "а", "б"), { recursive: true });
    fs.writeFileSync(path.join(dir, "а", "б", "файл.txt"), "x");
    console.log(dir);
  `;
  const r = spawnSync(process.execPath, ["--input-type=module", "-e", code], { encoding: "utf8" });
  assert.equal(r.status, 0, r.stderr);
  const dir = r.stdout.trim();
  assert.match(dir, /symphysis-снятие-/);
  assert.equal(fs.existsSync(dir), false);
});
