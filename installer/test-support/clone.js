import fs from "node:fs";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

/** Корень клона ядра, из которого идут тесты. */
export const REPO = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");

/**
 * Модули ядра, из которых собирается payload (F-18 A, F-67 A): код и данные, скиллы `<модуль>/skills/`,
 * водители `<модуль>/agents/`, общие файлы скиллов. Каталога `skills/` у клона нет.
 */
export const SOURCE_MODULES = [
  "anchors", "attack", "cli", "consequences", "decisions", "openspec-run", "probes", "research", "roots", "settings",
  "skill-shared", "step-help", "trace", "viewer",
];

export const gitIn = (cwd, ...args) =>
  spawnSync("git", ["-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false", ...args], { cwd, encoding: "utf8" });

/**
 * Клон-образец в модульной раскладке в каталоге `dir`: модули, схема, файлы mermaid — чтобы хеш и свежесть payload
 * задавались тестом. `git` — клон под git с одним коммитом. Возвращает `dir`.
 */
export function makeClone(dir, { git }) {
  const keep = (s) => path.basename(s) !== "__pycache__";
  for (const rel of [...SOURCE_MODULES, path.join("openspec", "schemas", "symphysis")]) {
    fs.cpSync(path.join(REPO, rel), path.join(dir, rel), { recursive: true, filter: keep });
  }
  const mer = path.join(dir, "installer", "node_modules", "mermaid");
  fs.mkdirSync(path.join(mer, "dist"), { recursive: true });
  fs.copyFileSync(path.join(REPO, "installer", "node_modules", "mermaid", "dist", "mermaid.min.js"), path.join(mer, "dist", "mermaid.min.js"));
  fs.copyFileSync(path.join(REPO, "installer", "node_modules", "mermaid", "LICENSE"), path.join(mer, "LICENSE"));
  if (git) {
    gitIn(dir, "init", "-q");
    gitIn(dir, "add", "-A");
    const done = gitIn(dir, "commit", "-qm", "один");
    if (done.status !== 0) throw new Error(`клон-образец: коммит не прошёл: ${done.stderr}`);
  }
  return dir;
}
