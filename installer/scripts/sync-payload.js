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
  "tools/step_help.py",
  "tools/openspec_run.py",
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

/** Все файлы дерева: пути от `dir` с «/». */
function walk(dir, prefix = "") {
  return fs.readdirSync(dir, { withFileTypes: true }).flatMap((e) => {
    if (e.isDirectory()) return e.name === "__pycache__" ? [] : walk(path.join(dir, e.name), `${prefix}${e.name}/`);
    return [`${prefix}${e.name}`];
  });
}

/** Стирает дерево: `fs.rmSync` в Node 24 на Windows молча не удаляет по кириллическому пути. */
export function removeTree(dir) {
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
  const fromRoot = [...FILES, ...[...DIRS, ...skillDirs(root)].flatMap((rel) => walk(path.join(root, rel)).map((f) => `${rel}/${f}`))];
  const mermaid = path.join(root, "installer", "node_modules", "mermaid");
  const expected = [...fromRoot.map((rel) => [rel, path.join(root, rel)]), ...MERMAID_FILES.map(([from, rel]) => [rel, path.join(mermaid, from)])];
  if (!fs.existsSync(dest) || walk(dest).length !== expected.length) return false;
  return expected.every(([rel, source]) => {
    const copy = path.join(dest, rel);
    return fs.existsSync(copy) && fs.existsSync(source) && fs.readFileSync(copy).equals(fs.readFileSync(source));
  });
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
  const sources = [...DIRS, ...skills, ...FILES, ...MERMAID_FILES.map(([, rel]) => rel)];
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
  for (const [from, rel] of MERMAID_FILES) {
    const to = path.join(dest, rel);
    fs.mkdirSync(path.dirname(to), { recursive: true });
    fs.copyFileSync(path.join(mermaid, from), to);
  }
  return sources;
}

if (process.argv[1] && import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href) {
  const list = syncPayload();
  console.log(`payload: ${list.length} источников -> ${DEFAULT_DEST}`);
}
