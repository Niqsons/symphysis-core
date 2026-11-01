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

/** Все файлы дерева: пути от `dir` с «/». */
function walk(dir, prefix = "") {
  return fs.readdirSync(dir, { withFileTypes: true }).flatMap((e) => {
    if (e.isDirectory()) return e.name === "__pycache__" ? [] : walk(path.join(dir, e.name), `${prefix}${e.name}/`);
    return [`${prefix}${e.name}`];
  });
}

/** Стирает дерево: `fs.rmSync` в Node 24 на Windows молча не удаляет по кириллическому пути. */
function removeTree(dir) {
  for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, e.name);
    if (e.isDirectory()) removeTree(full);
    else fs.unlinkSync(full);
  }
  fs.rmdirSync(dir);
}

/** Есть ли рядом исходники: инсталлятор запущен из клона, а не из тарбола. */
export function hasSources(root = ROOT) {
  return fs.existsSync(path.join(root, "skills")) && FILES.every((rel) => fs.existsSync(path.join(root, rel)));
}

/** Совпадает ли dest с исходниками побайтно: тот же состав файлов и те же байты. */
export function payloadMatches(dest = DEFAULT_DEST, root = ROOT) {
  const expected = [...FILES, ...[...DIRS, ...skillDirs(root)].flatMap((rel) => walk(path.join(root, rel)).map((f) => `${rel}/${f}`))];
  if (!fs.existsSync(dest) || walk(dest).length !== expected.length) return false;
  return expected.every((rel) => {
    const copy = path.join(dest, rel);
    return fs.existsSync(copy) && fs.readFileSync(copy).equals(fs.readFileSync(path.join(root, rel)));
  });
}

/** Стирает и пересоздаёт dest, копируя источники из корня symphysis с теми же относительными путями. */
export function syncPayload(dest = DEFAULT_DEST, root = ROOT) {
  // Корень проверяется до очистки: неудачная синхронизация не оставляет пустой payload.
  if (!fs.existsSync(path.join(root, "skills"))) {
    throw new Error(`syncPayload: в корне ${root} нет каталога skills — payload не тронут`);
  }
  const skills = skillDirs(root);
  const sources = [...DIRS, ...skills, ...FILES];
  // Уже совпадает — не трогать: `npm pack` зовёт `prepare`, пока параллельные тесты читают payload.
  if (payloadMatches(dest, root)) return sources;
  if (fs.existsSync(dest)) removeTree(dest);
  fs.mkdirSync(dest, { recursive: true });
  for (const rel of [...DIRS, ...skills]) {
    fs.cpSync(path.join(root, rel), path.join(dest, rel), { recursive: true, filter: (s) => path.basename(s) !== "__pycache__" });
  }
  for (const rel of FILES) {
    const to = path.join(dest, rel);
    fs.mkdirSync(path.dirname(to), { recursive: true });
    fs.copyFileSync(path.join(root, rel), to);
  }
  return sources;
}

if (process.argv[1] && import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href) {
  const list = syncPayload();
  console.log(`payload: ${list.length} источников -> ${DEFAULT_DEST}`);
}
