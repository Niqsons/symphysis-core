import path from "node:path";

export const DEFAULT_SKILLS_DIR = path.join(".claude", "skills");

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
