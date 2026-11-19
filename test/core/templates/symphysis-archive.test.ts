import { describe, expect, it } from 'vitest';
import { getArchiveChangeSkillTemplate, getOpsxArchiveCommandTemplate } from '../../../src/core/templates/workflows/archive-change.js';

const variants = [
  ['skill', getArchiveChangeSkillTemplate().instructions],
  ['command', getOpsxArchiveCommandTemplate().content],
] as const;

describe.each(variants)('Symphysis archive result protocol: %s', (_, content) => {
  it('prepares the graph after path resolution and before assessment, even without guidance', () => {
    const root = content.indexOf('**Check artifact completion status**');
    const prepare = content.indexOf('**Symphysis archive preparation:**');
    const assess = content.indexOf('**Assess delta spec sync state**');
    expect(prepare).toBeGreaterThan(root);
    expect(assess).toBeGreaterThan(prepare);
    expect(content.slice(prepare, assess)).toContain('does not depend on the optional archive-input lookup');
    expect(content.slice(prepare, assess)).toContain('working directory to `planningHome.root`');
    expect(content.slice(prepare, assess)).toContain('A graph error alone is not a sync or archive gate');
  });

  it('preserves the explicit no-sync route without master writes', () => {
    expect(content).toContain('"Archive without syncing" MUST leave all main specs untouched');
    expect(content).toContain('skip anchoring and post-sync verification');
    expect(content).toContain('"Archive without syncing" — proceed to archive without writing main specs');
  });

  it('verifies an already-synced change instead of jumping straight to the move', () => {
    expect(content).toContain('complete the already-synced result review below before step 5');
    expect(content).toContain('"Archive now" only checks the already-synced state');
    expect(content).toContain('a late freeze of an anchored master does not prove the old origin');
  });

  it('checks the completed scoped sync before moving, keeping review distinct from mismatch', () => {
    const verify = content.indexOf('**Finish a requested Symphysis sync before moving the directory:**');
    const move = content.indexOf('**Perform the archive**');
    expect(verify).toBeGreaterThan(content.indexOf('If the sync reports any stop or blocking condition'));
    expect(move).toBeGreaterThan(verify);
    const body = content.slice(verify, move);
    expect(body).toContain('sync_check.py');
    expect(body).toContain('`mismatch`: show the findings and stop');
    expect(body).toContain('`review`: resolve each finding');
    expect(body).toContain('not an automatic success or failure');
    expect(body).toContain('same planning root, change and exact capability scope');
    expect(body).toContain('Never strip arbitrary journal prefixes');
    expect(body).toContain('you MUST reuse that result and its review conclusions');
    expect(body).toContain('A pre-sync assessment result cannot be reused after a master write');
    expect(body).toContain('An absent, malformed, failed or differently scoped result is not a receipt');
  });
});
