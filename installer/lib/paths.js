import path from "node:path";

export const DEFAULT_SKILLS_DIR = path.join(".claude", "skills");

/**
 * Раскладка целей установки в проекте. Карты клиентов нет:
 * каталоги скиллов задаёт вызывающий, по умолчанию — один `.claude/skills`.
 */
export function targets(project, skillsDirs = []) {
  const root = path.resolve(project);
  const dirs = skillsDirs.length ? skillsDirs : [DEFAULT_SKILLS_DIR];
  return {
    schemaDir: path.join(root, "openspec", "schemas", "symphysis"),
    configPath: path.join(root, "openspec", "config.yaml"),
    skillsDirs: dirs.map((d) => path.resolve(root, d)),
    toolsDir: path.join(root, ".symphysis"),
  };
}
