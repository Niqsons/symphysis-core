import { createHash } from 'node:crypto';
import * as fs from 'node:fs';
import * as path from 'node:path';
import type { ApplyPhase, Artifact, CompletedSet, VerdictStatus } from './types.js';
import type { ArtifactGraph } from './graph.js';
import { artifactOutputExists, resolveArtifactOutputPath, resolveArtifactOutputs } from './outputs.js';
import { readFrontmatter } from './frontmatter.js';
import { FileSystemUtils } from '../../utils/file-system.js';
import { parseTaskLines } from '../../utils/task-progress.js';

/**
 * Detects which artifacts are completed by checking file existence in the change directory.
 * An artifact that declares `verdict` (fork, symphysis C2) is completed only when its file
 * exists and the file's frontmatter carries the declared value (and, C7, every target hash
 * it declares still matches).
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
 * Fork (symphysis, C7): the optional artifacts whose output does not exist.
 *
 * Such an artifact satisfies the `requires` of its dependents and is left out
 * of planning completeness. Once its output exists it is judged like any other
 * artifact - by `detectCompleted`, verdict included; deleting the output makes
 * it absent again.
 */
export function detectAbsentOptional(graph: ArtifactGraph, changeDir: string): Set<string> {
  const absent = new Set<string>();
  const changeDirExists = fs.existsSync(changeDir);

  for (const artifact of graph.getAllArtifacts()) {
    if (artifact.optional && !(changeDirExists && isArtifactComplete(artifact.generates, changeDir))) {
      absent.add(artifact.id);
    }
  }

  return absent;
}

/**
 * Fork (symphysis, C11): what closed a stale verdict's window - the next step
 * that has begun since the verdict was written.
 * - `dependent` an artifact that directly `requires` this one has output (its id)
 * - `tracks`    nothing requires this one, `apply.requires` names it, and a file
 *               matched by `apply.tracks` has a checked task (the `tracks` value)
 */
export type StaleSignal = { dependent: string } | { tracks: string };

/**
 * Fork (symphysis, C11): the `stale` verdicts that are a signal, not a gate.
 *
 * A stale verdict gates only until the next step has begun. For an artifact
 * other artifacts `require`, that is when one of them has output; for one that
 * nothing requires but `apply.requires` names, when `apply.tracks` has a
 * checked task (`- [x]`). Past that point the verdict counts as satisfied for
 * dependents, planning completeness and the apply gate, and stays visible as
 * `stale`. An artifact with neither (or a schema without `apply.tracks`) keeps
 * gating. Only `stale` has a window: `mismatch` and `missing` always gate.
 * The window is read from the graph and the apply phase, never from artifact ids.
 */
export function detectStaleSignals(
  graph: ArtifactGraph,
  changeDir: string,
  apply: ApplyPhase | undefined
): Map<string, StaleSignal> {
  const signals = new Map<string, StaleSignal>();
  if (!fs.existsSync(changeDir)) {
    return signals;
  }

  const artifacts = graph.getAllArtifacts();
  let tracksChecked: boolean | undefined;
  for (const artifact of artifacts) {
    if (!artifact.verdict || verdictState(artifact, changeDir) !== 'stale') {
      continue;
    }

    const dependents = artifacts.filter((a) => a.requires.includes(artifact.id));
    if (dependents.length > 0) {
      const begun = dependents.find((a) => artifactOutputExists(changeDir, a.generates));
      if (begun) {
        signals.set(artifact.id, { dependent: begun.id });
      }
      continue;
    }

    if (apply?.tracks && apply.requires.includes(artifact.id)) {
      tracksChecked ??= hasCheckedTask(changeDir, apply.tracks);
      if (tracksChecked) {
        signals.set(artifact.id, { tracks: apply.tracks });
      }
    }
  }

  return signals;
}

/**
 * Fork (symphysis, C11): whether a file matched by `apply.tracks` has a checked
 * task, read with the parser apply and archive count progress with. A file
 * that cannot be read counts as none - the window stays open.
 */
function hasCheckedTask(changeDir: string, tracks: string): boolean {
  let files: string[];
  try {
    files = resolveArtifactOutputs(changeDir, tracks);
  } catch {
    return false;
  }
  return files.some((file) => {
    try {
      return parseTaskLines(fs.readFileSync(file, 'utf-8')).some((task) => task.done);
    } catch {
      return false;
    }
  });
}

/**
 * Checks if an artifact is complete by checking if its generated file(s) exist.
 * Supports both simple paths and glob patterns.
 */
function isArtifactComplete(generates: string, changeDir: string): boolean {
  return artifactOutputExists(changeDir, generates);
}

/**
 * State of an artifact's verdict (fork, symphysis C2, C7):
 * - `n/a`      the artifact declares no `verdict`
 * - `missing`  no output file, or no frontmatter / verdict key in it
 * - `mismatch` the key is present but its value (compared as a string) differs
 * - `stale`    the value is the declared one, but a target hash the file declares
 *              no longer holds (see `staleVerdictTarget`)
 * - `ok`       the value is the declared one and every declared target hash holds
 */
export function verdictState(artifact: Artifact, changeDir: string): 'n/a' | VerdictStatus {
  return inspectVerdict(artifact, changeDir).state;
}

/**
 * Fork (symphysis, C7): the target that makes a verdict `stale`.
 * - `changed`   the file's SHA-256 differs from the declared one, or the file is gone
 * - `outside`   the path is absolute or leaves the change directory; the file is not read
 * - `malformed` a hash without a path, or a target without a sha256; `path` then
 *               names the frontmatter field (`target`, `targets`, `targets[<i>]`)
 */
export interface StaleTarget {
  path: string;
  reason: 'changed' | 'outside' | 'malformed';
}

/**
 * Fork (symphysis, C7): the first declared target that makes the verdict
 * `stale`, or undefined when the verdict is not `stale`.
 */
export function staleVerdictTarget(artifact: Artifact, changeDir: string): StaleTarget | undefined {
  return inspectVerdict(artifact, changeDir).staleTarget;
}

function inspectVerdict(
  artifact: Artifact,
  changeDir: string
): { state: 'n/a' | VerdictStatus; staleTarget?: StaleTarget } {
  const verdict = artifact.verdict;
  if (!verdict) {
    return { state: 'n/a' };
  }

  const outputPath = resolveArtifactOutputPath(changeDir, artifact.generates);
  try {
    if (!fs.statSync(outputPath).isFile()) {
      return { state: 'missing' };
    }
  } catch {
    return { state: 'missing' };
  }

  const frontmatter = readFrontmatter(outputPath);
  if (!frontmatter || !Object.hasOwn(frontmatter, verdict.frontmatter)) {
    return { state: 'missing' };
  }

  // Hashes are checked only behind the declared value: a verdict that does not
  // pass is a mismatch whatever its targets say.
  if (String(frontmatter[verdict.frontmatter]) !== verdict.value) {
    return { state: 'mismatch' };
  }

  const staleTarget = findStaleTarget(frontmatter, changeDir);
  return staleTarget ? { state: 'stale', staleTarget } : { state: 'ok' };
}

type DeclaredTarget = { path: string; sha256: string } | { malformed: string };

/**
 * Fork (symphysis, C7): the hash targets a verdict file declares - `target`
 * with `target_sha256`, then each `targets` entry `{path, sha256}`. A `target`
 * without `target_sha256` declares no hash and is not checked; no hash fields
 * at all means no check.
 */
function declaredTargets(frontmatter: Record<string, unknown>): DeclaredTarget[] {
  const targets: DeclaredTarget[] = [];

  if (Object.hasOwn(frontmatter, 'target_sha256')) {
    const targetPath = frontmatter.target;
    const sha256 = frontmatter.target_sha256;
    targets.push(
      isNonEmptyString(targetPath) && isNonEmptyString(sha256)
        ? { path: targetPath, sha256 }
        : { malformed: 'target' }
    );
  }

  if (Object.hasOwn(frontmatter, 'targets')) {
    const list = frontmatter.targets;
    if (!Array.isArray(list)) {
      targets.push({ malformed: 'targets' });
    } else {
      list.forEach((entry: unknown, index) => {
        const record =
          entry !== null && typeof entry === 'object' ? (entry as Record<string, unknown>) : {};
        targets.push(
          isNonEmptyString(record.path) && isNonEmptyString(record.sha256)
            ? { path: record.path, sha256: record.sha256 }
            : { malformed: `targets[${index}]` }
        );
      });
    }
  }

  return targets;
}

function findStaleTarget(
  frontmatter: Record<string, unknown>,
  changeDir: string
): StaleTarget | undefined {
  for (const target of declaredTargets(frontmatter)) {
    if ('malformed' in target) {
      return { path: target.malformed, reason: 'malformed' };
    }
    const stale = checkTarget(target.path, target.sha256, changeDir);
    if (stale) {
      return stale;
    }
  }
  return undefined;
}

/**
 * Compares the SHA-256 of a target's raw bytes (what `sha256sum` prints) with
 * the declared one, case-insensitively. The path is relative to the change
 * directory: one that is absolute, leaves the directory after normalization or
 * reaches outside it through a link is `outside` and is never read.
 */
function checkTarget(declaredPath: string, sha256: string, changeDir: string): StaleTarget | undefined {
  const normalized = path.posix.normalize(FileSystemUtils.toPosixPath(declaredPath));
  const isAbsolute =
    path.posix.isAbsolute(normalized) ||
    path.win32.isAbsolute(declaredPath) ||
    /^[A-Za-z]:/u.test(declaredPath);
  const escapes = normalized === '..' || normalized.startsWith('../');
  if (isAbsolute || escapes || declaredPath.includes('\0')) {
    return { path: declaredPath, reason: 'outside' };
  }

  const targetPath = path.join(changeDir, normalized);
  try {
    FileSystemUtils.assertPathWithin(changeDir, targetPath);
  } catch {
    return { path: declaredPath, reason: 'outside' };
  }

  let actual: string;
  try {
    actual = createHash('sha256').update(fs.readFileSync(targetPath)).digest('hex');
  } catch {
    return { path: declaredPath, reason: 'changed' };
  }

  return actual === sha256.toLowerCase() ? undefined : { path: declaredPath, reason: 'changed' };
}

function isNonEmptyString(value: unknown): value is string {
  return typeof value === 'string' && value.length > 0;
}
