import { createHash } from 'node:crypto';
import * as fs from 'node:fs';
import * as os from 'node:os';
import * as path from 'node:path';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { verdictState, staleVerdictTarget } from '../../../src/core/artifact-graph/state.js';
import type { Artifact } from '../../../src/core/artifact-graph/types.js';

vi.mock('node:fs', { spy: true });
const realRead = (await vi.importActual<typeof import('node:fs')>('node:fs')).readFileSync;

describe('master support verdict freshness', () => {
  let root: string;
  let change: string;
  let spec: string;
  const requirement = '### Requirement: Shared input\nThe system SHALL preserve input.\n\n#### Scenario: Kept\n- **WHEN** called\n- **THEN** input stays\n\n';
  const scenario = '#### Scenario: Kept\n- **WHEN** called\n- **THEN** input stays\n\n';
  const neighbor = '### Requirement: Neighbor\nThe system SHALL remain separate.\n';
  const document = (body: string): string => `# Shared input\n\n## Requirements\n\n${body}`;
  const sha = (content: string): string => createHash('sha256').update(content).digest('hex');
  const artifact: Artifact = {
    id: 'attack', generates: 'attack.md', description: 'Attack', template: 't.md', requires: [],
    verdict: { frontmatter: 'status', value: 'passed' },
  };
  const support = (extra = {}): Record<string, unknown> => ({
    capability: 'shared-input', requirement: 'Shared input', sha256: sha(requirement), ...extra,
  });
  const report = (field: string): void => {
    fs.writeFileSync(path.join(change, 'attack.md'), `---\nstatus: passed\n${field}\n---\n# Attack\n`);
  };
  const writeSupports = (entries: unknown): void => report(`master_supports: ${JSON.stringify(entries)}`);
  const diagnostic = (reason: string): void => {
    expect(verdictState(artifact, change, root)).toBe('stale');
    expect(staleVerdictTarget(artifact, change, root)).toEqual({
      path: 'master_supports[1]', scope: 'master', reason,
    });
  };

  beforeEach(() => {
    root = fs.mkdtempSync(path.join(os.tmpdir(), 'openspec-master-supports-'));
    change = path.join(root, 'openspec', 'changes', 'sample');
    spec = path.join(root, 'openspec', 'specs', 'shared-input', 'spec.md');
    fs.mkdirSync(change, { recursive: true });
    fs.mkdirSync(path.dirname(spec), { recursive: true });
    fs.writeFileSync(spec, document(requirement + neighbor));
  });
  afterEach(() => {
    vi.restoreAllMocks();
    vi.mocked(fs.readFileSync).mockImplementation(realRead);
    fs.rmSync(root, { recursive: true, force: true });
  });

  it.each(['\n', '\r\n', '\r'])('hashes the original requirement block with normalized %j endings and a BOM', (newline) => {
    fs.writeFileSync(spec, '\ufeff' + document(requirement + neighbor).replaceAll('\n', newline));
    writeSupports([support()]);
    expect(verdictState(artifact, change, root)).toBe('ok');
  });

  it('checks only the named scenario within the named requirement', () => {
    writeSupports([support({ scenario: 'Kept', sha256: sha(scenario) })]);
    fs.writeFileSync(spec, document(requirement.replace('preserve input', 'preserve changed input') + neighbor));
    expect(verdictState(artifact, change, root)).toBe('ok');
    fs.writeFileSync(spec, document(requirement.replace('input stays', 'input disappears') + neighbor));
    diagnostic('changed');
  });

  it('does not invalidate an unchanged support when its neighbor changes', () => {
    writeSupports([support()]);
    fs.writeFileSync(spec, document(requirement + neighbor.replace('separate', 'independent')));
    expect(verdictState(artifact, change, root)).toBe('ok');
  });

  it('includes separator blank lines and whitespace in the hashed block', () => {
    writeSupports([support()]);
    fs.writeFileSync(spec, document(requirement.replace('input stays\n\n', 'input stays \n\n') + neighbor));
    diagnostic('changed');
  });

  it('reports a missing file or named block', () => {
    writeSupports([support()]);
    fs.unlinkSync(spec);
    diagnostic('missing');
    fs.writeFileSync(spec, document(neighbor));
    diagnostic('missing');
  });

  it('rejects duplicate named requirements and scenarios', () => {
    writeSupports([support()]);
    fs.writeFileSync(spec, document(requirement + requirement + neighbor));
    diagnostic('ambiguous');
    writeSupports([support({ scenario: 'Kept', sha256: sha(scenario) })]);
    fs.writeFileSync(spec, document(requirement + scenario + neighbor));
    diagnostic('ambiguous');
  });

  it('requires one identified Requirements section and a nonempty selected block', () => {
    writeSupports([support()]);
    fs.writeFileSync(spec, requirement + neighbor);
    diagnostic('invalid');
    fs.writeFileSync(spec, document(requirement) + document(requirement));
    diagnostic('ambiguous');
    fs.writeFileSync(spec, document('### Requirement: Shared input\n\n' + neighbor));
    diagnostic('invalid');
  });

  it('ignores fenced fake headings while preserving their exact bytes', () => {
    const raw = requirement + '~~~md\n### Requirement: Shared input\n#### Scenario: Kept\n~~~\n\n';
    writeSupports([support({ sha256: sha(raw) })]);
    fs.writeFileSync(spec, document(raw + neighbor));
    expect(verdictState(artifact, change, root)).toBe('ok');
    fs.writeFileSync(spec, document(raw.replace('~~~\n\n', '') + neighbor));
    diagnostic('invalid');
  });

  it('matches canonical named headings with closing hashes and case-sensitive identifiers', () => {
    const raw = '###Requirement: Shared input ##\nThe system SHALL preserve input.\n\n';
    fs.writeFileSync(spec, '# Shared\n\n## REQUIREMENTS ##\n\n' + raw + neighbor);
    writeSupports([support({ sha256: sha(raw) })]);
    expect(verdictState(artifact, change, root)).toBe('ok');
    writeSupports([support({ requirement: 'shared input', sha256: sha(raw) })]);
    diagnostic('missing');
  });

  it('rejects non-UTF-8 without hashing replacement characters', () => {
    writeSupports([support()]);
    fs.writeFileSync(spec, Buffer.from([0xff, 0xfe, 0x61]));
    diagnostic('unreadable');
  });

  it('reports read refusal for an existing support', () => {
    writeSupports([support()]);
    vi.mocked(fs.readFileSync).mockImplementation(((file: fs.PathOrFileDescriptor, ...args: unknown[]) => {
      if (file === spec) throw Object.assign(new Error('refused'), { code: 'EACCES' });
      return Reflect.apply(realRead, fs, [file, ...args]);
    }) as typeof fs.readFileSync);
    diagnostic('unreadable');
  });

  it.each(['[broken', '{}', 'null', '[null]', '[{"capability":"shared-input"}]'])('keeps malformed declared JSON stale (%s), including invalid YAML', (raw) => {
    report(`master_supports: ${raw}`);
    diagnostic('invalid');
  });

  it('rejects repeated top-level declarations', () => {
    report('master_supports: []\nmaster_supports: []');
    diagnostic('ambiguous');
  });

  it.each(['"master_supports"', "'master_supports'", 'master_supports '])('rejects noncanonical field spelling %s as declared, including broken YAML', (key) => {
    report(`${key}: ${JSON.stringify([support()])}`);
    diagnostic('invalid');
    report(`${key}: [broken`);
    diagnostic('invalid');
  });

  it.each([' ', '  ', '\t'])('keeps an indented malformed support declaration stale (%j)', (indent) => {
    report(`${indent}master_supports: [broken`);
    diagnostic('invalid');
  });

  it('rejects a continuation under the dedicated one-line support field', () => {
    report('master_supports: []\n  ignored: payload');
    diagnostic('invalid');
  });

  it('rejects a flow-mapping field instead of treating it as absent', () => {
    fs.writeFileSync(path.join(change, 'attack.md'), `---\n${JSON.stringify({ status: 'passed', master_supports: [support()] })}\n---\n`);
    diagnostic('invalid');
  });

  it.each([
    { requirement: ' Shared input' }, { scenario: 'Kept\nnext' }, { extra: 'unexpected' },
    { scenario: null }, { sha256: 'f'.repeat(63) },
  ])('rejects an invalid support record %j', (extra) => {
    writeSupports([support(extra)]);
    diagnostic('invalid');
  });

  it('rejects duplicate JSON keys and duplicate support identities', () => {
    report(`master_supports: [{"capability":"shared-input","capability":"shared-input","requirement":"Shared input","sha256":"${sha(requirement)}"}]`);
    diagnostic('invalid');
    writeSupports([support(), support()]);
    expect(staleVerdictTarget(artifact, change, root)).toEqual({ path: 'master_supports[2]', scope: 'master', reason: 'ambiguous' });
  });

  it('identifies duplicate nested supports through slash and backslash aliases', () => {
    fs.mkdirSync(path.join(root, 'openspec', 'specs', 'nested'), { recursive: true });
    fs.renameSync(path.dirname(spec), path.join(root, 'openspec', 'specs', 'nested', 'shared-input'));
    writeSupports([support({ capability: 'nested/shared-input' }), support({ capability: 'nested\\shared-input' })]);
    expect(staleVerdictTarget(artifact, change, root)).toEqual({ path: 'master_supports[2]', scope: 'master', reason: 'ambiguous' });
  });

  it('does not recover an otherwise malformed YAML document as a passing verdict', () => {
    report(`master_supports: ${JSON.stringify([support()])}\nbroken: [value`);
    expect(verdictState(artifact, change, root)).toBe('missing');
  });

  it('does not read master supports behind a nonpassing verdict', () => {
    report(`master_supports: ${JSON.stringify([support()])}`);
    const file = path.join(change, 'attack.md');
    fs.writeFileSync(file, fs.readFileSync(file, 'utf8').replace('status: passed', 'status: gaps_found'));
    const opened: string[] = [];
    vi.mocked(fs.readFileSync).mockImplementation(((file: fs.PathOrFileDescriptor, ...args: unknown[]) => {
      opened.push(String(file));
      return Reflect.apply(realRead, fs, [file, ...args]);
    }) as typeof fs.readFileSync);
    expect(verdictState(artifact, change, root)).toBe('mismatch');
    expect(opened.filter((file) => file.endsWith('spec.md'))).toEqual([]);
  });

  it.each(['../private', 'safe/../shared-input', '/private', 'C:\\private', 'C:private', '\\\\host\\private', '.', 'safe//shared-input', 'safe/./shared-input', '\u212a'])('rejects outside capability %j before opening its file', (capability) => {
    writeSupports([support({ capability })]);
    diagnostic('outside');
  });

  it('accepts nested capabilities within the master-spec directory', () => {
    fs.mkdirSync(path.join(root, 'openspec', 'specs', 'nested'), { recursive: true });
    fs.renameSync(path.dirname(spec), path.join(root, 'openspec', 'specs', 'nested', 'shared-input'));
    writeSupports([support({ capability: 'nested/shared-input' })]);
    expect(verdictState(artifact, change, root)).toBe('ok');
  });

  it.each(['specs', 'capability'])('rejects an escaping %s junction before reading', (kind) => {
    const outside = fs.mkdtempSync(path.join(os.tmpdir(), 'openspec-master-outside-'));
    try {
      const link = kind === 'specs' ? path.join(root, 'openspec', 'specs') : path.dirname(spec);
      fs.renameSync(link, path.join(outside, 'original'));
      fs.symlinkSync(path.join(outside, 'original'), link, 'junction');
      writeSupports([support()]);
      const opened: string[] = [];
      vi.mocked(fs.readFileSync).mockImplementation(((file: fs.PathOrFileDescriptor, ...args: unknown[]) => {
        opened.push(String(file));
        return Reflect.apply(realRead, fs, [file, ...args]);
      }) as typeof fs.readFileSync);
      diagnostic('outside');
      expect(opened.filter((file) => file.endsWith('spec.md'))).toEqual([]);
      fs.unlinkSync(link);
    } finally {
      fs.rmSync(outside, { recursive: true, force: true });
    }
  });

  it('rejects a master-spec directory junction resolving to the planning root itself', () => {
    fs.renameSync(path.join(root, 'openspec', 'specs'), path.join(root, 'saved-specs'));
    fs.renameSync(path.join(root, 'saved-specs', 'shared-input'), path.join(root, 'shared-input'));
    const link = path.join(root, 'openspec', 'specs');
    fs.symlinkSync(root, link, 'junction');
    try {
      writeSupports([support()]);
      diagnostic('outside');
    } finally {
      fs.unlinkSync(link);
    }
  });

  it('keeps old reports on their local target hashes', () => {
    fs.writeFileSync(path.join(change, 'design.md'), 'design\n');
    report(`targets: [{"path":"design.md","sha256":"${sha('design\n')}"}]`);
    expect(verdictState(artifact, change, root)).toBe('ok');
    fs.writeFileSync(path.join(change, 'design.md'), 'changed\n');
    expect(staleVerdictTarget(artifact, change, root)).toEqual({ path: 'design.md', reason: 'changed' });
  });
});
