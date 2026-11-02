import { readGlobalConfig } from "./global-config.js";
import { describeFailure, runOpenspec } from "./openspec-bin.js";

export const TELEMETRY_OFF_COMMAND = "openspec config set telemetry.enabled false";

/**
 * Состояние телеметрии в глобальном конфиге (переменные окружения OPENSPEC_TELEMETRY, DO_NOT_TRACK, CI не учитываются):
 * "missing" — файла нет; "unreadable" — не JSON (форк в этом случае телеметрию выключает);
 * "off" — enabled: false; "on" — enabled: true; "unset" — ключа нет (у форка это «включена»).
 */
export function telemetryState() {
  const { state, config } = readGlobalConfig();
  if (state !== "ok") return state;
  const enabled = config.telemetry?.enabled;
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
  if (r.notFound || r.error || r.status !== 0) {
    return `telemetry: ${describeFailure(r)} — выключить после установки: ${TELEMETRY_OFF_COMMAND}`;
  }
  return "telemetry: выключена (telemetry.enabled: false в глобальном конфиге OpenSpec)";
}
