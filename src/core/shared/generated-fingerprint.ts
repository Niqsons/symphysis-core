import { createHash } from 'crypto';
import { RELEASED_GENERATED_FINGERPRINTS } from './released-generated-fingerprints.js';
import { findMarkerBlock } from '../../utils/file-system.js';

const GENERATED_VERSION =
  /^(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)(?:-(?:(?:0|[1-9]\d*|\d*[A-Za-z-][0-9A-Za-z-]*)(?:\.(?:0|[1-9]\d*|\d*[A-Za-z-][0-9A-Za-z-]*))*))?(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$/;

/**
 * Normalizes checkout line endings, a BOM, and a valid generated version
 * inside the YAML frontmatter: the parts of a generated file that change
 * between releases or checkouts without anyone editing it. Free-form
 * `generatedBy` text remains material.
 */
export function normalizeGeneratedContent(content: string): string {
  const normalized = content.replace(/^﻿/, '').replace(/\r\n/g, '\n');
  const frontmatter = normalized.match(/^---\n[\s\S]*?\n---(?:\n|$)/)?.[0];
  if (!frontmatter) return normalized;

  // `[ \t]` rather than `\s` so a leading/trailing whitespace run can never
  // cross a newline: an `m`-anchored `\s*` re-scans from every line start,
  // which is quadratic on a whitespace-heavy frontmatter. YAML indentation is
  // spaces and tabs only, so matching is unchanged.
  const versionLine =
    /^([ \t]*generatedBy:[ \t]*)(?:"([^"\n]+)"|'([^'\n]+)'|([^\s"'#]+))[ \t]*$/m;
  const normalizedFrontmatter = frontmatter.replace(
    versionLine,
    (
      line: string,
      prefix: string,
      doubleQuoted: string | undefined,
      singleQuoted: string | undefined,
      bare: string | undefined
    ) => {
      const version = doubleQuoted ?? singleQuoted ?? bare;
      return version && GENERATED_VERSION.test(version)
        ? `${prefix}"<generated-version>"`
        : line;
    }
  );
  return normalizedFrontmatter + normalized.slice(frontmatter.length);
}

/** Short content fingerprint of a generated file, after normalization. */
export function fingerprintGeneratedContent(content: string): string {
  return createHash('sha256')
    .update(normalizeGeneratedContent(content), 'utf8')
    .digest('hex')
    .slice(0, 16);
}

const BLOCK_START = '<!-- OPENSPEC:START -->';
const BLOCK_END = '<!-- OPENSPEC:END -->';

/**
 * The OpenSpec-managed block of a file older releases added it to (a user's
 * CLAUDE.md or AGENTS.md), markers included, or undefined when there is none.
 * Found by the same own-line marker rules legacy cleanup removes it by.
 */
export function extractOpenSpecBlock(content: string): string | undefined {
  return findMarkerBlock(content.replace(/\r\n/g, '\n'), BLOCK_START, BLOCK_END);
}

const RELEASED = new Set<string>([
  ...RELEASED_GENERATED_FINGERPRINTS,
  // Additional output of 1.16.1+symphysis.9 for Claude Code, Codex and OpenCode.
  // Captured across core, all, and former default profiles and all delivery modes.
  '01ad2e590cff600f', '104aed9c88930241', '1183508b31ec4b20', '1a5bba620fd6eb46',
  '2c3f937411f08124', '317effa8eced67b5', '364f390640811f23', '4081d606a1e38f95',
  '4a6575827b0126a0', '4c1a948f8bdd4fd5', '4c49b5d0fd8b1f78', '5aadd7aebc401a18',
  '5b917f1595a0e61c', '5ef9bc34f61e1383', '6140afd162ec10ef', '7916f433280b3261',
  '87d82dc32ee8ec7f', '88d70ca56e4324ef', '8a43919e90dc76f3', '95ba7f89d1b8aa45',
  '97090164e0f7da2c', '978d3bbccbe1e9d7', '97a13ca03acc6d3e', '9a7296503cd3996a',
  'adf3141a0065cf0c', 'ae989bf0da9b0678', 'caa0670e9482ddbe', 'd74eff25f4d34fce',
  'd78e196ad99fac12', 'da2330642c1181f3', 'f3df50fcc29dfe0b', 'f6d05fa3ce6d789a',
  'f6e61c3a56b9e323', 'f97f810a5282e76b', 'faadf0a5c6024391', 'ffc5624d8c823c9c',
]);

/**
 * Whether `content` is, after normalization, a file some released OpenSpec
 * version generated. Such a file was never edited by a user, so an upgrade
 * may remove or replace it without losing anything.
 */
export function isReleasedGeneratedContent(content: string): boolean {
  return RELEASED.has(fingerprintGeneratedContent(content));
}

/**
 * Whether the file's OpenSpec block is exactly one a released version wrote,
 * so removing the block cannot drop anything the user typed inside it.
 */
export function hasReleasedOpenSpecBlock(content: string): boolean {
  const block = extractOpenSpecBlock(content);
  return block !== undefined && isReleasedGeneratedContent(block);
}
