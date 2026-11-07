import fs from "node:fs";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
export const ROOT = path.resolve(here, "..", "..");
export const DEFAULT_DEST = path.resolve(here, "..", "payload");

const DIRS = ["openspec/schemas/symphysis"];

/** Файл лежит в каталоге тестов модуля (F-58): тесты и фикстуры — контур разработки, где бы каталог ни обходился. */
function inTestsDir(rel) {
  return rel.split("/").slice(0, -1).includes("tests");
}

/**
 * Каталог схемы проекта получает не всё: тесты модуля схемы (F-23 A, F-58) и `README.md` модуля (F-36 A) —
 * контур разработки, образец конфига `config.symphysis.yaml` идёт отдельным файлом по прежнему пути payload (F-37 A).
 */
function schemaFileExcluded(rel) {
  return inTestsDir(rel) || rel === "README.md" || rel === "config.symphysis.yaml";
}

/**
 * Код и данные модулей ядра: исходник `<модуль>/<файл>` -> `tools/<файл>` payload, в проекте `.symphysis/tools/`.
 * Исходник разложен по модулям (F-18 A), установка плоская (F-19 A); схема журнала — рядом с кодом (F-41 A).
 */
const TOOLS_FILES = [
  "cli/journal.py",
  "cli/journal_cli.py",
  "decisions/journal_model.py",
  "decisions/journal_render.py",
  "decisions/journal_apply.py",
  "decisions/journal.schema.json",
  "roots/roots.py",
  "viewer/viewer_render.py",
  "viewer/playground-template.html",
  "attack/attack_table.py",
  "consequences/journal_sites.py",
  "consequences/journal_consequences.py",
  "settings/symphysis_config.py",
  "step-help/step_help.py",
  "openspec-run/openspec_run.py",
  "trace/trace_graph.py",
  "anchors/anchor_refs.py",
];

/** Отдельные файлы: [исходник, путь в payload]. Образец конфига лежит в модуле схемы, в payload — по прежнему пути (F-37 A). */
const FILES = [
  ["openspec/schemas/symphysis/config.symphysis.yaml", "openspec/config.symphysis.yaml"],
  ...toolsFiles().map(({ name, src }) => [src, `tools/${name}`]),
];

/**
 * Общие файлы скиллов: исходник в модуле -> `docs/<имя>` payload, в проекте `.symphysis/docs/`, без провенанса.
 * Термины и форма водителя — в `skill-shared`, остальные — в модуле, чью механику описывают (F-35 A, F-66 A).
 */
const SHARED_FILES = [
  "skill-shared/terms.md",
  "skill-shared/driver.md",
  "decisions/candidate.md",
  "cli/journal-cli.md",
  "settings/config.md",
  "attack/attack-table.md",
];
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
  return inTestsDir(rel) || rel.split("/").includes("sources") || path.basename(rel) === "TRANSLATION-NOTES.md";
}

/** Каталоги первого уровня, где ищутся скиллы и водители: без точки в начале (`.claude/` — установка, не исходник). */
function moduleDirs(root) {
  return fs
    .readdirSync(root, { withFileTypes: true })
    .filter((e) => e.isDirectory() && !e.name.startsWith("."))
    .map((e) => e.name)
    .sort();
}

/** Записи `<модуль>/<подкаталог>/` по маске имени: `{ name, src }`, `src` — путь от корня с «/». */
function inModules(root, sub, match) {
  const found = [];
  for (const mod of moduleDirs(root)) {
    const dir = path.join(root, mod, sub);
    if (!fs.existsSync(dir)) continue;
    for (const e of fs.readdirSync(dir, { withFileTypes: true })) if (match(e)) found.push({ name: e.name, src: `${mod}/${sub}/${e.name}` });
  }
  return found;
}

/** Скиллы по маске `<модуль>/skills/symphysis-*` (F-67 A): в payload — `skills/<имя>/`. */
export function skillDirs(root = ROOT) {
  return inModules(root, "skills", (e) => e.isDirectory() && e.name.startsWith("symphysis-"));
}

/** Тела агентов-водителей `<модуль>/agents/symphysis-*-driver.md` (F-67 A): в payload — `agents/`, без провенанса. */
function agentFiles(root) {
  return inModules(root, "agents", (e) => e.isFile() && /^symphysis-.*-driver\.md$/.test(e.name));
}

/** Одно имя в двух модулях установка плоская не различит: ошибка с обоими путями. */
function uniqueNames(entries, what) {
  const seen = new Map();
  for (const { name, src } of entries) {
    if (seen.has(name)) throw new Error(`syncPayload: ${what} ${name} в двух модулях: ${seen.get(name)} и ${src}`);
    seen.set(name, src);
  }
  return entries;
}

/** Файлы кода и данных модулей плоским списком по имени: одно имя в двух модулях — ошибка с обоими путями. */
export function toolsFiles(list = TOOLS_FILES) {
  return uniqueNames(list.map((src) => ({ name: path.posix.basename(src), src })), "файл tools");
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

/**
 * Есть ли рядом исходники: инсталлятор запущен из клона, а не из тарбола. Клон узнаётся по модульной раскладке —
 * скиллы в `<модуль>/skills/`, код и общие файлы скиллов в модулях (F-60); каталога `skills/` в клоне нет.
 */
export function hasSources(root = ROOT) {
  return (
    skillDirs(root).length > 0 &&
    FILES.every(([src]) => fs.existsSync(path.join(root, src))) &&
    SHARED_FILES.every((src) => fs.existsSync(path.join(root, src)))
  );
}

function mermaidDir(root) {
  return path.join(root, "installer", "node_modules", "mermaid");
}

/** Карта payload по исходникам корня: относительный путь с «/» -> байты. Тела `.md` скиллов и общих файлов — без провенанса. */
export function expectedPayload(root = ROOT) {
  const map = new Map();
  const read = (rel) => fs.readFileSync(path.join(root, rel));
  const readStripped = (rel) => Buffer.from(stripProvenance(fs.readFileSync(path.join(root, rel), "utf8")));
  for (const dir of DIRS) for (const f of walk(path.join(root, dir))) if (!schemaFileExcluded(f)) map.set(`${dir}/${f}`, read(`${dir}/${f}`));
  for (const { name, src } of uniqueNames(skillDirs(root), "скилл")) {
    for (const f of walk(path.join(root, src))) {
      if (skillFileExcluded(f)) continue;
      map.set(`skills/${name}/${f}`, f.endsWith(".md") ? readStripped(`${src}/${f}`) : read(`${src}/${f}`));
    }
  }
  for (const src of SHARED_FILES) map.set(`docs/${path.posix.basename(src)}`, readStripped(src));
  for (const { name, src } of uniqueNames(agentFiles(root), "водитель")) map.set(`agents/${name}`, readStripped(src));
  for (const [src, rel] of FILES) map.set(rel, read(src));
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
  uniqueNames(agentFiles(root), "водитель");
  if (uniqueNames(skillDirs(root), "скилл").length === 0) {
    throw new Error(`syncPayload: в корне ${root} нет скиллов <модуль>/skills/symphysis-* — payload не тронут`);
  }
  // Зависимость сборки тоже проверяется до очистки: без файла поставка не собирается (F-100).
  for (const [from] of MERMAID_FILES) {
    if (!fs.existsSync(path.join(mermaidDir(root), from))) {
      throw new Error(`syncPayload: нет ${path.join(mermaidDir(root), from)}: поставьте зависимости сборки (npm ci в installer), payload не тронут`);
    }
  }
  const sources = [
    ...DIRS,
    ...skillDirs(root).map(({ src }) => src),
    ...SHARED_FILES,
    ...agentFiles(root).map(({ src }) => src),
    ...FILES.map(([src]) => src),
    NOTICES[1],
    ...MERMAID_FILES.map(([, rel]) => rel),
  ];
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
