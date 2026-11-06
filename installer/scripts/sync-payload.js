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
  "tools/roots.py",
  "tools/viewer_render.py",
  "tools/attack_table.py",
  "tools/journal_cli.py",
  "tools/journal_sites.py",
  "tools/journal_consequences.py",
  "tools/symphysis_config.py",
  "tools/step_help.py",
  "tools/openspec_run.py",
  "tools/trace_graph.py",
  "tools/playground-template.html",
  "docs/journal.schema.json",
];

/** Общие файлы скиллов: `skills/shared/*.md` -> `docs/*.md`, в проекте `.symphysis/docs/`. */
const SHARED_DIR = "skills/shared";
/** Тела агентов-водителей: `agents/symphysis-*-driver.md` -> `agents/` payload, без провенанса. */
const AGENTS_DIR = "agents";
/** Уведомления MIT о донорах: переведённые механики — производная работа, копий доноров в поставке нет. */
const NOTICES = ["installer/THIRD-PARTY-NOTICES.md", "docs/THIRD-PARTY-NOTICES.md"];

/** Файл mermaid и лицензия: приходят из зависимости сборки, в git ядра не лежат (F-53). */
const MERMAID_FILES = [
  ["dist/mermaid.min.js", "tools/mermaid.min.js"],
  ["LICENSE", "tools/mermaid.LICENSE"],
];

/**
 * Провенанс в телах: комментарии `<!-- src: … -->` и `<!-- dev: … -->` отдельной строкой
 * или блоком. Контур разработки, в продукт не идут (docs/skills-canon.md, раздел 9).
 */
const PROVENANCE = /^[ \t]*<!--[ \t]*(?:src|dev)\b[\s\S]*?-->[ \t]*\r?\n?/gm;

export function stripProvenance(text) {
  return text.replace(PROVENANCE, "");
}

/** Каталог `sources/` скилла (выписки доноров, заметки перевода) — контур разработки. */
function skillFileExcluded(rel) {
  return rel.split("/").includes("sources") || path.basename(rel) === "TRANSLATION-NOTES.md";
}

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

function mermaidDir(root) {
  return path.join(root, "installer", "node_modules", "mermaid");
}

/** Карта payload по исходникам корня: относительный путь с «/» -> байты. Тела `.md` скиллов и общих файлов — без провенанса. */
export function expectedPayload(root = ROOT) {
  const map = new Map();
  const read = (rel) => fs.readFileSync(path.join(root, rel));
  const readStripped = (rel) => Buffer.from(stripProvenance(fs.readFileSync(path.join(root, rel), "utf8")));
  for (const dir of DIRS) for (const f of walk(path.join(root, dir))) map.set(`${dir}/${f}`, read(`${dir}/${f}`));
  for (const skill of skillDirs(root)) {
    for (const f of walk(path.join(root, skill))) {
      if (skillFileExcluded(f)) continue;
      map.set(`${skill}/${f}`, f.endsWith(".md") ? readStripped(`${skill}/${f}`) : read(`${skill}/${f}`));
    }
  }
  if (fs.existsSync(path.join(root, SHARED_DIR))) {
    for (const f of walk(path.join(root, SHARED_DIR))) if (f.endsWith(".md")) map.set(`docs/${f}`, readStripped(`${SHARED_DIR}/${f}`));
  }
  if (fs.existsSync(path.join(root, AGENTS_DIR))) {
    for (const f of walk(path.join(root, AGENTS_DIR))) if (/^symphysis-.*-driver\.md$/.test(f)) map.set(`${AGENTS_DIR}/${f}`, readStripped(`${AGENTS_DIR}/${f}`));
  }
  for (const rel of FILES) map.set(rel, read(rel));
  const [noticeFrom, noticeTo] = NOTICES;
  if (fs.existsSync(path.join(root, noticeFrom))) map.set(noticeTo, read(noticeFrom));
  for (const [from, rel] of MERMAID_FILES) map.set(rel, fs.readFileSync(path.join(mermaidDir(root), from)));
  return map;
}

/** Совпадает ли dest с исходниками побайтно: тот же состав файлов и те же байты. */
export function payloadMatches(dest = DEFAULT_DEST, root = ROOT) {
  if (!fs.existsSync(dest)) return false;
  const expected = expectedPayload(root);
  if (walk(dest).length !== expected.size) return false;
  for (const [rel, bytes] of expected) {
    const copy = path.join(dest, rel);
    if (!fs.existsSync(copy) || !fs.readFileSync(copy).equals(bytes)) return false;
  }
  return true;
}

/** Стирает и пересоздаёт dest по карте `expectedPayload`. Возвращает список источников. */
export function syncPayload(dest = DEFAULT_DEST, root = ROOT) {
  // Корень проверяется до очистки: неудачная синхронизация не оставляет пустой payload.
  if (!fs.existsSync(path.join(root, "skills"))) {
    throw new Error(`syncPayload: в корне ${root} нет каталога skills — payload не тронут`);
  }
  // Зависимость сборки тоже проверяется до очистки: без файла поставка не собирается (F-100).
  for (const [from] of MERMAID_FILES) {
    if (!fs.existsSync(path.join(mermaidDir(root), from))) {
      throw new Error(`syncPayload: нет ${path.join(mermaidDir(root), from)}: поставьте зависимости сборки (npm ci в installer), payload не тронут`);
    }
  }
  const sources = [...DIRS, ...skillDirs(root), SHARED_DIR, ...FILES, NOTICES[1], ...MERMAID_FILES.map(([, rel]) => rel)];
  // Уже совпадает — не трогать: `npm pack` зовёт `prepare`, пока параллельные тесты читают payload.
  if (payloadMatches(dest, root)) return sources;
  const expected = expectedPayload(root);
  if (fs.existsSync(dest)) removeTree(dest);
  fs.mkdirSync(dest, { recursive: true });
  for (const [rel, bytes] of expected) {
    const to = path.join(dest, rel);
    fs.mkdirSync(path.dirname(to), { recursive: true });
    fs.writeFileSync(to, bytes);
  }
  return sources;
}

if (process.argv[1] && import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href) {
  const list = syncPayload();
  console.log(`payload: ${list.length} источников -> ${DEFAULT_DEST}`);
}
