import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { parseDocument, isMap, isSeq, isScalar } from "yaml";
import { ensureContinue } from "./clients.js";
import { globalConfigPath } from "./global-config.js";
import { targets } from "./paths.js";
import { disableTelemetryIfUnset } from "./telemetry.js";

const here = path.dirname(fileURLToPath(import.meta.url));
export const DEFAULT_PAYLOAD = path.resolve(here, "..", "payload");
const SKIP_SUFFIX = "(есть, отличается — перезапись: --force)";
const ROOTS_CONTENT = '{"": "<root>/.."}\n';
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

/** Слияние чужого config.yaml со своим: схема переключается, rules объединяются, остальное не трогается. */
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
  return { text: doc.toString({ lineWidth: 0 }), previous: previous === undefined || previous === null ? null : String(previous), warnings };
}

/**
 * Ставит схему, скиллы и инструменты журнала в проект и обновляет его, если в нём нет `/opsx:continue`.
 * Пути в результате — от корня проекта, с «/». `messages` — строки для печати.
 */
export function install(project, { skillsDirs = [], force = false, payloadDir = DEFAULT_PAYLOAD } = {}) {
  const root = path.resolve(project);
  const t = targets(root, skillsDirs);
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

  const toolsDir = path.join(t.toolsDir, "tools");
  copyTree(res, root, path.join(payloadDir, "tools"), toolsDir, force, (f) => /^(journal.*\.py|symphysis_config\.py|playground-template\.html)$/.test(path.basename(f)));
  place(res, root, path.join(t.toolsDir, "docs", "journal.schema.json"), fs.readFileSync(path.join(payloadDir, "docs", "journal.schema.json")), force);
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
  // Телеметрия раньше обновления: `config set` записывает профиль, и разовая миграция форка не срабатывает.
  const tele = disableTelemetryIfUnset();
  if (tele) res.messages.push(tele);
  res.messages.push(...ensureContinue(root, t.skillsDirs));
  res.messages.push(`openspec: глобальный конфиг ${globalConfigPath()}`);
  return res;
}
