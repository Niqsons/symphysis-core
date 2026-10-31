// Fork (symphysis, C4): an artifact whose schema entry declares a verdict reads
// `done` only once its frontmatter carries the right value (C2/C3). When such an
// artifact has `verdict: "mismatch"`, or `verdict: "missing"` while its file
// already exists, `continue` must produce the verdict - not rewrite the file and
// not move on to the next artifact. `"missing"` also covers a file that does not
// exist yet; that artifact is created by the ordinary ready branch. Skill and
// slash-command variants carry the step word for word.

import { describe, expect, it } from 'vitest';

import {
  getContinueChangeSkillTemplate,
  getOpsxContinueCommandTemplate,
} from '../../../src/core/templates/skill-templates.js';
import { NAMED_ARTIFACT, VERDICT_CHECK } from '../../../src/core/templates/workflows/continue-change.js';

const VARIANTS: Array<[label: string, text: string]> = [
  ['continue skill', getContinueChangeSkillTemplate().instructions],
  ['continue command', getOpsxContinueCommandTemplate().content],
];

const occurrences = (text: string, needle: string) => text.split(needle).length - 1;

describe('continue template: verdict step', () => {
  it('continue skill and command carry the verdict step before artifact creation', () => {
    for (const text of [
      getContinueChangeSkillTemplate().instructions,
      getOpsxContinueCommandTemplate().content,
    ]) {
      expect(text).toContain('verdict: "missing"');
      expect(text.indexOf('verdict: "missing"')).toBeLessThan(
        text.indexOf('If artifacts are ready to create')
      );
    }
  });

  it.each(VARIANTS)('%s: states the VERDICT_CHECK block exactly once', (_label, text) => {
    expect(occurrences(text, VERDICT_CHECK)).toBe(1);
  });

  it.each(VARIANTS)(
    '%s: places the verdict step after the partial-artifact check and before completion',
    (_label, text) => {
      const partialAt = text.indexOf('**Before anything else, finish a partly written artifact**');
      const verdictAt = text.indexOf(VERDICT_CHECK);
      const completeAt = text.indexOf('**If all planning artifacts are complete');
      const readyAt = text.indexOf('**If artifacts are ready to create**');

      expect(partialAt).toBeGreaterThanOrEqual(0);
      expect(verdictAt).toBeGreaterThan(partialAt);
      expect(completeAt).toBeGreaterThan(verdictAt);
      expect(readyAt).toBeGreaterThan(completeAt);

      // Same `---` separators as the neighbouring blocks.
      expect(text.slice(0, verdictAt).endsWith('\n   ---\n\n   ')).toBe(true);
      expect(text.slice(verdictAt + VERDICT_CHECK.length)).toMatch(/^\n\n   ---\n\n   \*\*If all planning/);
    }
  );

  it.each(VARIANTS)('%s: never rewrites the existing file and stops after the verdict', (_label, text) => {
    expect(text).toContain('non-empty)**: do NOT rewrite the file. Get its instructions');
    expect(text).toContain(
      'the instruction names the attack skill that writes `status: passed` or `status: gaps_found` into the file\'s frontmatter'
    );
    expect(text).toContain('confirm the artifact now shows `verdict: "ok"` (and `status: "done"`)');
    expect(text).toContain(
      'if it shows `gaps_found`, report the gaps to the user and STOP'
    );
    expect(text).toContain("This counts as this invocation's ONE artifact \u2014 STOP after it.");
  });

  // `verdict: "missing"` is also what C3 reports for a verdict artifact whose
  // file does not exist yet. That artifact must still be created by the ordinary
  // ready branch, so the verdict step keys on an existing output file.
  it.each(VARIANTS)(
    '%s: the verdict step applies only to an existing file and leaves a new artifact to the ordinary branch',
    (_label, text) => {
      const condition =
        'carries `verdict: "mismatch"`, `verdict: "stale"`, or `verdict: "missing"` while its file already exists (`artifactPaths.<artifact-id>.existingOutputPaths` in the status output is non-empty)**';
      const fallback =
        'A verdict artifact with `verdict: "missing"` and no existing file is created like any other ready artifact (its instruction writes the file with its frontmatter) \u2014 the ordinary branch below applies.';
      const blockStart = text.indexOf('**If the first artifact with `status: "ready"`');
      const blockEnd = text.indexOf('**If all planning artifacts are complete');

      for (const needle of [condition, fallback]) {
        expect(occurrences(text, needle)).toBe(1);
        expect(text.indexOf(needle)).toBeGreaterThan(blockStart);
        expect(text.indexOf(needle)).toBeLessThan(blockEnd);
      }
      // The fallback closes the block.
      expect(text.indexOf(fallback) + fallback.length).toBe(
        text.indexOf(VERDICT_CHECK) + VERDICT_CHECK.length
      );
      // The bare `verdict: "missing"` trigger of the first draft is gone.
      expect(text).not.toContain('or `verdict: "missing"`**');
      expect(text).not.toContain('its file already exists; do NOT rewrite it');
    }
  );

  it.each(VARIANTS)('%s: documents the verdict field of status --json', (_label, text) => {
    const bullet =
      '- `verdict` on an artifact: present only when its schema entry declares a verdict; `"ok"`, `"missing"` (file or frontmatter value absent), `"mismatch"` (wrong value) or `"stale"` (a target changed since the verdict)';
    expect(occurrences(text, bullet)).toBe(1);
    expect(text.indexOf(bullet)).toBeGreaterThan(text.indexOf('- `artifacts`: Array of artifacts'));
    expect(text.indexOf(bullet)).toBeLessThan(text.indexOf('- `isPlanningComplete`'));
  });

  it.each(VARIANTS)('%s: the ready-artifact step defers to the verdict step', (_label, text) => {
    const deferral =
      '(if it carries `verdict: "mismatch"`, `verdict: "stale"`, or `verdict: "missing"` with an existing file, the verdict step above applies instead)';
    expect(occurrences(text, deferral)).toBe(1);
    expect(text).not.toContain('a verdict other than "ok"');
    expect(text.indexOf(deferral)).toBeGreaterThan(text.indexOf('**If artifacts are ready to create**'));
  });

  it('VERDICT_CHECK treats stale like mismatch: no blind rewrite, instruction run again', () => {
    expect(VERDICT_CHECK).toContain('`verdict: "stale"`');
    expect(VERDICT_CHECK).toContain('stale');
    expect(VERDICT_CHECK).toMatch(/stale[^.]*run the artifact's instruction again/);
  });
});

// Fork (symphysis, C8): `/opsx:continue <change> [<artifact-id>]` - four rules.
describe('continue template: artifact named by the caller', () => {
  it.each(VARIANTS)('%s: states the NAMED_ARTIFACT block exactly once', (_label, text) => {
    expect(occurrences(text, NAMED_ARTIFACT)).toBe(1);
  });

  it.each(VARIANTS)('%s: (a) input takes an optional second argument, the artifact id', (_label, text) => {
    expect(text).toContain('/opsx:continue <change> [<artifact-id>]');
    expect(text).toContain('second argument is optional');
  });

  it.each(VARIANTS)('%s: (b) exact match against ids, refusal lists ids and writes nothing', (_label, text) => {
    expect(text).toContain('exactly - case and hyphens included');
    expect(text).toContain('list every artifact `id`, write no file');
    expect(text).toContain('do NOT pick a similar artifact');
  });

  it.each(VARIANTS)('%s: (c) blocked, valid verdict, stale/mismatch and ready branches', (_label, text) => {
    expect(text).toContain('name its `missingDeps` and STOP');
    expect(text).toContain('the verdict is valid');
    expect(text).toContain('do NOT rewrite the file');
    expect(text).toContain('only for the rows not passed');
    expect(text).toContain('`verdict: "mismatch"`, `"stale"`, or `"missing"` with an existing file');
    expect(text).toContain('create it from its instructions');
    expect(text).toContain("the ONLY artifact of this invocation");
  });

  it.each(VARIANTS)('%s: (d) without a name optional artifacts are skipped', (_label, text) => {
    expect(text).toContain('Without a name, skip artifacts with `optional: true`');
    const pick = text.slice(text.indexOf('**If artifacts are ready to create**'));
    expect(pick).toContain('without `optional: true`');
  });

  it.each(VARIANTS)('%s: named step comes before the partial-artifact check', (_label, text) => {
    expect(text.indexOf(NAMED_ARTIFACT)).toBeGreaterThan(text.indexOf('3. **Act based on status**'));
    expect(text.indexOf(NAMED_ARTIFACT)).toBeLessThan(
      text.indexOf('**Before anything else, finish a partly written artifact**')
    );
  });

  it.each(VARIANTS)('%s: status bullets name optional and fileExists', (_label, text) => {
    expect(text).toContain('`optional: true`');
    expect(text).toContain('`fileExists`');
  });
});
