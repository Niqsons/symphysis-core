import { createHash } from 'node:crypto';
import * as fs from 'node:fs';
import * as path from 'node:path';
import { parse as parseYaml } from 'yaml';
import { FileSystemUtils } from '../../utils/file-system.js';
import { readFrontmatter, readRawFrontmatterField } from './frontmatter.js';

export type MasterSupportReason = 'changed' | 'invalid' | 'outside' | 'missing' | 'unreadable' | 'ambiguous';
export interface MasterSupportFailure {
  path: string;
  scope: 'master';
  reason: MasterSupportReason;
}

interface Support {
  capability: string;
  requirement: string;
  scenario?: string;
  sha256: string;
}

/** Identifiers are untrusted data; diagnostics disclose only a one-based field index. */
export function inspectMasterSupports(
  reportPath: string,
  planningRoot?: string
): { declared: boolean; staleTarget?: MasterSupportFailure } {
  const fields = readRawFrontmatterField(reportPath, 'master_supports', { includeIndented: true });
  const failure = (reason: MasterSupportReason, index = 0) => ({
    declared: true,
    staleTarget: { path: `master_supports[${index + 1}]`, scope: 'master' as const, reason },
  });
  if (fields.length === 0) {
    return Object.hasOwn(readFrontmatter(reportPath) ?? {}, 'master_supports')
      ? failure('invalid') : { declared: false };
  }
  if (fields.length !== 1) return failure('ambiguous');
  if (!fields[0].canonical) return failure('invalid');
  let entries: unknown;
  try {
    entries = JSON.parse(fields[0].value);
    // YAML's JSON-compatible parser rejects duplicate object keys, which
    // JSON.parse otherwise silently overwrites (including escaped key aliases).
    parseYaml(fields[0].value);
  } catch {
    return failure('invalid');
  }
  if (!Array.isArray(entries)) return failure('invalid');
  const identities = new Set<string>();
  for (let index = 0; index < entries.length; index++) {
    const support = entries[index];
    if (!isSupport(support)) return failure('invalid', index);
    for (const identifier of [support.capability, support.requirement, support.scenario]) {
      if (identifier === undefined) continue;
      if (path.posix.isAbsolute(identifier) || path.win32.isAbsolute(identifier) || /^[A-Za-z]:/u.test(identifier) || identifier.split(/[/\\]/u).includes('..')) return failure('outside', index);
    }
    const capability = FileSystemUtils.toPosixPath(support.capability);
    if (capability.split('/').some((part) => !/^[A-Za-z\d][A-Za-z\d._-]*$/u.test(part))) return failure('outside', index);
    const identity = JSON.stringify([capability, support.requirement, support.scenario]);
    if (identities.has(identity)) return failure('ambiguous', index);
    identities.add(identity);
  }
  for (let index = 0; index < entries.length; index++) {
    const support = entries[index] as Support;
    const reason = checkSupport(support, planningRoot);
    if (reason) return failure(reason, index);
  }
  return { declared: true };
}

function isSupport(entry: unknown): entry is Support {
  if (entry === null || typeof entry !== 'object' || Array.isArray(entry)) return false;
  const value = entry as Record<string, unknown>;
  const named = (key: string): boolean => typeof value[key] === 'string' &&
    value[key].length > 0 && value[key] === value[key].trim() && !/[\x00-\x1f\x7f-\x9f\u2028\u2029]/u.test(value[key]);
  if (Object.keys(value).some((key) => !['capability', 'requirement', 'scenario', 'sha256'].includes(key))) return false;
  return named('capability') && named('requirement') &&
    (!Object.hasOwn(value, 'scenario') || named('scenario')) &&
    typeof value.sha256 === 'string' && /^[a-f\d]{64}$/iu.test(value.sha256);
}

function checkSupport(support: Support, planningRoot?: string): MasterSupportReason | undefined {
  const capability = FileSystemUtils.toPosixPath(support.capability);
  if (!planningRoot) return 'invalid';
  const specsDir = path.join(planningRoot, 'openspec', 'specs');
  const specPath = path.join(specsDir, capability, 'spec.md');
  try {
    // The directory itself must not escape the trusted root through a link.
    FileSystemUtils.assertPathWithin(planningRoot, specsDir);
    FileSystemUtils.assertPathWithin(specsDir, specPath);
    if (FileSystemUtils.canonicalizeExistingPath(planningRoot) === FileSystemUtils.canonicalizeExistingPath(specsDir)) return 'outside';
  } catch {
    return 'outside';
  }
  let bytes: Buffer;
  try {
    bytes = fs.readFileSync(specPath);
  } catch (error) {
    return ['ENOENT', 'ENOTDIR'].includes((error as NodeJS.ErrnoException).code ?? '') ? 'missing' : 'unreadable';
  }
  let content: string;
  try {
    content = new TextDecoder('utf-8', { fatal: true }).decode(bytes).replace(/\r\n?/gu, '\n');
  } catch {
    return 'unreadable';
  }
  const block = masterBlock(content, support.requirement, support.scenario);
  if ('reason' in block) return block.reason;
  return createHash('sha256').update(block.content).digest('hex') === support.sha256.toLowerCase()
    ? undefined : 'changed';
}

interface Heading { start: number; end: number; level: number; name: string; requirement?: string }

/** Selects raw markdown by structural headings, ignoring headings inside fenced code. */
function masterBlock(content: string, requirement: string, scenario?: string):
  { content: string } | { reason: MasterSupportReason } {
  const headings: Heading[] = [];
  let fence: { character: string; length: number; start: number } | undefined;
  let offset = 0;
  for (const raw of content.split(/(?<=\n)/u)) {
    const line = raw.replace(/\n$/u, '');
    const marker = /^\s*(`{3,}|~{3,})(.*)$/u.exec(line);
    if (fence) {
      if (marker && marker[1][0] === fence.character && marker[1].length >= fence.length && marker[2].trim() === '') fence = undefined;
    } else if (marker && !(marker[1][0] === '`' && marker[2].includes('`'))) {
      fence = { character: marker[1][0], length: marker[1].length, start: offset };
    } else {
      const heading = /^(#{1,6})\s+(.+)$/u.exec(line);
      const req = /^###\s*Requirement:\s*(.+)\s*$/iu.exec(line);
      if (heading || req) {
        const level = req ? 3 : heading![1].length;
        const name = (req ? req[1] : heading![2]).replace(/[ \t]+#+[ \t]*$/u, '').trim();
        headings.push({ start: offset, end: offset + raw.length, level, name, ...(req ? { requirement: name } : {}) });
      }
    }
    offset += raw.length;
  }
  const sections = headings.filter((heading) => heading.level === 2 && heading.name.toLowerCase() === 'requirements');
  if (sections.length !== 1) return { reason: sections.length ? 'ambiguous' : 'invalid' };
  const section = sections[0];
  const endOf = (heading: Heading): number => headings.find((candidate) => candidate.start > heading.start && candidate.level <= heading.level)?.start ?? content.length;
  const sectionEnd = endOf(section);
  const requirements = headings.filter((heading) => heading.start > section.start && heading.start < sectionEnd && heading.requirement === requirement);
  if (requirements.length !== 1) return { reason: requirements.length ? 'ambiguous' : 'missing' };
  let selected = requirements[0];
  if (scenario !== undefined) {
    const requirementEnd = endOf(selected);
    const scenarios = headings.filter((heading) => heading.start > selected.start && heading.start < requirementEnd && heading.level === 4 && heading.name.replace(/^Scenario:\s*/iu, '') === scenario);
    if (scenarios.length !== 1) return { reason: scenarios.length ? 'ambiguous' : 'missing' };
    selected = scenarios[0];
  }
  const end = endOf(selected);
  if (content.slice(selected.end, end).trim() === '' || (fence && fence.start >= selected.start && fence.start < end)) return { reason: 'invalid' };
  return { content: content.slice(selected.start, end) };
}
