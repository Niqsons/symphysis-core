import os from "node:os";
import path from "node:path";
import { agentsDirFor, isFullyAbsolute } from "./paths.js";

const CLIENTS = Object.freeze({
  claude: { agentFormat: "claude-md", agentExtension: ".md", workflowCarrier: "commands", commandPrefix: "opsx:" },
  codex: { agentFormat: "codex-toml", agentExtension: ".toml", workflowCarrier: "skills", commandPrefix: null },
  opencode: { agentFormat: "opencode-v2-md", agentExtension: ".md", workflowCarrier: "commands", commandPrefix: "opsx-" },
});
const REQUIRED_WORKFLOWS = Object.freeze(["new", "continue", "apply", "sync", "archive"]);

export class ClientTargetError extends Error {
  constructor(message) {
    super(message);
    this.name = "ClientTargetError";
    this.code = "client-targets-usage";
    this.exitCode = 2;
  }
}

const fail = (message) => { throw new ClientTargetError(message); };
const object = (value) => value !== null && typeof value === "object" && !Array.isArray(value);
function strings(values, name) {
  if (!Array.isArray(values) || values.some((value) => typeof value !== "string" || !value || value.includes("\0"))) fail(`${name}: нужен список непустых строк`);
  return values;
}
function uniquePaths(paths) {
  const seen = new Set();
  return paths.filter((file) => {
    const key = process.platform === "win32" ? file.toLowerCase() : file;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}
function absolute(value, name) {
  if (!isFullyAbsolute(value)) fail(`${name}: нужен абсолютный путь с однозначным корнем`);
  return path.resolve(value);
}

/**
 * Pure descriptors, without profile/executable/filesystem discovery.
 * Without --client, local custom skill paths retain legacy neighboring agents;
 * this remains a Claude/default override, not a claim of native Codex support.
 * With an explicit client, all native roots are independent.
 */
export function clientTargets(options = {}) {
  if (!object(options)) fail("Параметры клиентских каталогов должны быть объектом");
  const { scope = "local", project, clients = [], skillsDirs = [], agentsDirs = [], env = process.env, home } = options;
  if (!["local", "global"].includes(scope)) fail("--scope: допустимы local либо global");
  if (!object(env)) fail("Окружение клиентских каталогов должно быть объектом");
  strings(clients, "--client");
  strings(skillsDirs, "--skills-dir");
  strings(agentsDirs, "--agents-dir");
  const explicitClients = clients.length > 0;
  const selected = [...new Set(clients.length ? clients : ["claude"])];
  for (const id of selected) if (!Object.hasOwn(CLIENTS, id)) fail(`Неизвестный --client: ${id}; допустимы claude, codex, opencode`);
  if (selected.length > 1 && (skillsDirs.length || agentsDirs.length)) fail("--skills-dir/--agents-dir неоднозначны для нескольких --client; выбери одного клиента");
  if (scope === "local" && (typeof project !== "string" || !project || project.includes("\0"))) fail("Local-каталогам нужен явный проект");
  const projectRoot = scope === "local" ? path.resolve(project) : null;
  let cachedHome;
  const userHome = () => cachedHome ??= absolute(home ?? (process.platform === "win32" ? env.USERPROFILE : env.HOME) ?? os.homedir(), "home");
  const configRoot = (key, fallback) => env[key] === undefined ? fallback() : absolute(env[key], key);
  const override = (values, defaults, label) => values.length ? uniquePaths(values.map((value) => scope === "global" ? absolute(value, label) : path.resolve(projectRoot, value))) : defaults;

  return selected.map((id) => {
    let root;
    let skillsRoot;
    if (scope === "local") {
      root = path.join(projectRoot, id === "claude" ? ".claude" : id === "codex" ? ".codex" : ".opencode");
      skillsRoot = path.join(projectRoot, id === "codex" ? ".agents" : id === "claude" ? ".claude" : ".opencode", "skills");
    } else if (id === "claude") {
      root = configRoot("CLAUDE_CONFIG_DIR", () => path.join(userHome(), ".claude"));
      skillsRoot = path.join(root, "skills");
    } else if (id === "codex") {
      root = configRoot("CODEX_HOME", () => path.join(userHome(), ".codex"));
      skillsRoot = path.join(userHome(), ".agents", "skills");
    } else {
      root = configRoot("OPENCODE_CONFIG_DIR", () => path.join(configRoot("XDG_CONFIG_HOME", () => path.join(userHome(), ".config")), "opencode"));
      skillsRoot = path.join(root, "skills");
    }
    // Native clients have independent roots. Only the old local invocation
    // without --client retains agentsDirFor for compatibility with targets().
    const skillsRoots = override(skillsDirs, [skillsRoot], "--skills-dir");
    const legacyTargets = scope === "local" && !explicitClients;
    const defaultAgents = legacyTargets ? uniquePaths(skillsRoots.map(agentsDirFor)) : [path.join(root, "agents")];
    const agentsRoots = override(agentsDirs, defaultAgents, "--agents-dir");
    return {
      id, scope, legacyTargets, configRoot: root, skillsRoots, agentsRoots,
      skillsRoot: skillsRoots.length === 1 ? skillsRoots[0] : null,
      agentsRoot: agentsRoots.length === 1 ? agentsRoots[0] : null,
      commandsRoot: id === "codex" ? null : path.join(root, "commands", ...(id === "claude" ? ["opsx"] : [])),
      ...CLIENTS[id],
      requiredWorkflows: [...REQUIRED_WORKFLOWS],
    };
  });
}
