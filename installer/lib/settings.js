import fs from "node:fs";
import path from "node:path";
import { parseDocument, visit, isAlias, isScalar } from "yaml";

const FILE_NAME = "symphysis.yaml";
const SIGNAL_UNPARSED = `${FILE_NAME}: не разбирается`;
const SIGNAL_NOT_UTF8 = `${FILE_NAME}: не UTF-8`;

// Группа -> вложенный ключ -> поле результата. Map, а не объект: ключ `constructor` не должен найтись.
const KEYS = new Map([
  ["consequences", new Map([["failure_branches", "failure_branches"], ["assumptions", "assumptions"]])],
  ["edge_probe", new Map([["enabled", "edge_probe"]])],
]);

// Таб и управляющие символы читатели понимают по-разному: `enabled:<таб>false` один разбирает,
// другой нет. Поэтому такой файл не разбирается ни одним, тот же класс — в `symphysis_config.py`.
// eslint-disable-next-line no-control-regex
const NOT_YAML_TEXT = /[\x00-\x09\x0b\x0c\x0e-\x1f\x7f-\x9f\u2028\u2029\ufeff\ufffe\uffff]/;

const plain = (_key, value) => (value instanceof Map ? Object.fromEntries(value) : value);

/** Значение в строке сигнала: текст как есть в одну строку, составное — компактным JSON, как у `symphysis_config.py`. */
function show(value) {
  if (typeof value === "string") return value.replace(/\s*\n\s*/g, " ").replace(/^ +| +$/g, "");
  return JSON.stringify(value, plain);
}

/** Разбор текстом: схема failsafe не разбирает типы и не исполняет теги, повтор ключа — последнее значение. */
function parseText(text) {
  if (NOT_YAML_TEXT.test(text)) return { failed: true };
  const doc = parseDocument(text, { schema: "failsafe", uniqueKeys: false });
  if (doc.errors.length) return { failed: true };
  // Составной и пустой ключ: `: x` один читатель отвергает, другой читает как ключ из пустоты.
  let badKey = false;
  visit(doc, {
    Pair(_key, pair) {
      const key = isAlias(pair.key) ? pair.key.resolve(doc) : pair.key;
      if (!isScalar(key) || key.value === "") badKey = true;
    },
  });
  if (badKey) return { failed: true };
  try {
    const data = doc.toJS({ mapAsMap: true });
    JSON.stringify(data, plain); // рекурсивный алиас читатели не принимают
    return { data };
  } catch {
    return { failed: true };
  }
}

/** Разобранный файл -> поля и сигналы. Пустой корень равен пустому файлу, пустое значение — отсутствию ключа (F-50.C, F-109.A). */
function apply(data, settings) {
  if (data === null || data === undefined || data === "") return;
  if (!(data instanceof Map)) {
    settings.signals.push(SIGNAL_UNPARSED);
    return;
  }
  for (const [group, inner] of data) {
    const fields = KEYS.get(group);
    if (!fields) settings.signals.push(`${FILE_NAME}: неизвестный ключ ${group}`);
    else if (inner === "") continue;
    else if (!(inner instanceof Map)) settings.signals.push(`${FILE_NAME}: ${group} — нужен вложенный ключ`);
    else {
      for (const [key, value] of inner) {
        if (!fields.has(key)) settings.signals.push(`${FILE_NAME}: неизвестный ключ ${group}.${key}`);
        else if (value === "false") settings[fields.get(key)] = false;
        else if (value !== "true" && value !== "") settings.signals.push(`${FILE_NAME}: недопустимое значение ${show(value)}`);
      }
    }
  }
}

/**
 * Состав из `<projectRoot>/symphysis.yaml`: те же поля и тексты сигналов, что у `tools/symphysis_config.py`,
 * один файл случаев гоняется на обоих языках (F-110.B, F-113). Нет файла — всё включено без сигнала;
 * сомнение решается во включённую сторону сигналом (F-24.A).
 */
export function readSettings(projectRoot) {
  const settings = { failure_branches: true, assumptions: true, edge_probe: true, signals: [] };
  let bytes;
  try {
    bytes = fs.readFileSync(path.join(projectRoot, FILE_NAME));
  } catch (e) {
    if (e.code !== "ENOENT" && e.code !== "EISDIR") settings.signals.push(SIGNAL_UNPARSED);
    return settings;
  }
  let text;
  try {
    text = new TextDecoder("utf-8", { fatal: true }).decode(bytes); // BOM снимает сам декодер
  } catch {
    settings.signals.push(SIGNAL_NOT_UTF8);
    return settings;
  }
  const { failed, data } = parseText(text);
  if (failed) settings.signals.push(SIGNAL_UNPARSED);
  else apply(data, settings);
  return settings;
}

/** Строка состава: та же у `symphysis_config.py`, `symphysis config` и в `symphysis check`. */
export function compositionLine(settings) {
  const on = (value) => (value ? "вкл" : "выкл");
  return `${FILE_NAME}: ветки отказа ${on(settings.failure_branches)}, допущения ${on(settings.assumptions)}, проба краёв ${on(settings.edge_probe)}`;
}
