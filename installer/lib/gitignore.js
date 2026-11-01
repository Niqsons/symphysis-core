import fs from "node:fs";
import path from "node:path";

/**
 * Вносит строку в `.gitignore` проекта, если её там нет; файла нет — создаёт, git не нужен.
 * Прежние байты не переписываются, конец строки берётся из файла. Возвращает true, если файл изменён.
 */
export function ensureIgnored(root, entry) {
  const file = path.join(root, ".gitignore");
  const before = fs.existsSync(file) ? fs.readFileSync(file).toString("latin1") : "";
  if (before.split(/\r?\n/).some((line) => line.trim() === entry)) return false;
  const eol = before.includes("\r\n") ? "\r\n" : "\n";
  const glue = before && !before.endsWith("\n") ? eol : "";
  fs.appendFileSync(file, `${glue}${entry}${eol}`);
  return true;
}
