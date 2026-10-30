import { FileSystemUtils } from '../../utils/file-system.js';

// Fork (symphysis): the glob-pattern predicate lives apart from outputs.ts so the
// schema reader can call it without importing tinyglobby, brace-expansion and
// picomatch (test/cli-e2e/startup-modules.test.ts pins that).

export const EXTGLOB_RE = /[!*+?@]\([^(]*\)/u;
const BRACE_EXPANSION_SEPARATORS_RE = /,|\.\./u;

function hasBraceExpansion(pattern: string): boolean {
  const openings: number[] = [];
  for (let index = 0; index < pattern.length; index += 1) {
    if (pattern[index] === '{') openings.push(index);
    if (pattern[index] !== '}') continue;
    const opening = openings.pop();
    if (opening !== undefined && BRACE_EXPANSION_SEPARATORS_RE.test(pattern.slice(opening, index))) {
      return true;
    }
  }
  return false;
}

/**
 * Recognizes artifact globs while preserving literal output filenames.
 */
export function isGlobPattern(pattern: string): boolean {
  // Keep the original wildcard rules and recognize brace expansions and extglobs.
  // Its full dynamic predicate also reinterprets literal !, parentheses, and backslashes.
  const normalized = FileSystemUtils.toPosixPath(pattern);
  return normalized.includes('*') || normalized.includes('?') || normalized.includes('[')
    || EXTGLOB_RE.test(normalized) || hasBraceExpansion(normalized);
}
