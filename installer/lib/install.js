import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { parseDocument, isMap, isSeq, isScalar } from "yaml";
import { ensureContinue } from "./clients.js";
import { ensureIgnored } from "./gitignore.js";
import { globalConfigPath } from "./global-config.js";
import { spawnTool } from "./openspec-bin.js";
import { targets } from "./paths.js";
import { disableTelemetryIfUnset } from "./telemetry.js";
import { hasSources, payloadMatches, ROOT } from "../scripts/sync-payload.js";

const here = path.dirname(fileURLToPath(import.meta.url));
export const DEFAULT_PAYLOAD = path.resolve(here, "..", "payload");
const VERSION_FILE = "symphysis-version.txt";
const SKIP_SUFFIX = "(есть, отличается — перезапись: --force)";
const ROOTS_CONTENT = '{"": "<root>/.."}\n';
const SETTINGS_FILE = "symphysis.yaml";
const SETTINGS_CONTENT = `# Личная настройка symphysis: в git проекта не идёт. Показать состав: symphysis config
consequences:
  failure_branches: true
  assumptions: true
edge_probe:
  enabled: true
drivers:
  attack: true
  probes: false
  consequences: false
  research: true
attack:
  context-compliance: true
  claim-authority: true
  claim-extraction: true
  coverage: true
  scenario-run: true
  trace-link: true
`;

const rel = (project, p) => path.relative(project, p).split(path.sep).join("/");

function walk(dir) {
  const out = [];
  for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, e.name);
    if (e.isDirectory()) out.push(...walk(full));
    else out.push(full);
  }
  return out;
}

/** Пишет байты в `to`: те же — ничего; другие — skipped без force, иначе перезапись. */
function place(res, project, to, bytes, force, { keepExisting = false, schemaDir = null } = {}) {
  if (fs.existsSync(to)) {
    if (fs.readFileSync(to).equals(bytes)) return;
    if (keepExisting) return;
    if (!force) {
      res.skipped.push(`${rel(project, to)} ${SKIP_SUFFIX}`);
      if (schemaDir && to.startsWith(schemaDir + path.sep)) res.messages.push(`пропущен: ${rel(project, to)} — отличается, нужен --force`);
      return;
    }
  }
  fs.mkdirSync(path.dirname(to), { recursive: true });
  fs.writeFileSync(to, bytes);
  res.written.push(rel(project, to));
}

function copyTree(res, project, srcDir, destDir, force, filter = () => true, opts = {}) {
  for (const file of walk(srcDir)) {
    if (!filter(file)) continue;
    place(res, project, path.join(destDir, path.relative(srcDir, file)), fs.readFileSync(file), force, opts);
  }
}

/** Короткий хеш HEAD клона или null: нет git, нет репозитория или каталог лежит внутри чужого репозитория. */
function cloneHash(root) {
  const git = (...args) => spawnTool("git", ["-C", root, ...args], { encoding: "utf8" });
  const top = git("rev-parse", "--show-cdup");
  if (top.error || top.status !== 0 || top.stdout.trim() !== "") return null;
  const head = git("rev-parse", "--short", "HEAD");
  return head.error || head.status !== 0 ? null : head.stdout.trim() || null;
}

/** Текст файла версии: `0.1.0+aa50e8f`; хеш только от клона, с которым payload совпадает (F-36, F-64). */
function versionText(payloadDir, sourceRoot) {
  const { version } = JSON.parse(fs.readFileSync(path.resolve(here, "..", "package.json"), "utf8"));
  const hash = hasSources(sourceRoot) && payloadMatches(payloadDir, sourceRoot) ? cloneHash(sourceRoot) : null;
  return `${hash ? `${version}+${hash}` : version}
`;
}

/** Слияние чужого config.yaml со своим: схема переключается, rules и подсказки operations объединяются, остальное не трогается. */
export function mergeConfig(existingText, oursText) {
  const doc = parseDocument(existingText);
  const ours = parseDocument(oursText).toJS();
  const previous = doc.get("schema");
  const warnings = [];
  doc.set("schema", ours.schema);

  for (const [key, list] of Object.entries(ours.rules ?? {})) {
    let rules = doc.get("rules", true);
    if (!isMap(rules)) {
      doc.set("rules", doc.createNode({}));
      rules = doc.get("rules", true);
    }
    const seq = rules.get(key, true);
    if (!isSeq(seq)) {
      if (!rules.has(key)) rules.set(key, doc.createNode(list));
      else warnings.push(`rules.${key} не список — правила symphysis не добавлены`);
      continue;
    }
    const have = new Set(seq.items.map((i) => (isScalar(i) ? i.value : i)));
    for (const s of list) if (!have.has(s)) seq.add(doc.createNode(s));
  }

  // Подсказки операций (F-49, F-110): как rules — чужие строки остаются, наши добавляются, если их ещё нет.
  for (const [op, body] of Object.entries(ours.operations ?? {})) {
    const list = body?.guidance;
    if (!Array.isArray(list)) continue;
    let operations = doc.get("operations", true);
    if (!isMap(operations)) {
      if (doc.has("operations")) {
        warnings.push("operations не словарь — подсказки symphysis не добавлены");
        break;
      }
      doc.set("operations", doc.createNode({}));
      operations = doc.get("operations", true);
    }
    let entry = operations.get(op, true);
    if (!isMap(entry)) {
      if (operations.has(op)) {
        warnings.push(`operations.${op} не словарь — подсказки symphysis не добавлены`);
        continue;
      }
      operations.set(op, doc.createNode({}));
      entry = operations.get(op, true);
    }
    const seq = entry.get("guidance", true);
    if (!isSeq(seq)) {
      if (!entry.has("guidance")) entry.set("guidance", doc.createNode(list));
      else warnings.push(`operations.${op}.guidance не список — подсказка symphysis не добавлена`);
      continue;
    }
    const have = new Set(seq.items.map((i) => (isScalar(i) ? i.value : i)));
    for (const s of list) if (!have.has(s)) seq.add(doc.createNode(s));
  }
  return { text: doc.toString({ lineWidth: 0 }), previous: previous === undefined || previous === null ? null : String(previous), warnings };
}

/**
 * Ставит схему, скиллы и инструменты журнала в проект, создаёт личный `symphysis.yaml`,
 * вносит его в `.gitignore` и обновляет проект, если в нём нет `/opsx:continue`.
 * Пути в результате — от корня проекта, с «/». `messages` — строки для печати.
 */
export function install(project, { skillsDirs = [], agentsDirs = [], force = false, payloadDir = DEFAULT_PAYLOAD, sourceRoot = ROOT } = {}) {
  const root = path.resolve(project);
  const t = targets(root, skillsDirs, agentsDirs);
  const res = { written: [], merged: [], skipped: [], messages: [] };
  if (!fs.existsSync(path.join(payloadDir, "skills"))) {
    throw new Error(`payload не найден: ${payloadDir} (выполнить npm run prepare)`);
  }

  copyTree(res, root, path.join(payloadDir, "openspec", "schemas", "symphysis"), t.schemaDir, force, () => true, { schemaDir: t.schemaDir });

  const skillsSrc = path.join(payloadDir, "skills");
  for (const e of fs.readdirSync(skillsSrc, { withFileTypes: true })) {
    if (!e.isDirectory() || !e.name.startsWith("symphysis-")) continue;
    for (const dir of t.skillsDirs) copyTree(res, root, path.join(skillsSrc, e.name), path.join(dir, e.name), force);
  }
  // Тела агентов-водителей (`agents/symphysis-*-driver.md`): в каждый каталог агентов, по умолчанию `agents`
  // рядом с каталогом скиллов — у Claude Code это `.claude/agents/` (канон тел, раздел 10).
  const agentsSrc = path.join(payloadDir, "agents");
  if (fs.existsSync(agentsSrc)) {
    for (const dir of t.agentsDirs) copyTree(res, root, agentsSrc, dir, force, (f) => /^symphysis-.*-driver\.md$/.test(path.basename(f)));
  }

  const toolsDir = path.join(t.toolsDir, "tools");
  const skippedBefore = res.skipped.length;
  copyTree(res, root, path.join(payloadDir, "tools"), toolsDir, force, (f) => /^(journal.*\.py|roots\.py|viewer_render\.py|attack_table\.py|symphysis_config\.py|step_help\.py|trace_graph\.py|openspec_run\.py|playground-template\.html|mermaid\.min\.js|mermaid\.LICENSE)$/.test(path.basename(f)));
  // Файл версии описывает поставленные инструменты: если часть пропущена, а файла не было, писать его значило бы
  // назвать версией то, чего в проекте нет. Панель покажет «неизвестно». Уже лежащий файл идёт по общему правилу.
  const toolsPrefix = `${rel(root, toolsDir)}/`;
  const toolsSkipped = res.skipped.slice(skippedBefore).some((line) => line.startsWith(toolsPrefix));
  const versionFile = path.join(toolsDir, VERSION_FILE);
  if (!toolsSkipped || fs.existsSync(versionFile)) place(res, root, versionFile, Buffer.from(versionText(payloadDir, sourceRoot)), force);
  // `docs/` payload целиком: схема журнала, общие файлы скиллов (`terms.md`, `journal-cli.md`, …), уведомления MIT.
  copyTree(res, root, path.join(payloadDir, "docs"), path.join(t.toolsDir, "docs"), force);
  place(res, root, path.join(toolsDir, "journal-roots.json"), Buffer.from(ROOTS_CONTENT), force, { keepExisting: true });

  const oursBytes = fs.readFileSync(path.join(payloadDir, "openspec", "config.symphysis.yaml"));
  if (!fs.existsSync(t.configPath)) {
    place(res, root, t.configPath, oursBytes, force);
  } else {
    const before = fs.readFileSync(t.configPath, "utf8");
    const { text, previous, warnings } = mergeConfig(before, oursBytes.toString("utf8"));
    res.messages.push(...warnings);
    if (text !== before) {
      fs.writeFileSync(t.configPath, text);
      res.merged.push(rel(root, t.configPath));
      res.messages.push(
        previous === null
          ? "config.yaml уже был: схема установлена symphysis, rules добавлены"
          : previous !== "symphysis"
            ? `config.yaml уже был: схема переключена с ${previous} на symphysis, rules добавлены`
            : "config.yaml уже был: схема symphysis, rules добавлены",
      );
    }
  }
  // Файл личный: не перезаписывается и с --force, в git не идёт (F-24.A, F-94.E).
  place(res, root, path.join(root, SETTINGS_FILE), Buffer.from(SETTINGS_CONTENT), force, { keepExisting: true });
  if (ensureIgnored(root, SETTINGS_FILE)) res.messages.push(`.gitignore: добавлена строка ${SETTINGS_FILE} — правка уйдёт в git вместе с работой`);

  // Телеметрия раньше обновления: `config set` записывает профиль, и разовая миграция форка не срабатывает.
  const tele = disableTelemetryIfUnset();
  if (tele) res.messages.push(tele);
  res.messages.push(...ensureContinue(root, t.skillsDirs));
  res.messages.push(`openspec: глобальный конфиг ${globalConfigPath()}`);
  return res;
}
