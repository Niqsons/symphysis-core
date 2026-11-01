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
  "tools/playground-template.html",
  "docs/journal.schema.json",
];

/** Файл mermaid и лицензия: приходят из зависимости сборки, в git ядра не лежат (F-53). */
const MERMAID_FILES = [
  ["dist/mermaid.min.js", "tools/mermaid.min.js"],
  ["LICENSE", "tools/mermaid.LICENSE"],
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
  // Зависимость сборки тоже проверяется до очистки: без файла поставка не собирается (F-100).
  const mermaid = path.join(root, "installer", "node_modules", "mermaid");
  for (const [from] of MERMAID_FILES) {
    if (!fs.existsSync(path.join(mermaid, from))) {
      throw new Error(`syncPayload: нет ${path.join(mermaid, from)}: поставьте зависимости сборки (npm ci в installer), payload не тронут`);
    }
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
  for (const [from, rel] of MERMAID_FILES) {
    const to = path.join(dest, rel);
    fs.mkdirSync(path.dirname(to), { recursive: true });
    fs.copyFileSync(path.join(mermaid, from), to);
    copied.push(rel);
  }
  return copied;
}

if (process.argv[1] && import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href) {
  const list = syncPayload();
  console.log(`payload: ${list.length} источников -> ${DEFAULT_DEST}`);
}
