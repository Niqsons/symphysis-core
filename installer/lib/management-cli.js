import path from "node:path";
import fs from "node:fs";
import { parseArgs } from "node:util";
import { install } from "./install.js";
import { check } from "./check.js";
import { initProject, recoverProjectInitialization } from "./project-init.js";
import { recoverInstallation } from "./installation-transaction.js";
import { userDirectory, resolveRuntime } from "./runtime-resolver.js";
import { dispatchTool } from "./runtime-dispatcher.js";
import { previewInstallation, applyInstallationReview, saveReview } from "./installation-review.js";
import { installationPath } from "./installation-plan.js";
import { previewMigration } from "./migration-plan.js";

export const MANAGEMENT_HELP = `symphysis — установка и инструменты OpenSpec symphysis

Использование:
  symphysis install [--scope local|global] [--client claude|codex|opencode]...
                    [--project <dir>] [--skills-dir <dir>]... [--agents-dir <dir>]... [--force]
  symphysis install --recover [--scope local|global] [--project <dir>]
  symphysis install [--scope local|global] [--project <dir>] [--client <id>]... --preview [--out <plan>]
                    [--skills-dir <dir>]... [--agents-dir <dir>]...
  symphysis install --apply-plan <plan> --confirm
  symphysis init [--scope global] [--project <source>] [--store <id>] [--recover]
  symphysis migrate --to local|global [--project <source>] [--store <id>] [--client <id>]... [--out <plan>]
                    [--skills-dir <dir>]... [--agents-dir <dir>]...
  symphysis migrate --apply-plan <plan> --confirm
  symphysis migrate --recover [--project <source>] [--store <id>]
  symphysis check [--scope local|global] [--project <source>] [--store <id>]
                  [--client <id>]... [--skills-dir <dir>]... [--agents-dir <dir>]...
  symphysis config [--scope local|global] [--project <source>] [--store <id>] [--strict]
  symphysis resolve [--project <source>] [--store <id>] --json
  symphysis preflight [--project <source>] [--store <id>] [--json]
  symphysis [--project <source>] [--store <id>] journal|trace|anchors|help|openspec <argv...>
  symphysis [--project <source>] [--store <id>] resource skill|doc|template <id>

install: local по умолчанию. Global устанавливает общий runtime, пользовательскую
схему и клиентские файлы; не выбирает store, --project/--store с ним запрещены.
init: настроить выбранный OpenSpec planning root для global без локальной копии
runtime. При обнаружении local требуется явная миграция. --recover восстанавливает
только незавершённую операцию выбранного scope/store после проверки владельца.
check: только чтение; проверяет выбранную поставку, схему, настройки и журналы.
Наличие клиентских файлов не подтверждает native discovery или сессию клиента.
config: показать состав личных настроек выбранного store; --strict называет ошибки.
migrate: сначала показать выбранные собственные копии, источники, назначения и конфликты;
после просмотра --apply-plan --confirm заново проверяет пути, байты и поколения.
Другие store и их общий runtime не переводятся вслед за выбранным.

--scope local|global     independent scope install/check (init поддерживает global)
--client <id>           повторяемый; claude, codex, opencode; install/check
--project <dir>         исходный каталог; local install — место установки
--store <id>            store через закреплённый OpenSpec context; init/check/config
--skills-dir <dir>      повторяемый override каталога скиллов одного клиента
--agents-dir <dir>      повторяемый override каталога агентов одного клиента
                        local: от --project; global: только полный абсолютный путь
                        Без --client local сохраняет прежние соседние agents.
                        Повторный install без overrides сохраняет прежние targets.
--force                 совместимый флаг install; ownership-защиту не отключает
--recover               явное восстановление install или init; не новая установка
--preview               install: только показать файлы/конфликты и known predecessor adoption
--out <plan>            сохранить preview; без --out JSON идёт только в stdout
--apply-plan <plan>      заново проверить install/migrate preview и применить его
--confirm               явное подтверждение после просмотра --apply-plan
-h, --help              эта справка

Коды: 0 — выполнено; 2 — usage, конфликт или расхождения; 1 — внутренняя ошибка.
Маркеры check: [!!] расхождение, [..] сигнал. Системные зависимости не ставятся.
`;

function offsetOf(args) {
  const values = new Set(["--project", "--store", "--scope", "--client", "--skills-dir", "--agents-dir", "--to", "--out", "--apply-plan"]);
  for (let index = 0; index < args.length; index++) {
    if (values.has(args[index])) { index++; continue; }
    if (args[index].startsWith("-")) continue;
    return index;
  }
  return -1;
}
const fail = (message) => { throw Object.assign(new Error(message), { exitCode: 2, usage: true }); };
function readSavedPlan(file) {
  try { return JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(fs.readFileSync(file))); }
  catch { throw Object.assign(new Error(`План не прочитан как UTF-8 JSON: ${file}`), { exitCode: 2 }); }
}

export async function runManagementCommand(args, { cwd = process.cwd(), env = process.env, stdout = process.stdout, stderr = process.stderr } = {}) {
  const offset = offsetOf(args);
  const command = args[offset];
  if (args.some((arg) => ["-h", "--help"].includes(arg)) && !["install", "check", "init", "config", "migrate", "resolve", "preflight", "journal", "trace", "anchors", "help", "openspec", "resource"].includes(command)) { stdout.write(MANAGEMENT_HELP); return 0; }
  if (!["install", "check", "init", "config", "migrate"].includes(command) && !(offset === -1 && args.some((arg) => ["-h", "--help"].includes(arg)))) return null;
  try {
    const { values, positionals, tokens } = parseArgs({ args: args.filter((_, index) => index !== offset), allowPositionals: true, tokens: true, options: {
      scope: { type: "string" }, project: { type: "string" }, store: { type: "string" }, to: { type: "string" }, client: { type: "string", multiple: true }, "skills-dir": { type: "string", multiple: true }, "agents-dir": { type: "string", multiple: true }, force: { type: "boolean" }, recover: { type: "boolean" }, strict: { type: "boolean" }, preview: { type: "boolean" }, out: { type: "string" }, "apply-plan": { type: "string" }, confirm: { type: "boolean" }, help: { type: "boolean", short: "h" },
    } });
    if (values.help) { stdout.write(MANAGEMENT_HELP); return 0; }
    if (positionals.length) fail(`Лишние аргументы: ${positionals.join(" ")}`);
    for (const name of ["scope", "project", "store", "to", "out", "apply-plan"]) {
      if (tokens.filter((token) => token.kind === "option" && token.name === name).length > 1) fail(`--${name} указан повторно`);
      if (values[name] !== undefined && (!values[name] || values[name].startsWith("--") || values[name].includes("\0"))) fail(`--${name}: нужно непустое значение`);
    }
    if (values.scope && !["local", "global"].includes(values.scope)) fail("--scope: допустимы local либо global");
    const allowed = { install: ["scope", "project", "client", "skills-dir", "agents-dir", "force", "recover", "preview", "out", "apply-plan", "confirm"], init: ["scope", "project", "store", "recover"], check: ["scope", "project", "store", "client", "skills-dir", "agents-dir"], config: ["scope", "project", "store", "strict"], migrate: ["project", "store", "to", "client", "skills-dir", "agents-dir", "out", "apply-plan", "confirm", "recover"] }[command];
    for (const key of Object.keys(values)) if (!allowed.includes(key)) fail(`--${key} не поддерживается командой ${command}`);
    const project = values.project === undefined ? cwd : path.resolve(cwd, values.project);
    if (command === "config" && !fs.statSync(project, { throwIfNoEntry: false })?.isDirectory()) fail(`--project: каталога нет: ${project}`);
    if (command === "migrate") {
      if (values["apply-plan"]) {
        if (Object.keys(values).some((key) => !["apply-plan", "confirm"].includes(key))) fail("--apply-plan не принимает новые selectors/targets/out overrides");
        if (!values.confirm) fail("--apply-plan требует явный --confirm после просмотра preview");
        const file = installationPath(path.resolve(cwd, values["apply-plan"]));
        const preview = readSavedPlan(file);
        const { applyMigrationPlan } = await import("./migration-transaction.js");
        const result = applyMigrationPlan(preview, { confirm: Boolean(values.confirm), env });
        stdout.write(`Миграция завершена: ${result.from} → ${result.to}; store ${result.storeRoot}\n`);
        for (const warning of result.warnings ?? []) stdout.write(`[..] ${warning.message}; ${warning.action}\n`);
        return 0;
      }
      if (values.recover) {
        if (Object.keys(values).some((key) => !["project", "store", "recover"].includes(key))) fail("migrate --recover не принимает новые цели перехода");
        const { recoverMigration } = await import("./migration-transaction.js");
        const result = recoverMigration({ project, store: values.store, env });
        stdout.write(result.recovered ? `Миграция восстановлена: ${result.action}\n` : "Незавершённой миграции нет\n");
        return 0;
      }
      if (values.confirm) fail("--confirm требует --apply-plan");
      if (!["local", "global"].includes(values.to)) fail("migrate требует --to local|global");
      const preview = previewMigration({ project, store: values.store, to: values.to, clients: values.client ?? [], skillsDirs: values["skills-dir"] ?? [], agentsDirs: values["agents-dir"] ?? [], env });
      if (values.out) stdout.write(`Preview: ${saveReview(path.resolve(cwd, values.out), preview)}\n`);
      else stdout.write(`${JSON.stringify(preview, null, 2)}\n`);
      return preview.ready ? 0 : 2;
    }
    if (command === "install") {
      if (values["apply-plan"]) {
        if (Object.keys(values).some((key) => !["apply-plan", "confirm"].includes(key))) fail("--apply-plan нельзя совмещать с новыми project/scope/client/dirs/force overrides");
        if (!values.confirm) fail("--apply-plan требует явный --confirm после просмотра preview");
        const file = installationPath(path.resolve(cwd, values["apply-plan"]));
        const preview = readSavedPlan(file);
        const result = applyInstallationReview(preview, { confirm: Boolean(values.confirm), env });
        stdout.write(`записано ${result.written.length}\n`); for (const message of result.messages) stdout.write(`${message}\n`);
        return 0;
      }
      if (values.confirm) fail("--confirm требует --apply-plan");
      if (values.out && !values.preview) fail("--out разрешён только вместе с --preview");
      if (values.preview && (values.recover || values.force)) fail("--preview нельзя совмещать с --recover или --force");
      const scope = values.scope ?? "local";
      if (scope === "global" && values.project !== undefined) fail("Global install не принимает --project или --store; для store выполни symphysis init");
      if (values.recover && ["client", "skills-dir", "agents-dir", "force"].some((key) => values[key] !== undefined)) fail("install --recover не принимает новые targets или --force");
      if (values.recover) {
        const result = recoverInstallation({ scope, root: scope === "global" ? userDirectory(env) : path.join(project, ".symphysis") });
        stdout.write(result.recovered ? `Восстановлено: ${result.action}\n` : "Незавершённой установки нет\n"); return 0;
      }
      if (values.preview) {
        const { preview } = previewInstallation(scope === "global" ? undefined : project, { scope, env, clients: values.client ?? [], skillsDirs: values["skills-dir"] ?? [], agentsDirs: values["agents-dir"] ?? [] });
        if (values.out) stdout.write(`Preview: ${saveReview(path.resolve(cwd, values.out), preview)}\n`);
        else stdout.write(`${JSON.stringify(preview, null, 2)}\n`);
        return preview.ready ? 0 : 2;
      }
      const result = install(scope === "global" ? undefined : project, { scope, env, clients: values.client ?? [], skillsDirs: values["skills-dir"] ?? [], agentsDirs: values["agents-dir"] ?? [], force: Boolean(values.force) });
      stdout.write(`записано ${result.written.length}\n`);
      for (const message of result.messages) stdout.write(`${message}\n`);
      return 0;
    }
    if (command === "init") {
      if (values.scope && values.scope !== "global") fail("init настраивает global; для local выполни symphysis install --scope local");
      const result = values.recover ? recoverProjectInitialization({ project, store: values.store, env }) : initProject({ project, store: values.store, env });
      if (values.recover) stdout.write(result.recovered ? `Store init восстановлен: ${result.action}\n` : "Незавершённого store init нет\n");
      else for (const message of result.messages) stdout.write(`${message}\n`);
      return 0;
    }
    if (command === "check") {
      const result = check(project, { scope: values.scope, store: values.store, env, clients: values.client ?? [], skillsDirs: values["skills-dir"] ?? [], agentsDirs: values["agents-dir"] ?? [] });
      for (const finding of result.findings) stdout.write(`[!!] ${finding}\n`);
      for (const note of result.notes) stdout.write(`[..] ${note}\n`);
      stdout.write(result.ok ? "check: ok\n" : `check: ${result.findings.length} расхождений\n`);
      return result.ok ? 0 : 2;
    }
    if (values.scope) {
      const context = resolveRuntime({ project, store: values.store, env });
      if (context.scope !== values.scope) fail(`--scope ${values.scope}: выбран ${context.scope ?? "неразрешённый"} runtime; требуется явная миграция`);
    }
    return await dispatchTool("config", values.strict ? ["--strict"] : [], { project, store: values.store, env, stdout, stderr });
  } catch (error) {
    const usage = error.usage || String(error.code ?? "").startsWith("ERR_PARSE_ARGS");
    stderr.write(`symphysis ${command ?? ""}: ${error.message}\n${usage ? `\n${MANAGEMENT_HELP}` : ""}`);
    return usage ? 2 : error.exitCode ?? 1;
  }
}
