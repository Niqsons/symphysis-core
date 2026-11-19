import * as fs from 'node:fs';
import { parse as parseYaml } from 'yaml';

const FENCE = '---';

/**
 * Fork (symphysis, C2): reads the YAML frontmatter block of a markdown file.
 *
 * The block runs from a first-line `---` to the next line that is exactly
 * `---`. A leading BOM is dropped and both CRLF and LF line endings are
 * accepted. Returns null - never throws - when the file is unreadable, has no
 * opening fence on its first line, has no closing fence, holds an empty block,
 * or the block is not valid YAML describing a mapping.
 */
export function readFrontmatter(filePath: string): Record<string, unknown> | null {
  const lines = readFrontmatterLines(filePath);
  if (!lines) {
    return null;
  }
  const block = lines.join('\n');
  if (block.trim() === '') {
    return null;
  }

  let parsed: unknown;
  try {
    parsed = parseYaml(block);
  } catch {
    return null;
  }

  if (parsed === null || typeof parsed !== 'object' || Array.isArray(parsed)) {
    return null;
  }
  return parsed as Record<string, unknown>;
}

/** Reads a dedicated top-level field without letting malformed YAML hide it. */
export function readRawFrontmatterField(
  filePath: string,
  key: string,
  options: { includeIndented?: boolean } = {}
): Array<{ value: string; canonical: boolean }> {
  return (readFrontmatterLines(filePath) ?? []).flatMap((line, index, lines) => {
    const field = /^([^\s:#][^:]*?)\s*:\s*(.*)$/u.exec(options.includeIndented ? line.trimStart() : line);
    if (!field) return [];
    let name: unknown = field[1];
    if (name !== key) {
      try {
        name = parseYaml(field[1]);
      } catch {
        return [];
      }
    }
    const continuation = options.includeIndented && /^[ \t]+\S/u.test(lines[index + 1] ?? '');
    return name === key ? [{ value: field[2], canonical: line.startsWith(`${key}:`) && !continuation }] : [];
  });
}

/** Recovers one isolated verdict value when the declared support field breaks YAML. */
export function readFrontmatterValue(filePath: string, key: string): unknown {
  const fields = readRawFrontmatterField(filePath, key);
  if (fields.length !== 1) return undefined;
  try {
    return parseYaml(fields[0].value);
  } catch {
    return undefined;
  }
}

function readFrontmatterLines(filePath: string): string[] | null {
  let content: string;
  try {
    content = fs.readFileSync(filePath, 'utf-8');
  } catch {
    return null;
  }

  if (content.charCodeAt(0) === 0xfeff) {
    content = content.slice(1);
  }

  const lines = content.split('\n').map((line) => line.replace(/\r$/, ''));
  if (lines[0] !== FENCE) {
    return null;
  }

  const closing = lines.indexOf(FENCE, 1);
  if (closing === -1) {
    return null;
  }

  return lines.slice(1, closing);
}
