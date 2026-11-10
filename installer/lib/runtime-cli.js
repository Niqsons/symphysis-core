import { parseArgs } from "node:util";
import { resolveRuntime } from "./runtime-resolver.js";
import { dispatchTool } from "./runtime-dispatcher.js";

const HELP = `symphysis resolve / preflight — выбранные store и поставка

Использование:
  symphysis resolve [--project <source>] [--store <id>] --json
  symphysis preflight [--project <source>] [--store <id>] [--json]
  symphysis [--project <source>] [--store <id>] journal|trace|anchors|sync-check|help|openspec <argv...>
  symphysis [--project <source>] [--store <id>] resource skill|doc|template <id>

Звать, когда нужно проверить выбранный runtime и совместимость перед работой.
--project <source>  исходный каталог; planning root определяет OpenSpec context
--store <id>        явно выбранный зарегистрированный store
--json              локальный JSON format 1 с diagnostics и выбранными ресурсами
--change <id>       схема существующего изменения для resolve/preflight
-h, --help          эта справка
Коды: 0 — готово; 2 — usage либо отказ; 1 — внутренняя ошибка.
Только чтение: не устанавливает runtime, не инициализирует и не мигрирует store.
Resolve не выдаёт lease для последующего прямого запуска Python.
`;

/** Locate the command while retaining the legacy command-first option grammar. */
function commandOffset(args) {
  for (let index = 0; index < args.length; index++) {
    const value = args[index];
    if (value === "--project" || value === "--store") { index++; continue; }
    if (value.startsWith("--project=") || value.startsWith("--store=")) continue;
    return index;
  }
  return -1;
}

function validateSelectors(values, tokens) {
  for (const name of ["project", "store", "change"]) {
    if (tokens.filter((token) => token.kind === "option" && token.name === name).length > 1) throw new Error(`--${name} указан повторно`);
    if (values[name] !== undefined && (!values[name] || values[name].startsWith("--") || values[name].includes("\0"))) throw new Error(`--${name}: нужно непустое значение`);
  }
}

/** Null lets the original install/check/config parser keep its existing grammar. */
export async function runRuntimeCommand(args, { stdout = process.stdout, stderr = process.stderr, env = process.env } = {}) {
  const offset = commandOffset(args);
  const command = args[offset];
  const discovery = ["resolve", "preflight"].includes(command);
  if (!discovery && !["journal", "trace", "anchors", "sync-check", "help", "openspec", "resource"].includes(command)) return null;
  if (!discovery) {
    try {
      const { values, tokens } = parseArgs({ args: args.slice(0, offset), tokens: true, options: { project: { type: "string" }, store: { type: "string" } } });
      validateSelectors(values, tokens);
      return await dispatchTool(command, args.slice(offset + 1), { project: values.project, store: values.store, env, stdout, stderr });
    } catch (error) { stderr.write(`${error.message}\n\n${HELP}`); return error.exitCode ?? 2; }
  }
  let values;
  try {
    let tokens;
    ({ values, tokens } = parseArgs({ args: [...args.slice(0, offset), ...args.slice(offset + 1)], tokens: true, options: { project: { type: "string" }, store: { type: "string" }, change: { type: "string" }, json: { type: "boolean" }, help: { type: "boolean", short: "h" } } }));
    validateSelectors(values, tokens);
  } catch (error) { stderr.write(`${error.message}\n\n${HELP}`); return 2; }
  if (values.help) { stdout.write(HELP); return 0; }
  const result = resolveRuntime({ project: values.project, store: values.store, change: values.change, env });
  if (values.json) stdout.write(`${JSON.stringify(result, null, 2)}\n`);
  else if (result.status === "ready") stdout.write(`symphysis ${command}: ${result.scope}, store ${result.store.root}, generation ${result.runtime.generation}\n`);
  else for (const issue of result.diagnostics) stderr.write(`${issue.code}: ${issue.message}\n${issue.action}\n`);
  return result.status === "ready" ? 0 : 2;
}
