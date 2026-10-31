import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import * as fs from 'node:fs';
import * as path from 'node:path';
import * as os from 'node:os';
import { statusCommand } from '../../src/commands/workflow/status.js';
import { runCLI } from '../helpers/run-cli.js';

// Fork (symphysis, C3): `openspec status` for a change whose schema declares a
// verdict artifact. Most cases call the command in-process; the last one goes
// through the real CLI with runCLI, which runs the built `dist/` - build
// (`pnpm build`) before running it, runCLI builds only when `dist/` is missing.
describe('status command with a verdict artifact', () => {
  let tempDir: string;
  let originalCwd: string;
  let originalConfigHome: string | undefined;
  let lines: string[];

  beforeEach(() => {
    originalCwd = process.cwd();
    originalConfigHome = process.env.XDG_CONFIG_HOME;
    tempDir = fs.realpathSync(fs.mkdtempSync(path.join(os.tmpdir(), 'openspec-status-verdict-')));
    // Keep the developer's real global config (default store, ...) out of root resolution.
    process.env.XDG_CONFIG_HOME = path.join(tempDir, 'xdg-config');

    const schemaDir = path.join(tempDir, 'openspec', 'schemas', 'verdict-flow');
    fs.mkdirSync(schemaDir, { recursive: true });
    fs.writeFileSync(
      path.join(schemaDir, 'schema.yaml'),
      [
        'name: verdict-flow',
        'version: 1',
        'description: schema with a verdict artifact',
        'artifacts:',
        '  - id: attack',
        '    generates: attack.md',
        '    description: Attack review',
        '    template: attack.md',
        '    requires: []',
        '    verdict:',
        '      frontmatter: status',
        '      value: passed',
        '  - id: after',
        '    generates: after.md',
        '    description: Work that follows a passed attack review',
        '    template: after.md',
        '    requires: [attack]',
        '',
      ].join('\n')
    );
    const changeDir = path.join(tempDir, 'openspec', 'changes', 'my-change');
    fs.mkdirSync(changeDir, { recursive: true });
    fs.writeFileSync(path.join(changeDir, '.openspec.yaml'), 'schema: verdict-flow\n');

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

  function writeAttack(content: string): void {
    fs.writeFileSync(path.join(tempDir, 'openspec', 'changes', 'my-change', 'attack.md'), content);
  }

  it('prints the verdict and the hint in --json when the verdict does not match', async () => {
    writeAttack('---\nstatus: gaps_found\n---\n# Attack\n');

    await statusCommand({ change: 'my-change', json: true });

    const status = JSON.parse(lines.join('\n'));
    const attack = status.artifacts.find((a: { id: string }) => a.id === 'attack');
    const after = status.artifacts.find((a: { id: string }) => a.id === 'after');
    expect(attack.status).toBe('ready');
    expect(attack.verdict).toBe('mismatch');
    expect('verdict' in after).toBe(false);
    expect(status.nextSteps[0]).toBe(
      'Artifact "attack" has verdict status=gaps_found but passed is required — run its instruction again'
    );
  });

  it('shows the verdict word after each verdict artifact in the text output', async () => {
    writeAttack('# Attack\n\nNo frontmatter here.\n');
    await statusCommand({ change: 'my-change' });
    expect(lines.join('\n')).toContain('[ ] attack (verdict: missing)');
    expect(lines.join('\n')).toContain('[-] after (blocked by: attack)');

    lines.length = 0;
    writeAttack('---\nstatus: gaps_found\n---\n# Attack\n');
    await statusCommand({ change: 'my-change' });
    expect(lines.join('\n')).toContain('[ ] attack (verdict: mismatch)');

    lines.length = 0;
    writeAttack('---\nstatus: passed\n---\n# Attack\n');
    await statusCommand({ change: 'my-change' });
    const output = lines.join('\n');
    expect(output).toContain('[x] attack (verdict: ok)');
    // A plain artifact carries no verdict suffix.
    expect(output).toMatch(/\[ \] after$/m);
  });

  it('reports the verdict through the real CLI (built dist/)', async () => {
    writeAttack('---\nstatus: gaps_found\n---\n# Attack\n');

    const result = await runCLI(['status', '--change', 'my-change', '--json'], { cwd: tempDir });

    expect(result.exitCode).toBe(0);
    const status = JSON.parse(result.stdout);
    const attack = status.artifacts.find((a: { id: string }) => a.id === 'attack');
    const after = status.artifacts.find((a: { id: string }) => a.id === 'after');
    expect(attack.status).toBe('ready');
    expect(attack.verdict).toBe('mismatch');
    expect(after.status).toBe('blocked');
    expect(status.nextSteps[0]).toBe(
      'Artifact "attack" has verdict status=gaps_found but passed is required — run its instruction again'
    );
  });

  // Fork (symphysis, C7): optional artifacts and the stale verdict in the
  // status output.
  describe('optional artifacts', () => {
    const changeDir = () => path.join(tempDir, 'openspec', 'changes', 'my-change');

    beforeEach(() => {
      const schemaDir = path.join(tempDir, 'openspec', 'schemas', 'optional-flow');
      fs.mkdirSync(schemaDir, { recursive: true });
      fs.writeFileSync(
        path.join(schemaDir, 'schema.yaml'),
        [
          'name: optional-flow',
          'version: 1',
          'description: schema with optional verdict artifacts',
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
          '  - id: review',
          '    generates: review.md',
          '    description: Optional review of the proposal',
          '    template: review.md',
          '    requires: [proposal]',
          '    optional: true',
          '    verdict:',
          '      frontmatter: status',
          '      value: passed',
          '',
        ].join('\n')
      );
      fs.writeFileSync(path.join(changeDir(), '.openspec.yaml'), 'schema: optional-flow\n');
      fs.writeFileSync(path.join(changeDir(), 'brief.md'), '# Brief\n');
    });

    it('Планирование без вызванных атак: --json несёт optional и fileExists, текст называет невызванные', async () => {
      fs.writeFileSync(path.join(changeDir(), 'proposal.md'), '# Proposal\n');

      await statusCommand({ change: 'my-change', json: true });
      const status = JSON.parse(lines.join('\n'));
      const byId = (id: string) => status.artifacts.find((a: { id: string }) => a.id === id);
      expect(status.isPlanningComplete).toBe(true);
      for (const id of ['attack', 'review']) {
        expect(byId(id).optional).toBe(true);
        expect(byId(id).fileExists).toBe(false);
        expect('verdict' in byId(id)).toBe(false);
      }

      lines.length = 0;
      await statusCommand({ change: 'my-change' });
      const output = lines.join('\n');
      expect(output).toContain('[ ] attack (optional, not invoked)');
      expect(output).toContain('[ ] review (optional, not invoked)');
      expect(output).toContain('Progress: 2/2 artifacts complete (2 optional, not invoked)');
      expect(output).toContain(
        'All planning artifacts complete! (optional, not invoked: attack, review)'
      );
      expect(output).toContain('Next: openspec instructions apply --change "my-change" --json');
    });

    it('Необязательный артефакт с файлом: текст показывает вердикт, а не «not invoked»', async () => {
      fs.writeFileSync(path.join(changeDir(), 'attack.md'), '---\nstatus: gaps_found\n---\n# Attack\n');

      await statusCommand({ change: 'my-change' });
      const output = lines.join('\n');
      expect(output).toContain('[ ] attack (verdict: mismatch)');
      expect(output).not.toContain('attack (optional, not invoked)');
      expect(output).toContain('[-] proposal (blocked by: attack)');
      expect(output).toContain('Progress: 1/3 artifacts complete (1 optional, not invoked)');
      expect(output).toContain('Next: openspec instructions attack --change "my-change" --json');
    });

    it('Вердикт с чужим хешем: текст показывает stale', async () => {
      fs.writeFileSync(
        path.join(changeDir(), 'attack.md'),
        `---\nstatus: passed\ntarget: brief.md\ntarget_sha256: ${'0'.repeat(64)}\n---\n# Attack\n`
      );

      await statusCommand({ change: 'my-change' });
      const output = lines.join('\n');
      expect(output).toContain('[ ] attack (verdict: stale)');
      expect(output).toContain('[-] proposal (blocked by: attack)');
    });

    // Fork (symphysis, C11): proposal exists, so the stale verdict is a signal.
    it('Устаревший вердикт после начала работы — сигнал: текст и --json', async () => {
      fs.writeFileSync(
        path.join(changeDir(), 'attack.md'),
        `---\nstatus: passed\ntarget: brief.md\ntarget_sha256: ${'0'.repeat(64)}\n---\n# Attack\n`
      );
      fs.writeFileSync(path.join(changeDir(), 'proposal.md'), '# Proposal\n');

      await statusCommand({ change: 'my-change' });
      const output = lines.join('\n');
      expect(output).toContain('[x] attack (verdict: stale — signal, not a gate)');
      expect(output).toContain('All planning artifacts complete! (optional, not invoked: review)');

      lines.length = 0;
      await statusCommand({ change: 'my-change', json: true });
      const status = JSON.parse(lines.join('\n'));
      const attack = status.artifacts.find((a: { id: string }) => a.id === 'attack');
      expect(attack).toMatchObject({ status: 'done', verdict: 'stale', optional: true, fileExists: true });
      expect(status.isPlanningComplete).toBe(true);
      expect(status.nextSteps).toContain(
        'Artifact "attack" verdict is stale (signal, not a gate: proposal already exists) — re-run it by name if needed'
      );
    });
  });
});
