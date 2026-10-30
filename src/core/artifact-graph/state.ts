import * as fs from 'node:fs';
import type { Artifact, CompletedSet } from './types.js';
import type { ArtifactGraph } from './graph.js';
import { artifactOutputExists, resolveArtifactOutputPath } from './outputs.js';
import { readFrontmatter } from './frontmatter.js';

/**
 * Detects which artifacts are completed by checking file existence in the change directory.
 * An artifact that declares `verdict` (fork, symphysis C2) is completed only when its file
 * exists and the file's frontmatter carries the declared value.
 * Returns a Set of completed artifact IDs.
 *
 * @param graph - The artifact graph to check
 * @param changeDir - The change directory to scan for files
 * @returns Set of artifact IDs whose generated files exist (and, for verdict artifacts, pass)
 */
export function detectCompleted(graph: ArtifactGraph, changeDir: string): CompletedSet {
  const completed = new Set<string>();

  // Handle missing change directory gracefully
  if (!fs.existsSync(changeDir)) {
    return completed;
  }

  for (const artifact of graph.getAllArtifacts()) {
    const complete = artifact.verdict
      ? verdictState(artifact, changeDir) === 'ok'
      : isArtifactComplete(artifact.generates, changeDir);
    if (complete) {
      completed.add(artifact.id);
    }
  }

  return completed;
}

/**
 * Checks if an artifact is complete by checking if its generated file(s) exist.
 * Supports both simple paths and glob patterns.
 */
function isArtifactComplete(generates: string, changeDir: string): boolean {
  return artifactOutputExists(changeDir, generates);
}

/**
 * State of an artifact's verdict (fork, symphysis C2):
 * - `n/a`      the artifact declares no `verdict`
 * - `missing`  no output file, or no frontmatter / verdict key in it
 * - `mismatch` the key is present but its value (compared as a string) differs
 * - `ok`       the key is present and equals the declared value
 */
export function verdictState(
  artifact: Artifact,
  changeDir: string
): 'n/a' | 'missing' | 'mismatch' | 'ok' {
  const verdict = artifact.verdict;
  if (!verdict) {
    return 'n/a';
  }

  const outputPath = resolveArtifactOutputPath(changeDir, artifact.generates);
  try {
    if (!fs.statSync(outputPath).isFile()) {
      return 'missing';
    }
  } catch {
    return 'missing';
  }

  const frontmatter = readFrontmatter(outputPath);
  if (!frontmatter || !Object.hasOwn(frontmatter, verdict.frontmatter)) {
    return 'missing';
  }

  return String(frontmatter[verdict.frontmatter]) === verdict.value ? 'ok' : 'mismatch';
}
