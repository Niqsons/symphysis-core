import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { isFullyAbsolute } from "./paths.js";

const FILE = ["openspec", "config.json"];

/** Путь конфига форка без XDG_CONFIG_HOME: APPDATA (Windows) или ~/.config. */
function absolute(value, name) {
  if (!isFullyAbsolute(value)) throw Object.assign(new Error(`${name}: нужен полный абсолютный путь`), { exitCode: 2 });
  return value;
}
function withoutXdg(env) {
  const home = () => absolute((process.platform === "win32" ? env.USERPROFILE : env.HOME) ?? os.homedir(), "home");
  const base = process.platform === "win32"
    ? env.APPDATA === undefined ? path.join(home(), "AppData", "Roaming") : absolute(env.APPDATA, "APPDATA")
    : path.join(home(), ".config");
  return path.join(base, ...FILE);
}

/** Путь глобального конфига форка — как `getGlobalConfigDir` форка: XDG_CONFIG_HOME, затем APPDATA (Windows) или ~/.config. */
export function globalConfigPath(env = process.env) {
  const xdg = env.XDG_CONFIG_HOME;
  return xdg === undefined ? withoutXdg(env) : path.join(absolute(xdg, "XDG_CONFIG_HOME"), ...FILE);
}

/** Второй файл конфига: XDG_CONFIG_HOME задана не во всех оболочках, и другая оболочка читает его (F-122). */
export function otherConfigPath(env = process.env) {
  const other = withoutXdg(env);
  return env.XDG_CONFIG_HOME && other !== globalConfigPath(env) && fs.existsSync(other) ? other : null;
}

/**
 * Конфиг как записан, без умолчаний форка.
 * `{ state: "missing" }` — файла нет; `{ state: "unreadable" }` — не JSON или не объект (форк в этом случае телеметрию выключает);
 * `{ state: "ok", config }` — разобран.
 */
export function readGlobalConfig(env = process.env) {
  const file = globalConfigPath(env);
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
