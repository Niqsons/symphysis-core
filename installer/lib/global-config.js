import fs from "node:fs";
import os from "node:os";
import path from "node:path";

const FILE = ["openspec", "config.json"];

/** Путь конфига форка без XDG_CONFIG_HOME: APPDATA (Windows) или ~/.config. */
function withoutXdg() {
  const base = process.platform === "win32"
    ? process.env.APPDATA || path.join(os.homedir(), "AppData", "Roaming")
    : path.join(os.homedir(), ".config");
  return path.join(base, ...FILE);
}

/** Путь глобального конфига форка — как `getGlobalConfigDir` форка: XDG_CONFIG_HOME, затем APPDATA (Windows) или ~/.config. */
export function globalConfigPath() {
  const xdg = process.env.XDG_CONFIG_HOME;
  return xdg ? path.join(xdg, ...FILE) : withoutXdg();
}

/** Второй файл конфига: XDG_CONFIG_HOME задана не во всех оболочках, и другая оболочка читает его (F-122). */
export function otherConfigPath() {
  const other = withoutXdg();
  return process.env.XDG_CONFIG_HOME && other !== globalConfigPath() && fs.existsSync(other) ? other : null;
}

/**
 * Конфиг как записан, без умолчаний форка.
 * `{ state: "missing" }` — файла нет; `{ state: "unreadable" }` — не JSON или не объект (форк в этом случае телеметрию выключает);
 * `{ state: "ok", config }` — разобран.
 */
export function readGlobalConfig() {
  const file = globalConfigPath();
  if (!fs.existsSync(file)) return { state: "missing" };
  let config;
  try {
    config = JSON.parse(fs.readFileSync(file, "utf8"));
  } catch {
    return { state: "unreadable" };
  }
  if (config === null || typeof config !== "object" || Array.isArray(config)) return { state: "unreadable" };
  return { state: "ok", config };
}
