import fs from "node:fs";
import { createHash } from "node:crypto";

const REQUIRED = ["new", "continue", "apply", "sync", "archive"];
const workflowMatches = (source, id) => new RegExp(`(?:^|/)(?:openspec-|opsx-)?${id}(?:-(?:change|specs))?(?:/SKILL\\.md|\\.md)$`).test(source);
const state = (issues) => issues.some((issue) => issue.reason === "conflict") ? "conflict" : issues.length ? "missing" : "ready";

/** Consume a path-validated manifest. File integrity never proves client discovery. */
export function evaluateClientReadiness(manifest) {
  return (manifest?.clients ?? []).map((client) => {
    const files = manifest.files.filter((file) => file.clientId === client.id);
    const missing = [];
    for (const file of files) {
      let reason;
      try {
        const stat = fs.lstatSync(file.path, { throwIfNoEntry: false });
        if (!stat) reason = "missing";
        else if (!stat.isFile() || stat.isSymbolicLink() || createHash("sha256").update(fs.readFileSync(file.path)).digest("hex") !== file.sha256) reason = "conflict";
      } catch { reason = "conflict"; }
      if (reason) missing.push({ source: file.source, path: file.path, reason });
    }
    const workflows = files.filter((file) => file.purpose === "workflow");
    const missingWorkflows = REQUIRED.filter((id) => !workflows.some((file) => workflowMatches(file.source, id)));
    const incomplete = !files.some((file) => file.purpose === "skill") || !files.some((file) => file.purpose === "agent");
    const fileState = state(missing) === "ready" && incomplete ? "missing" : state(missing);
    const workflowIssues = missing.filter((issue) => workflows.some((file) => file.path === issue.path));
    const workflowState = state(workflowIssues) === "ready" && missingWorkflows.length ? "missing" : state(workflowIssues);
    return { id: client.id, files: fileState, workflow: workflowState,
      filesystem: fileState === "ready" && workflowState === "ready" ? "ready" : "incomplete",
      discovery: "unconfirmed", sessionVerification: "unconfirmed", missing, missingWorkflows };
  });
}
