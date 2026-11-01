import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { runOpenspec } from "./openspec-bin.js";

export const TELEMETRY_OFF_COMMAND = "openspec config set telemetry.enabled false";

/** Путь глобального конфига форка — как `getGlobalConfigDir` форка: XDG_CONFIG_HOME, затем APPDATA (Windows) или ~/.config. */
export function globalConfigPath() {
  const xdg = process.env.XDG_CONFIG_HOME;
  let dir;
  if (xdg) dir = path.join(xdg, "openspec");
  else if (process.platform === "win32") dir = path.join(process.env.APPDATA || path.join(os.homedir(), "AppData", "Roaming"), "openspec");
  else dir = path.join(os.homedir(), ".config", "openspec");
  return path.join(dir, "config.json");
}

/**
 * Состояние телеметрии в глобальном конфиге (переменные окружения OPENSPEC_TELEMETRY, DO_NOT_TRACK, CI не учитываются):
 * "missing" — файла нет; "unreadable" — не JSON (форк в этом случае телеметрию выключает);
 * "off" — enabled: false; "on" — enabled: true; "unset" — ключа нет (у форка это «включена»).
 */
export function telemetryState() {
  const file = globalConfigPath();
  if (!fs.existsSync(file)) return "missing";
  let cfg;
  try {
    cfg = JSON.parse(fs.readFileSync(file, "utf8"));
  } catch {
    return "unreadable";
  }
  const enabled = cfg !== null && typeof cfg === "object" ? cfg.telemetry?.enabled : undefined;
  if (enabled === false) return "off";
  if (enabled === true) return "on";
  return "unset";
}

/**
 * Выключает телеметрию, если ключ не задан. Значение, заданное человеком (в том числе true), не меняется.
 * Читает файл конфига (надёжнее, чем `config get`: различает «нет файла» и «ключ не задан»),
 * пишет через `openspec config set` — форк сам держит формат файла. Возвращает строку для печати или null.
 */
export function disableTelemetryIfUnset() {
  const state = telemetryState();
  if (state !== "missing" && state !== "unset") return null;
  const r = runOpenspec(["config", "set", "telemetry.enabled", "false"]);
  if (r.error || r.status !== 0) {
    return `telemetry: openspec не найден — выключить после установки: ${TELEMETRY_OFF_COMMAND}`;
  }
  return "telemetry: выключена (telemetry.enabled: false в глобальном конфиге OpenSpec)";
}
