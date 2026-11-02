import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { removeTree } from "../scripts/sync-payload.js";

const made = [];

/** Временный каталог теста: снимается при выходе процесса. Каждый проект несёт копию файла mermaid, и без этого один прогон оставляет в системном каталоге около гигабайта. */
export function tempDir(prefix) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), prefix));
  made.push(dir);
  return dir;
}

process.on("exit", () => {
  for (const dir of made) {
    try {
      removeTree(dir);
    } catch {
      // Занятый или уже снятый каталог не должен ронять прогон.
    }
  }
});
