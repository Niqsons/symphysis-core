import * as fs from 'node:fs';
import * as os from 'node:os';
import * as path from 'node:path';
import { createHash } from 'node:crypto';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { loadChangeContext, formatChangeStatus } from '../../src/core/artifact-graph/instruction-loader.js';
import { generateApplyInstructions } from '../../src/commands/workflow/instructions.js';
import type { PlanningHome } from '../../src/core/planning-home.js';
import { runCLI } from '../helpers/run-cli.js';

describe('master supports in status and apply', () => {
  let temp: string;
  let project: string;
  let home: PlanningHome;
  let change: string;
  let spec: string;
  const raw = '### Requirement: Stable input\nThe system SHALL preserve input.\n\n#### Scenario: Kept\n- **WHEN** called\n- **THEN** kept\n';
  const digest = createHash('sha256').update(raw).digest('hex');
  const schema = `name: support-flow
version: 1
artifacts:
  - id: tasks
    generates: tasks.md
    description: Tasks
    template: tasks.md
    requires: []
  - id: review
    generates: attack.md
    description: Review
    template: attack.md
    requires: [tasks]
    optional: true
    verdict:
      frontmatter: status
      value: passed
apply:
  requires: [tasks, review]
  tracks: tasks.md
`;
  const status = () => formatChangeStatus(loadChangeContext(project, 'sample', 'support-flow', {
    changeDir: change, planningHome: home,
  }));
  const apply = () => generateApplyInstructions(project, 'sample', 'support-flow', { planningHome: home });

  beforeEach(() => {
    temp = fs.mkdtempSync(path.join(os.tmpdir(), 'openspec-support-workflow-'));
    project = path.join(temp, 'implementation');
    home = { kind: 'repo', root: path.join(temp, 'selected'), changesDir: path.join(temp, 'selected', 'openspec', 'changes'), defaultSchema: 'support-flow' };
    change = path.join(home.changesDir, 'sample');
    spec = path.join(home.root, 'openspec', 'specs', 'shared-input', 'spec.md');
    const schemaDir = path.join(project, 'openspec', 'schemas', 'support-flow');
    fs.mkdirSync(schemaDir, { recursive: true });
    fs.writeFileSync(path.join(schemaDir, 'schema.yaml'), schema);
    fs.mkdirSync(change, { recursive: true });
    fs.mkdirSync(path.dirname(spec), { recursive: true });
    fs.writeFileSync(spec, '# Shared\n\n## Requirements\n\n' + raw);
    fs.writeFileSync(path.join(change, '.openspec.yaml'), 'schema: support-flow\n');
    fs.writeFileSync(path.join(change, 'tasks.md'), '- [ ] 1.1 Work\n- [ ] 1.2 More\n');
    fs.writeFileSync(path.join(change, 'attack.md'), `---\nstatus: passed\nmaster_supports: [{"capability":"shared-input","requirement":"Stable input","sha256":"${digest}"}]\n---\n`);
  });
  afterEach(() => fs.rmSync(temp, { recursive: true, force: true }));

  it('uses the selected planning home rather than the implementation root', async () => {
    expect(status().artifacts.find((artifact) => artifact.id === 'review')).toMatchObject({ status: 'done', verdict: 'ok' });
    expect((await apply()).state).toBe('ready');
  });

  it('gates before a checked task and signals after the first checked task', async () => {
    fs.appendFileSync(spec, '\nChanged support.\n');
    const before = status();
    expect(before.artifacts.find((artifact) => artifact.id === 'review')).toMatchObject({ status: 'ready', verdict: 'stale' });
    expect(before.nextSteps.join('\n')).toContain('master_supports[1] changed since the verdict');
    expect(await apply()).toMatchObject({ state: 'blocked', artifactsWithoutPassingVerdict: [{ id: 'review', verdict: 'stale' }] });
    fs.writeFileSync(path.join(change, 'tasks.md'), '- [x] 1.1 Work\n- [ ] 1.2 More\n');
    const after = status();
    expect(after.artifacts.find((artifact) => artifact.id === 'review')).toMatchObject({ status: 'done', verdict: 'stale' });
    expect(after.nextSteps.join('\n')).toContain('signal, not a gate');
    expect((await apply()).state).toBe('ready');
  });

  it.each(['[broken', '{}'])('keeps malformed declared supports stale through the command surfaces (%s)', async (field) => {
    fs.writeFileSync(path.join(change, 'attack.md'), `---\nstatus: passed\nmaster_supports: ${field}\n---\n`);
    expect(status().artifacts.find((artifact) => artifact.id === 'review')?.verdict).toBe('stale');
    expect(await apply()).toMatchObject({ state: 'blocked', artifactsWithoutPassingVerdict: [{ id: 'review', verdict: 'stale' }] });
  });

  it.each([' master_supports: [broken', 'master_supports: []\n  ignored: payload'])('keeps a malformed declaration layout in the usual stale window (%s)', async (field) => {
    fs.writeFileSync(path.join(change, 'attack.md'), `---\nstatus: passed\n${field}\n---\n`);
    expect(status().artifacts.find((artifact) => artifact.id === 'review')).toMatchObject({ status: 'ready', verdict: 'stale' });
    expect(await apply()).toMatchObject({ state: 'blocked', artifactsWithoutPassingVerdict: [{ id: 'review', verdict: 'stale' }] });
    fs.writeFileSync(path.join(change, 'tasks.md'), '- [x] 1.1 Work\n- [ ] 1.2 More\n');
    expect(status().artifacts.find((artifact) => artifact.id === 'review')).toMatchObject({ status: 'done', verdict: 'stale' });
    expect((await apply()).state).toBe('ready');
  });

  it('runs built status and apply commands against the same master support', async () => {
    fs.mkdirSync(path.join(home.root, 'openspec', 'schemas', 'support-flow'), { recursive: true });
    fs.writeFileSync(path.join(home.root, 'openspec', 'schemas', 'support-flow', 'schema.yaml'), schema);
    fs.writeFileSync(path.join(home.root, 'openspec', 'config.yaml'), 'schema: support-flow\n');
    fs.appendFileSync(spec, '\nChanged support.\n');
    const result = await runCLI(['status', '--change', 'sample', '--json'], { cwd: home.root });
    expect(result.exitCode).toBe(0);
    expect(JSON.parse(result.stdout).artifacts.find((artifact: { id: string }) => artifact.id === 'review')?.verdict).toBe('stale');
    const blocked = await runCLI(['instructions', 'apply', '--change', 'sample', '--json'], { cwd: home.root });
    expect(blocked.exitCode).toBe(0);
    expect(JSON.parse(blocked.stdout)).toMatchObject({ state: 'blocked', artifactsWithoutPassingVerdict: [{ id: 'review', verdict: 'stale' }] });
    fs.writeFileSync(path.join(change, 'tasks.md'), '- [x] 1.1 Work\n- [ ] 1.2 More\n');
    const ready = await runCLI(['instructions', 'apply', '--change', 'sample', '--json'], { cwd: home.root });
    expect(ready.exitCode).toBe(0);
    expect(JSON.parse(ready.stdout).state).toBe('ready');
  });
});
