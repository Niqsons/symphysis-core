// Fork (symphysis, C9): `apply` tells the user which optional artifacts were
// never invoked, and follows the CLI `instruction` when blocked only by a
// verdict. Skill and slash command share one text (getApplyInstructions).

import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import { describe, expect, it } from 'vitest';

import {
  getApplyChangeSkillTemplate,
  getOpsxApplyCommandTemplate,
} from '../../../src/core/templates/skill-templates.js';
import { STALE_SIGNAL, UNINVOKED_OPTIONAL } from '../../../src/core/templates/workflows/apply-change.js';

const VARIANTS: Array<[label: string, text: string]> = [
  ['apply skill', getApplyChangeSkillTemplate().instructions],
  ['apply command', getOpsxApplyCommandTemplate().content],
];

const occurrences = (text: string, needle: string) => text.split(needle).length - 1;

describe('apply template: uninvoked optional artifacts', () => {
  it.each(VARIANTS)('%s: states the UNINVOKED_OPTIONAL block exactly once', (_label, text) => {
    expect(occurrences(text, UNINVOKED_OPTIONAL)).toBe(1);
  });

  it.each(VARIANTS)('%s: says the line verbatim before work and does not stop', (_label, text) => {
    expect(text).toContain('атаки не вызывались: <id, id, ...>');
    expect(text).toContain('`optional: true` and `fileExists: false`');
    expect(text).toContain('in schema order');
    expect(text).toContain('a signal, not a stop');
    expect(text.indexOf('атаки не вызывались:')).toBeLessThan(text.indexOf('3. **Get apply instructions**'));
  });

  it.each(VARIANTS)('%s: blocked only by a verdict - follow instruction, do not recreate', (_label, text) => {
    expect(text).toContain('`artifactsWithoutPassingVerdict`');
    expect(text).toContain('follow the `instruction` field');
    expect(text).toContain('do NOT recreate the file');
    expect(text.indexOf('`artifactsWithoutPassingVerdict` is non-empty')).toBeLessThan(
      text.indexOf('Otherwise, follow the CLI instruction to create or repair')
    );
  });

  // Fork (symphysis, C11): a stale verdict past its window is told, not obeyed.
  it.each(VARIANTS)('%s: a stale verdict past its window is a signal before work', (_label, text) => {
    expect(occurrences(text, STALE_SIGNAL)).toBe(1);
    expect(STALE_SIGNAL).toContain('`status: "done"` and `verdict: "stale"`');
    expect(STALE_SIGNAL).toContain('This is a signal, not a stop: the verdict no longer gates apply');
    expect(text.indexOf(STALE_SIGNAL)).toBeGreaterThan(text.indexOf(UNINVOKED_OPTIONAL));
    expect(text.indexOf(STALE_SIGNAL)).toBeLessThan(text.indexOf('3. **Get apply instructions**'));
  });

  it('generated SKILL.md carries the line', () => {
    const here = path.dirname(fileURLToPath(import.meta.url));
    const skill = readFileSync(
      path.join(here, '../../../skills/openspec-apply-change/SKILL.md'),
      'utf-8'
    );
    expect(skill).toContain('атаки не вызывались: <id, id, ...>');
    expect(skill).toContain('`artifactsWithoutPassingVerdict`');
    expect(skill).toContain('Stale verdicts past their window');
  });
});
