import fs from "node:fs";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
export const ROOT = path.resolve(here, "..", "..");
export const DEFAULT_DEST = path.resolve(here, "..", "payload");

const DIRS = ["openspec/schemas/symphysis"];
const FILES = [
  "openspec/config.symphysis.yaml",
  "tools/journal.py",
  "tools/journal_model.py",
  "tools/journal_render.py",
  "tools/journal_apply.py",
  "tools/journal_cli.py",
  "tools/journal_sites.py",
  "tools/journal_consequences.py",
  "tools/symphysis_config.py",
  "tools/playground-template.html",
  "docs/journal.schema.json",
];

function skillDirs(root) {
  return fs
    .readdirSync(path.join(root, "skills"), { withFileTypes: true })
    .filter((e) => e.isDirectory() && e.name.startsWith("symphysis-"))
    .map((e) => `skills/${e.name}`);
}

/** Стирает и пересоздаёт dest, копируя источники из корня symphysis с теми же относительными путями. */
export function syncPayload(dest = DEFAULT_DEST, root = ROOT) {
  // Корень проверяется до очистки: неудачная синхронизация не оставляет пустой payload.
  if (!fs.existsSync(path.join(root, "skills"))) {
    throw new Error(`syncPayload: в корне ${root} нет каталога skills — payload не тронут`);
  }
  const skills = skillDirs(root);
  fs.rmSync(dest, { recursive: true, force: true });
  fs.mkdirSync(dest, { recursive: true });
  const copied = [];
  for (const rel of [...DIRS, ...skills]) {
    fs.cpSync(path.join(root, rel), path.join(dest, rel), { recursive: true, filter: (s) => path.basename(s) !== "__pycache__" });
    copied.push(rel);
  }
  for (const rel of FILES) {
    const to = path.join(dest, rel);
    fs.mkdirSync(path.dirname(to), { recursive: true });
    fs.copyFileSync(path.join(root, rel), to);
    copied.push(rel);
  }
  return copied;
}

if (process.argv[1] && import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href) {
  const list = syncPayload();
  console.log(`payload: ${list.length} источников -> ${DEFAULT_DEST}`);
}
