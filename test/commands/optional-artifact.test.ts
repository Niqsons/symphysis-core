import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { createHash } from 'node:crypto';
import * as fs from 'node:fs';
import * as path from 'node:path';
import * as os from 'node:os';
import {
  generateApplyInstructions,
  instructionsCommand,
  printApplyInstructionsText,
} from '../../src/commands/workflow/instructions.js';

// Fork (symphysis, C7): commands that take an optional artifact as a
// dependency. The apply gate takes `apply.requires` the way a `requires` edge
// does - an optional artifact without a file does not hold apply back; once
// its file exists, apply waits for a passing, fresh verdict.
describe('generateApplyInstructions with an optional verdict artifact', () => {
  let tempDir: string;
  let changeDir: string;

  const sha = (content: string): string => createHash('sha256').update(content).digest('hex');
  const TASKS = '## 1. Work\n\n- [ ] 1.1 Do the work\n';

  function writeSchema(optional: boolean): void {
    const schemaDir = path.join(tempDir, 'openspec', 'schemas', 'review-flow');
    fs.mkdirSync(schemaDir, { recursive: true });
    fs.writeFileSync(
      path.join(schemaDir, 'schema.yaml'),
      [
        'name: review-flow',
        'version: 1',
        'description: tasks behind an optional review',
        'artifacts:',
        '  - id: proposal',
        '    generates: proposal.md',
        '    description: Proposal',
        '    template: proposal.md',
        '    requires: []',
        '  - id: tasks',
        '    generates: tasks.md',
        '    description: Tasks',
        '    template: tasks.md',
        '    requires: [proposal]',
        '  - id: review',
        '    generates: review.md',
        '    description: Review of the tasks',
        '    template: review.md',
        '    requires: [tasks]',
        ...(optional ? ['    optional: true'] : []),
        '    verdict:',
        '      frontmatter: status',
        '      value: passed',
        'apply:',
        '  requires: [tasks, review]',
        '  tracks: tasks.md',
        '',
      ].join('\n')
    );
  }

  function write(file: string, content: string): void {
    fs.writeFileSync(path.join(changeDir, file), content);
  }

  beforeEach(() => {
    tempDir = fs.mkdtempSync(path.join(os.tmpdir(), 'openspec-apply-optional-'));
    changeDir = path.join(tempDir, 'openspec', 'changes', 'my-change');
    fs.mkdirSync(changeDir, { recursive: true });
    write('.openspec.yaml', 'schema: review-flow\n');
    write('proposal.md', '# Proposal\n');
    writeSchema(true);
  });

  afterEach(() => {
    fs.rmSync(tempDir, { recursive: true, force: true });
  });

  it('Планирование без вызванных атак: optional без файла не держит apply', async () => {
    write('tasks.md', TASKS);

    const instructions = await generateApplyInstructions(tempDir, 'my-change');

    expect(instructions.state).toBe('ready');
    expect(instructions.missingArtifacts).toBeUndefined();
  });

  it('Планирование без вызванных атак: optional без файла не входит в недостающие предпосылки', async () => {
    const instructions = await generateApplyInstructions(tempDir, 'my-change');

    expect(instructions.state).toBe('blocked');
    expect(instructions.missingArtifacts).toEqual(['tasks']);
    expect(instructions.missingPrerequisites).toEqual(['tasks']);
  });

  it('Необязательный артефакт с файлом: gaps_found блокирует apply и называет вердикт, а не недостающий файл', async () => {
    write('tasks.md', TASKS);
    write('review.md', '---\nstatus: gaps_found\n---\n# Review\n');

    const instructions = await generateApplyInstructions(tempDir, 'my-change');

    expect(instructions.state).toBe('blocked');
    expect(instructions.missingArtifacts).toBeUndefined();
    expect(instructions.artifactsWithoutPassingVerdict).toEqual([{ id: 'review', verdict: 'mismatch' }]);
    expect(instructions.instruction).toBe(
      'Cannot apply this change yet. Artifacts without a passing verdict: review (verdict: mismatch)' +
        ' — run `openspec instructions review --change my-change` again; do not recreate the file.'
    );
  });

  it('Необязательный артефакт с файлом: passed со свежими хешами открывает apply', async () => {
    write('tasks.md', TASKS);
    write(
      'review.md',
      `---\nstatus: passed\ntargets:\n  - path: tasks.md\n    sha256: ${sha(TASKS)}\n---\n# Review\n`
    );

    const instructions = await generateApplyInstructions(tempDir, 'my-change');

    expect(instructions.state).toBe('ready');
    expect(instructions.missingArtifacts).toBeUndefined();
  });

  it('Вердикт с чужим хешем: stale блокирует apply', async () => {
    write('tasks.md', TASKS);
    write(
      'review.md',
      `---\nstatus: passed\ntargets:\n  - path: tasks.md\n    sha256: ${sha('## 1. Before the edit\n')}\n---\n# Review\n`
    );

    const instructions = await generateApplyInstructions(tempDir, 'my-change');

    expect(instructions.state).toBe('blocked');
    expect(instructions.missingArtifacts).toBeUndefined();
    expect(instructions.artifactsWithoutPassingVerdict).toEqual([{ id: 'review', verdict: 'stale' }]);
    expect(instructions.instruction).toBe(
      'Cannot apply this change yet. Artifacts without a passing verdict: review (verdict: stale)' +
        ' — run `openspec instructions review --change my-change` again; do not recreate the file.'
    );
    expect(instructions.instruction).not.toContain('Create it with');
    expect(instructions.instruction).not.toContain('Not created yet');
  });

  it('Вердикт с чужим хешем: текст apply называет stale в блоке Blocked', async () => {
    write('tasks.md', TASKS);
    write(
      'review.md',
      `---\nstatus: passed\ntargets:\n  - path: tasks.md\n    sha256: ${sha('## 1. Before the edit\n')}\n---\n# Review\n`
    );
    const lines: string[] = [];
    vi.spyOn(console, 'log').mockImplementation((...args: unknown[]) => {
      lines.push(args.join(' '));
    });

    printApplyInstructionsText(await generateApplyInstructions(tempDir, 'my-change'));
    vi.restoreAllMocks();
    const output = lines.join('\n');

    expect(output).toContain('### ⚠️ Blocked');
    expect(output).toContain('Artifacts without a passing verdict: review (verdict: stale)');
    expect(output).not.toContain('Missing artifacts');
    expect(output).not.toContain('Not created yet');
  });

  it('Необязательный артефакт с файлом: недостающий файл и вердикт без ok названы порознь', async () => {
    write('review.md', '---\nstatus: gaps_found\n---\n# Review\n');

    const instructions = await generateApplyInstructions(tempDir, 'my-change');

    expect(instructions.state).toBe('blocked');
    expect(instructions.missingArtifacts).toEqual(['tasks']);
    // review has a file: it is not "not created yet".
    expect(instructions.missingPrerequisites).toEqual(['tasks']);
    expect(instructions.artifactsWithoutPassingVerdict).toEqual([{ id: 'review', verdict: 'mismatch' }]);
    expect(instructions.instruction).toBe(
      'Cannot apply this change yet. Missing artifacts: tasks.\n' +
        'Create it with `openspec instructions tasks --change my-change` (`openspec status --change my-change` shows what is left).\n' +
        'Artifacts without a passing verdict: review (verdict: mismatch)' +
        ' — run `openspec instructions review --change my-change` again; do not recreate the file.'
    );
  });

  it('Файл вызванной атаки удалён: apply снова не ждёт optional', async () => {
    write('tasks.md', TASKS);
    write('review.md', '---\nstatus: gaps_found\n---\n# Review\n');
    expect((await generateApplyInstructions(tempDir, 'my-change')).state).toBe('blocked');

    fs.rmSync(path.join(changeDir, 'review.md'));

    expect((await generateApplyInstructions(tempDir, 'my-change')).state).toBe('ready');
  });

  it('обязательный verdict-артефакт с gaps_found тоже блокирует apply', async () => {
    writeSchema(false);
    write('tasks.md', TASKS);
    write('review.md', '---\nstatus: gaps_found\n---\n# Review\n');

    const instructions = await generateApplyInstructions(tempDir, 'my-change');

    expect(instructions.state).toBe('blocked');
    expect(instructions.missingArtifacts).toBeUndefined();
    expect(instructions.artifactsWithoutPassingVerdict).toEqual([{ id: 'review', verdict: 'mismatch' }]);
  });

  it('обязательный verdict-артефакт без файла остаётся недостающим', async () => {
    writeSchema(false);
    write('tasks.md', TASKS);

    const instructions = await generateApplyInstructions(tempDir, 'my-change');

    expect(instructions.state).toBe('blocked');
    expect(instructions.missingArtifacts).toEqual(['review']);
    expect(instructions.artifactsWithoutPassingVerdict).toBeUndefined();
    expect(instructions.instruction).toContain('Create it with `openspec instructions review --change my-change`');
  });
});

// `openspec instructions <artifact>` for an artifact that requires an optional
// one: without the optional file there is nothing unmet and nothing to read.
describe('instructions command with an optional dependency', () => {
  let tempDir: string;
  let changeDir: string;
  let originalCwd: string;
  let originalConfigHome: string | undefined;
  let lines: string[];

  beforeEach(() => {
    originalCwd = process.cwd();
    originalConfigHome = process.env.XDG_CONFIG_HOME;
    tempDir = fs.realpathSync(fs.mkdtempSync(path.join(os.tmpdir(), 'openspec-optional-dep-')));
    // Keep the developer's real global config (default store, ...) out of root resolution.
    process.env.XDG_CONFIG_HOME = path.join(tempDir, 'xdg-config');

    const schemaDir = path.join(tempDir, 'openspec', 'schemas', 'attack-flow');
    fs.mkdirSync(path.join(schemaDir, 'templates'), { recursive: true });
    for (const name of ['brief', 'attack', 'proposal']) {
      fs.writeFileSync(path.join(schemaDir, 'templates', `${name}.md`), `# ${name}\n`);
    }
    fs.writeFileSync(
      path.join(schemaDir, 'schema.yaml'),
      [
        'name: attack-flow',
        'version: 1',
        'description: proposal behind an optional attack',
        'artifacts:',
        '  - id: brief',
        '    generates: brief.md',
        '    description: Brief',
        '    template: brief.md',
        '    requires: []',
        '  - id: attack',
        '    generates: attack.md',
        '    description: Optional attack on the brief',
        '    template: attack.md',
        '    requires: [brief]',
        '    optional: true',
        '    verdict:',
        '      frontmatter: status',
        '      value: passed',
        '  - id: proposal',
        '    generates: proposal.md',
        '    description: Proposal',
        '    template: proposal.md',
        '    requires: [brief, attack]',
        '',
      ].join('\n')
    );
    changeDir = path.join(tempDir, 'openspec', 'changes', 'my-change');
    fs.mkdirSync(changeDir, { recursive: true });
    fs.writeFileSync(path.join(changeDir, '.openspec.yaml'), 'schema: attack-flow\n');
    fs.writeFileSync(path.join(changeDir, 'brief.md'), '# Brief\n');

    process.chdir(tempDir);
    lines = [];
    vi.spyOn(console, 'log').mockImplementation((...args: unknown[]) => {
      lines.push(args.join(' '));
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
    process.chdir(originalCwd);
    if (originalConfigHome === undefined) {
      delete process.env.XDG_CONFIG_HOME;
    } else {
      process.env.XDG_CONFIG_HOME = originalConfigHome;
    }
    fs.rmSync(tempDir, { recursive: true, force: true });
  });

  it('Необязательный артефакт без файла: зависимость не недостающая, читать нечего', async () => {
    await instructionsCommand('proposal', { change: 'my-change' });
    const output = lines.join('\n');

    expect(output).not.toContain('unmet dependencies');
    expect(output).toContain('<dependency id="attack" status="not-invoked">');
    expect(output).not.toContain(path.join(changeDir, 'attack.md'));
    expect(output).toContain('<dependency id="brief" status="done">');
  });

  it('Необязательный артефакт без файла: --json несёт optional и fileExists у зависимости', async () => {
    await instructionsCommand('proposal', { change: 'my-change', json: true });
    const instructions = JSON.parse(lines.join('\n'));
    const byId = (id: string) =>
      instructions.dependencies.find((d: { id: string }) => d.id === id);

    expect(byId('attack')).toMatchObject({ done: false, optional: true, fileExists: false });
    expect('optional' in byId('brief')).toBe(false);
    expect('fileExists' in byId('brief')).toBe(false);
  });

  it('Необязательный артефакт с файлом: вердикт не passed — зависимость недостающая', async () => {
    fs.writeFileSync(path.join(changeDir, 'attack.md'), '---\nstatus: gaps_found\n---\n# Attack\n');

    await instructionsCommand('proposal', { change: 'my-change' });
    const output = lines.join('\n');

    expect(output).toContain('unmet dependencies');
    expect(output).toContain('Missing: attack');
    expect(output).toContain('<dependency id="attack" status="missing">');
  });
});
