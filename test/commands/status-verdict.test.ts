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
});
