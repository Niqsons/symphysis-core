import { describe, expect, it } from 'vitest';
import { getOpsxSyncCommandTemplate, getSyncSpecsSkillTemplate } from '../../../src/core/templates/workflows/sync-specs.js';

const variants = [
  ['skill', getSyncSpecsSkillTemplate().instructions],
  ['command', getOpsxSyncCommandTemplate().content],
] as const;

describe.each(variants)('Symphysis sync sequencing: %s', (_, content) => {
  it('keeps graph preparation after selection and rule lookup but before any master write', () => {
    const selected = content.indexOf('**Find delta specs**');
    const rules = content.indexOf('Artifact rules are not operation guidance');
    const prepare = content.indexOf('**Preserve the Symphysis base before writing:**');
    const writes = content.indexOf('For each capability delta spec path selected in step 3');
    expect(selected).toBeGreaterThan(-1);
    expect(rules).toBeGreaterThan(selected);
    expect(prepare).toBeGreaterThan(rules);
    expect(writes).toBeGreaterThan(prepare);
    expect(content.slice(prepare, writes)).toContain('schemaName` is exactly `symphysis`');
    expect(content.slice(prepare, writes)).toContain('otherwise skip this block');
  });

  it('uses the selected planning root for Python, not the caller cwd or --store', () => {
    expect(content).toContain('working directory to `planningHome.root`');
    expect(content).toContain('Python tools do not accept `--store`');
    expect(content).toContain('--roots "<toolsHome>/journal-roots.json"');
  });

  it('distinguishes advisory graph failure from a failed sync', () => {
    expect(content).toContain('show the actual error and continue this workflow');
    expect(content).toContain('do not claim a base was saved');
    expect(content).toContain('A graph error alone is not a sync or archive gate');
    expect(content).toContain('If anchoring fails, report sync as failed and stop');
  });

  it('records scoped provenance only for a confirmed first sync before writing', () => {
    const block = content.slice(content.indexOf('**Preserve the Symphysis base before writing:**'),
      content.indexOf('For each capability delta spec path selected in step 3'));
    expect(block).toContain('--confirmed-pre-sync');
    expect(block).toContain('--capability "<selected-capability>"');
    expect(block).toContain('unknown order');
    expect(block).toContain('repeated sync');
    expect(block).toContain('graph command succeeded');
  });

  it('anchors only the selected capabilities after writes and before validation and success', () => {
    const writes = content.indexOf('Follow the **Main Spec Format Reference** below');
    const anchors = content.indexOf('**Anchor the selected Symphysis result before validation:**');
    const validate = content.indexOf('openspec validate --specs');
    const summary = content.indexOf('**Show summary**');
    expect(anchors).toBeGreaterThan(writes);
    expect(validate).toBeGreaterThan(anchors);
    expect(summary).toBeGreaterThan(validate);
    expect(content.slice(anchors, validate)).toContain('--capability "<selected-capability>"');
    expect(content.slice(anchors, validate)).toContain('Never widen that set');
    expect(content).toContain('stop before writing: an unscoped fallback could change excluded capabilities');
  });
});
