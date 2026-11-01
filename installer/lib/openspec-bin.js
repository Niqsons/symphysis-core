import { spawnSync } from "node:child_process";

const win = process.platform === "win32";

/**
 * Запускает форк OpenSpec с аргументами: SYMPHYSIS_OPENSPEC (.js или исполняемый) либо `openspec` из PATH.
 * Возвращает результат spawnSync; `r.error` или ненулевой `status` — не запустился.
 */
export function runOpenspec(args) {
  const env = process.env.SYMPHYSIS_OPENSPEC;
  if (env) {
    if (env.endsWith(".js")) return spawnSync(process.execPath, [env, ...args], { encoding: "utf8" });
    if (win && /\.(cmd|bat)$/i.test(env)) return spawnSync(`"${env}" ${args.join(" ")}`, { encoding: "utf8", shell: true });
    return spawnSync(env, args, { encoding: "utf8" });
  }
  // на Windows openspec из PATH — это openspec.cmd, его запускает только оболочка
  return win ? spawnSync(`openspec ${args.join(" ")}`, { encoding: "utf8", shell: true }) : spawnSync("openspec", args, { encoding: "utf8" });
}
