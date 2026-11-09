import path from "node:path";

export const DEFAULT_SKILLS_DIR = path.join(".claude", "skills");

/** Independent of cwd and the current Windows drive; non-string inputs are invalid. */
export function isFullyAbsolute(value, platform = process.platform) {
  if (typeof value !== "string" || !value || value.includes("\0")) return false;
  if (platform !== "win32") return path.posix.isAbsolute(value);
  if (/^[a-z]:[\\/]/i.test(value)) return true;
  if (!/^[\\/]{2}/.test(value)) return false;
  const [server, share] = value.slice(2).split(/[\\/]/);
  return Boolean(server && share && ![".", "..", "?"].includes(server) && ![".", "..", "?"].includes(share));
}

/** Каталог агентов рядом с каталогом скиллов: `.claude/skills` -> `.claude/agents`. */
export function agentsDirFor(skillsDir) {
  return path.join(path.dirname(skillsDir), "agents");
}

/**
 * Раскладка целей установки в проекте. Карты клиентов нет:
 * каталоги скиллов задаёт вызывающий, по умолчанию — один `.claude/skills`;
 * каталоги агентов-водителей — `--agents-dir`, без него `agents` рядом с каждым каталогом скиллов.
 */
export function targets(project, skillsDirs = [], agentsDirs = []) {
  const root = path.resolve(project);
  const dirs = skillsDirs.length ? skillsDirs : [DEFAULT_SKILLS_DIR];
  const skills = dirs.map((d) => path.resolve(root, d));
  const agents = agentsDirs.length ? agentsDirs.map((d) => path.resolve(root, d)) : skills.map(agentsDirFor);
  return {
    schemaDir: path.join(root, "openspec", "schemas", "symphysis"),
    configPath: path.join(root, "openspec", "config.yaml"),
    skillsDirs: skills,
    agentsDirs: agents,
    toolsDir: path.join(root, ".symphysis"),
  };
}
