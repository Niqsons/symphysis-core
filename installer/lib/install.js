import path from "node:path";
import { installManaged, DEFAULT_PAYLOAD } from "./managed-install.js";
export { DEFAULT_PAYLOAD } from "./managed-install.js";
export { mergeConfig } from "./planning-config.js";

/** Project-local remains the default; management ownership applies in both scopes. */
export function install(project, options = {}) {
  const result = installManaged(project, options);
  if ((options.scope ?? "local") === "global") return result;
  const root = path.resolve(project ?? process.cwd());
  const relative = (file) => path.relative(root, file).split(path.sep).join("/");
  return { ...result, written: result.written.filter((file) => !result.merged.includes(file)).map(relative), merged: result.merged.map(relative) };
}
