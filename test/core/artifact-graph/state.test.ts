import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import * as fs from 'node:fs';
import * as path from 'node:path';
import * as os from 'node:os';
import { createHash } from 'node:crypto';
import {
  detectAbsentOptional,
  detectCompleted,
  detectStaleSignals,
  staleVerdictTarget,
  verdictState,
} from '../../../src/core/artifact-graph/state.js';
import { ArtifactGraph } from '../../../src/core/artifact-graph/graph.js';
import type { Artifact, SchemaYaml } from '../../../src/core/artifact-graph/types.js';

describe('artifact-graph/state', () => {
  let tempDir: string;

  const createSchema = (artifacts: SchemaYaml['artifacts']): SchemaYaml => ({
    name: 'test',
    version: 1,
    artifacts,
  });

  beforeEach(() => {
    tempDir = fs.mkdtempSync(path.join(os.tmpdir(), 'openspec-state-test-'));
  });

  afterEach(() => {
    fs.rmSync(tempDir, { recursive: true, force: true });
  });

  describe('detectCompleted', () => {
    it('should return empty set when changeDir does not exist', () => {
      const schema = createSchema([
        { id: 'A', generates: 'a.md', description: 'A', template: 't.md', requires: [] },
      ]);
      const graph = ArtifactGraph.fromSchema(schema);

      const completed = detectCompleted(graph, '/nonexistent/path');

      expect(completed.size).toBe(0);
    });

    it('should return empty set when changeDir is empty', () => {
      const schema = createSchema([
        { id: 'A', generates: 'a.md', description: 'A', template: 't.md', requires: [] },
      ]);
      const graph = ArtifactGraph.fromSchema(schema);

      const completed = detectCompleted(graph, tempDir);

      expect(completed.size).toBe(0);
    });

    it('should mark artifact complete when file exists', () => {
      const schema = createSchema([
        { id: 'proposal', generates: 'proposal.md', description: 'Proposal', template: 't.md', requires: [] },
      ]);
      const graph = ArtifactGraph.fromSchema(schema);

      // Create the file
      fs.writeFileSync(path.join(tempDir, 'proposal.md'), 'content');

      const completed = detectCompleted(graph, tempDir);

      expect(completed.has('proposal')).toBe(true);
    });

    it('should not mark artifact complete when file does not exist', () => {
      const schema = createSchema([
        { id: 'proposal', generates: 'proposal.md', description: 'Proposal', template: 't.md', requires: [] },
        { id: 'design', generates: 'design.md', description: 'Design', template: 't.md', requires: [] },
      ]);
      const graph = ArtifactGraph.fromSchema(schema);

      // Only create proposal.md
      fs.writeFileSync(path.join(tempDir, 'proposal.md'), 'content');

      const completed = detectCompleted(graph, tempDir);

      expect(completed.has('proposal')).toBe(true);
      expect(completed.has('design')).toBe(false);
    });

    it('should handle nested paths', () => {
      const schema = createSchema([
        { id: 'nested', generates: 'docs/design.md', description: 'Nested', template: 't.md', requires: [] },
      ]);
      const graph = ArtifactGraph.fromSchema(schema);

      // Create nested directory and file
      fs.mkdirSync(path.join(tempDir, 'docs'), { recursive: true });
      fs.writeFileSync(path.join(tempDir, 'docs', 'design.md'), 'content');

      const completed = detectCompleted(graph, tempDir);

      expect(completed.has('nested')).toBe(true);
    });

    it('should detect glob pattern as complete when files exist', () => {
      const schema = createSchema([
        { id: 'specs', generates: 'specs/*.md', description: 'Specs', template: 't.md', requires: [] },
      ]);
      const graph = ArtifactGraph.fromSchema(schema);

      // Create specs directory with files
      fs.mkdirSync(path.join(tempDir, 'specs'), { recursive: true });
      fs.writeFileSync(path.join(tempDir, 'specs', 'feature-a.md'), 'content');
      fs.writeFileSync(path.join(tempDir, 'specs', 'feature-b.md'), 'content');

      const completed = detectCompleted(graph, tempDir);

      expect(completed.has('specs')).toBe(true);
    });

    it('should not mark glob pattern complete when directory is empty', () => {
      const schema = createSchema([
        { id: 'specs', generates: 'specs/*.md', description: 'Specs', template: 't.md', requires: [] },
      ]);
      const graph = ArtifactGraph.fromSchema(schema);

      // Create empty specs directory
      fs.mkdirSync(path.join(tempDir, 'specs'), { recursive: true });

      const completed = detectCompleted(graph, tempDir);

      expect(completed.has('specs')).toBe(false);
    });

    it('should not mark glob pattern complete when directory does not exist', () => {
      const schema = createSchema([
        { id: 'specs', generates: 'specs/*.md', description: 'Specs', template: 't.md', requires: [] },
      ]);
      const graph = ArtifactGraph.fromSchema(schema);

      const completed = detectCompleted(graph, tempDir);

      expect(completed.has('specs')).toBe(false);
    });

    it('should not mark glob pattern complete when only non-matching files exist', () => {
      const schema = createSchema([
        { id: 'specs', generates: 'specs/*.md', description: 'Specs', template: 't.md', requires: [] },
      ]);
      const graph = ArtifactGraph.fromSchema(schema);

      // Create specs directory with non-matching files
      fs.mkdirSync(path.join(tempDir, 'specs'), { recursive: true });
      fs.writeFileSync(path.join(tempDir, 'specs', 'readme.txt'), 'content');

      const completed = detectCompleted(graph, tempDir);

      expect(completed.has('specs')).toBe(false);
    });

    it('should handle multiple artifacts with mixed completion', () => {
      const schema = createSchema([
        { id: 'proposal', generates: 'proposal.md', description: 'Proposal', template: 't.md', requires: [] },
        { id: 'specs', generates: 'specs/*.md', description: 'Specs', template: 't.md', requires: ['proposal'] },
        { id: 'design', generates: 'design.md', description: 'Design', template: 't.md', requires: ['proposal'] },
        { id: 'tasks', generates: 'tasks.md', description: 'Tasks', template: 't.md', requires: ['specs', 'design'] },
      ]);
      const graph = ArtifactGraph.fromSchema(schema);

      // Create some files
      fs.writeFileSync(path.join(tempDir, 'proposal.md'), 'content');
      fs.mkdirSync(path.join(tempDir, 'specs'), { recursive: true });
      fs.writeFileSync(path.join(tempDir, 'specs', 'auth.md'), 'content');
      // design.md and tasks.md do not exist

      const completed = detectCompleted(graph, tempDir);

      expect(completed.has('proposal')).toBe(true);
      expect(completed.has('specs')).toBe(true);
      expect(completed.has('design')).toBe(false);
      expect(completed.has('tasks')).toBe(false);
    });

    it('should detect brace expansion pattern as complete and unblock dependent artifact', () => {
      const schema = createSchema([
        {
          id: 'review',
          generates: 'review-{api,ui}.md',
          description: 'Review',
          template: 't.md',
          requires: [],
        },
        {
          id: 'signoff',
          generates: 'signoff.md',
          description: 'Signoff',
          template: 't.md',
          requires: ['review'],
        },
      ]);
      const graph = ArtifactGraph.fromSchema(schema);

      fs.writeFileSync(path.join(tempDir, 'review-api.md'), 'content');

      const completed = detectCompleted(graph, tempDir);
      expect(completed.has('review')).toBe(true);
      expect(completed.has('signoff')).toBe(false);

      const next = graph.getNextArtifacts(completed);
      expect(next).toEqual(['signoff']);
    });

    it('should detect extglob pattern as complete and unblock dependent artifact', () => {
      const schema = createSchema([
        {
          id: 'spec',
          generates: '@(proposal|design).md',
          description: 'Spec',
          template: 't.md',
          requires: [],
        },
        {
          id: 'tasks',
          generates: 'tasks.md',
          description: 'Tasks',
          template: 't.md',
          requires: ['spec'],
        },
      ]);
      const graph = ArtifactGraph.fromSchema(schema);

      fs.writeFileSync(path.join(tempDir, 'proposal.md'), 'content');

      const completed = detectCompleted(graph, tempDir);
      expect(completed.has('spec')).toBe(true);
      expect(completed.has('tasks')).toBe(false);

      const next = graph.getNextArtifacts(completed);
      expect(next).toEqual(['tasks']);
    });
  });

  describe('verdict artifacts', () => {
    const verdictArtifact = (): Artifact => ({
      id: 'attack',
      generates: 'attack.md',
      description: 'Attack',
      template: 't.md',
      requires: [],
      verdict: { frontmatter: 'status', value: 'passed' },
    });

    const graphWithVerdict = (): ArtifactGraph =>
      ArtifactGraph.fromSchema(
        createSchema([
          verdictArtifact(),
          { id: 'next', generates: 'next.md', description: 'Next', template: 't.md', requires: ['attack'] },
        ])
      );

    const write = (file: string, content: string): void => {
      fs.writeFileSync(file, content);
    };

    it('verdict artifact with file but no frontmatter is not completed', () => {
      write(path.join(tempDir, 'attack.md'), '# no frontmatter');

      expect(detectCompleted(graphWithVerdict(), tempDir).has('attack')).toBe(false);
    });

    it('verdict artifact with status passed is completed', () => {
      write(path.join(tempDir, 'attack.md'), '---\nstatus: passed\n---\n');

      expect(detectCompleted(graphWithVerdict(), tempDir).has('attack')).toBe(true);
    });

    it('verdict artifact with status passed is completed under CRLF and BOM', () => {
      write(path.join(tempDir, 'attack.md'), '\uFEFF---\r\nstatus: passed\r\n---\r\n# t\r\n');

      expect(detectCompleted(graphWithVerdict(), tempDir).has('attack')).toBe(true);
    });

    it('verdict artifact with status gaps_found is not completed', () => {
      write(path.join(tempDir, 'attack.md'), '---\nstatus: gaps_found\n---\n');

      expect(detectCompleted(graphWithVerdict(), tempDir).has('attack')).toBe(false);
    });

    it('verdict artifact without a file is not completed', () => {
      expect(detectCompleted(graphWithVerdict(), tempDir).has('attack')).toBe(false);
    });

    it('a not-passed verdict artifact keeps its dependents blocked', () => {
      const graph = graphWithVerdict();
      write(path.join(tempDir, 'attack.md'), '---\nstatus: gaps_found\n---\n');
      expect(graph.getNextArtifacts(detectCompleted(graph, tempDir))).toEqual(['attack']);

      write(path.join(tempDir, 'attack.md'), '---\nstatus: passed\n---\n');
      expect(graph.getNextArtifacts(detectCompleted(graph, tempDir))).toEqual(['next']);
    });

    it.each([
      ['no frontmatter', '# plain'],
      ['gaps_found frontmatter', '---\nstatus: gaps_found\n---\n'],
      ['passed frontmatter', '---\nstatus: passed\n---\n'],
      ['invalid yaml frontmatter', '---\nstatus: [oops\n---\n'],
    ])('artifact without verdict stays completed by file existence (%s)', (_label, content) => {
      const schema = createSchema([
        { id: 'plain', generates: 'plain.md', description: 'Plain', template: 't.md', requires: [] },
      ]);
      write(path.join(tempDir, 'plain.md'), content);

      expect(detectCompleted(ArtifactGraph.fromSchema(schema), tempDir).has('plain')).toBe(true);
    });
  });

  describe('verdictState', () => {
    const artifact = (verdict?: Artifact['verdict']): Artifact => ({
      id: 'attack',
      generates: 'attack.md',
      description: 'Attack',
      template: 't.md',
      requires: [],
      ...(verdict ? { verdict } : {}),
    });
    const verdict = { frontmatter: 'status', value: 'passed' };
    const file = (): string => path.join(tempDir, 'attack.md');

    it("returns 'n/a' for an artifact without verdict", () => {
      fs.writeFileSync(file(), '---\nstatus: passed\n---\n');

      expect(verdictState(artifact(), tempDir)).toBe('n/a');
    });

    it.each([
      ['file absent', undefined, 'missing'],
      ['no frontmatter', '# plain', 'missing'],
      ['unterminated frontmatter', '---\nstatus: passed\n', 'missing'],
      ['key absent', '---\nround: 1\n---\n', 'missing'],
      ['value differs', '---\nstatus: gaps_found\n---\n', 'mismatch'],
      ['key present but empty', '---\nstatus:\n---\n', 'mismatch'],
      ['value equal', '---\nstatus: passed\n---\n', 'ok'],
      ['value equal under CRLF and BOM', '\uFEFF---\r\nstatus: passed\r\n---\r\n', 'ok'],
    ])('returns the right state when %s', (_label, content, expected) => {
      if (content !== undefined) fs.writeFileSync(file(), content);

      expect(verdictState(artifact(verdict), tempDir)).toBe(expected);
    });

    it('compares non-string scalars by their string form', () => {
      fs.writeFileSync(file(), '---\npassed: true\n---\n');

      expect(verdictState(artifact({ frontmatter: 'passed', value: 'true' }), tempDir)).toBe('ok');
      expect(verdictState(artifact({ frontmatter: 'passed', value: 'false' }), tempDir)).toBe('mismatch');
    });

    it('does not treat inherited object keys as present', () => {
      fs.writeFileSync(file(), '---\nstatus: passed\n---\n');

      expect(verdictState(artifact({ frontmatter: 'toString', value: 'passed' }), tempDir)).toBe('missing');
    });

    it("returns 'missing' when the output path is a directory", () => {
      fs.mkdirSync(file());

      expect(verdictState(artifact(verdict), tempDir)).toBe('missing');
    });
  });

  // Fork (symphysis, C7): optional artifacts. An optional artifact without a
  // file satisfies its dependents and is left out of planning completeness;
  // with a file it gates by its verdict like any other artifact.
  describe('optional artifacts', () => {
    const graph = (): ArtifactGraph =>
      ArtifactGraph.fromSchema(
        createSchema([
          { id: 'brief', generates: 'brief.md', description: 'Brief', template: 't.md', requires: [] },
          {
            id: 'attack',
            generates: 'attack.md',
            description: 'Attack',
            template: 't.md',
            requires: ['brief'],
            optional: true,
            verdict: { frontmatter: 'status', value: 'passed' },
          },
          {
            id: 'proposal',
            generates: 'proposal.md',
            description: 'Proposal',
            template: 't.md',
            requires: ['brief', 'attack'],
          },
        ])
      );

    // completed: done artifacts; satisfied: what a `requires` edge accepts.
    const stateOf = (g: ArtifactGraph) => {
      const completed = detectCompleted(g, tempDir);
      const absent = detectAbsentOptional(g, tempDir);
      return { completed, absent, satisfied: new Set([...completed, ...absent]) };
    };

    const write = (file: string, content: string): void => {
      fs.writeFileSync(path.join(tempDir, file), content);
    };

    it('Необязательный артефакт без файла: не блокирует зависимые и сам ready', () => {
      write('brief.md', '# Brief\n');
      const g = graph();
      const { completed, absent, satisfied } = stateOf(g);

      expect([...absent]).toEqual(['attack']);
      expect(completed.has('attack')).toBe(false);
      expect(g.getNextArtifacts(completed, satisfied)).toEqual(['attack', 'proposal']);
      expect(g.getBlocked(completed, satisfied)).toEqual({});
    });

    it('Необязательный артефакт без файла: в отсутствующие попадают только optional', () => {
      const g = graph();
      const { completed, absent, satisfied } = stateOf(g);

      // brief is missing too, but it is not optional.
      expect([...absent]).toEqual(['attack']);
      expect(g.getNextArtifacts(completed, satisfied)).toEqual(['brief']);
      expect(g.getBlocked(completed, satisfied)).toEqual({ attack: ['brief'], proposal: ['brief'] });
    });

    it('Необязательный артефакт без файла: зависимость удовлетворена и при невыполненных зависимостях его самого', () => {
      const g = ArtifactGraph.fromSchema(
        createSchema([
          { id: 'brief', generates: 'brief.md', description: 'Brief', template: 't.md', requires: [] },
          {
            id: 'attack',
            generates: 'attack.md',
            description: 'Attack',
            template: 't.md',
            requires: ['brief'],
            optional: true,
          },
          { id: 'after', generates: 'after.md', description: 'After', template: 't.md', requires: ['attack'] },
        ])
      );
      const { completed, satisfied } = stateOf(g);

      expect(g.getNextArtifacts(completed, satisfied)).toEqual(['brief', 'after']);
      expect(g.getBlocked(completed, satisfied)).toEqual({ attack: ['brief'] });
    });

    it('Необязательный артефакт с файлом: вердикт не passed держит зависимые', () => {
      write('brief.md', '# Brief\n');
      write('attack.md', '---\nstatus: gaps_found\n---\n');
      const g = graph();
      const { completed, absent, satisfied } = stateOf(g);

      expect(absent.size).toBe(0);
      expect(completed.has('attack')).toBe(false);
      expect(g.getNextArtifacts(completed, satisfied)).toEqual(['attack']);
      expect(g.getBlocked(completed, satisfied)).toEqual({ proposal: ['attack'] });
      expect(g.isComplete(satisfied)).toBe(false);
    });

    it('Необязательный артефакт с файлом: вердикт passed открывает зависимые', () => {
      write('brief.md', '# Brief\n');
      write('attack.md', '---\nstatus: passed\n---\n');
      const g = graph();
      const { completed, satisfied } = stateOf(g);

      expect(completed.has('attack')).toBe(true);
      expect(g.getNextArtifacts(completed, satisfied)).toEqual(['proposal']);
    });

    it('Файл вызванной атаки удалён: артефакт снова optional без файла, зависимые не blocked', () => {
      write('brief.md', '# Brief\n');
      write('attack.md', '---\nstatus: gaps_found\n---\n');
      const g = graph();
      const before = stateOf(g);
      expect(g.getBlocked(before.completed, before.satisfied)).toEqual({ proposal: ['attack'] });

      fs.rmSync(path.join(tempDir, 'attack.md'));
      const { completed, absent, satisfied } = stateOf(g);

      expect([...absent]).toEqual(['attack']);
      expect(g.getBlocked(completed, satisfied)).toEqual({});
      expect(g.getNextArtifacts(completed, satisfied)).toEqual(['attack', 'proposal']);
    });

    it('Планирование без вызванных атак: полнота не ждёт optional-артефакт без файла', () => {
      write('brief.md', '# Brief\n');
      write('proposal.md', '# Proposal\n');
      const g = graph();
      const { completed, satisfied } = stateOf(g);

      expect(g.isComplete(satisfied)).toBe(true);
      expect(g.isComplete(completed)).toBe(false);
    });

    it('detectAbsentOptional считает все optional отсутствующими без каталога изменения', () => {
      expect([...detectAbsentOptional(graph(), path.join(tempDir, 'missing'))]).toEqual(['attack']);
    });
  });

  // Fork (symphysis, C7): a passed verdict whose target hashes no longer match
  // the files is `stale`, so the artifact is not done.
  describe('stale verdict', () => {
    const sha = (content: string): string => createHash('sha256').update(content).digest('hex');
    const attack: Artifact = {
      id: 'attack',
      generates: 'attack.md',
      description: 'Attack',
      template: 't.md',
      requires: [],
      verdict: { frontmatter: 'status', value: 'passed' },
    };
    const write = (file: string, content: string): void => {
      fs.mkdirSync(path.dirname(path.join(tempDir, file)), { recursive: true });
      fs.writeFileSync(path.join(tempDir, file), content);
    };
    const writeVerdict = (frontmatter: string): void => {
      write('attack.md', `---\n${frontmatter}---\n# Attack\n`);
    };

    let outsideDir: string;
    beforeEach(() => {
      outsideDir = fs.mkdtempSync(path.join(os.tmpdir(), 'openspec-state-outside-'));
    });
    afterEach(() => {
      fs.rmSync(outsideDir, { recursive: true, force: true });
    });

    it('Вердикт с чужим хешем: targets[].sha256 разошёлся с файлом — stale', () => {
      write('specs/a/spec.md', 'spec A\n');
      write('design.md', 'design, edited after the attack\n');
      writeVerdict(
        'status: passed\ntargets:\n' +
          `  - path: specs/a/spec.md\n    sha256: ${sha('spec A\n')}\n` +
          `  - path: design.md\n    sha256: ${sha('design as attacked\n')}\n`
      );

      expect(verdictState(attack, tempDir)).toBe('stale');
      expect(staleVerdictTarget(attack, tempDir)).toEqual({ path: 'design.md', reason: 'changed' });
    });

    it('Вердикт с чужим хешем: target_sha256 разошёлся с файлом — stale', () => {
      write('decisions.json', '{"entries": []}\n');
      writeVerdict(`status: passed\ntarget: decisions.json\ntarget_sha256: ${sha('{}\n')}\n`);

      expect(verdictState(attack, tempDir)).toBe('stale');
      expect(staleVerdictTarget(attack, tempDir)).toEqual({ path: 'decisions.json', reason: 'changed' });
    });

    it('Вердикт с чужим хешем: хеши совпали — ok', () => {
      // Raw bytes, as sha256sum hashes them: CRLF stays CRLF.
      write('decisions.json', '{"entries": []}\r\n');
      write('specs/a/spec.md', 'spec A\n');
      write('design.md', 'design\n');
      writeVerdict(
        'status: passed\n' +
          `target: decisions.json\ntarget_sha256: ${sha('{"entries": []}\r\n')}\n` +
          'targets:\n' +
          `  - path: decisions.json\n    sha256: ${sha('{"entries": []}\r\n')}\n` +
          `  - path: specs\\a\\spec.md\n    sha256: ${sha('spec A\n')}\n` +
          `  - path: ./design.md\n    sha256: ${sha('design\n').toUpperCase()}\n`
      );

      expect(verdictState(attack, tempDir)).toBe('ok');
      expect(staleVerdictTarget(attack, tempDir)).toBeUndefined();
    });

    it('Вердикт с чужим хешем: файл цели удалён — stale', () => {
      writeVerdict(`status: passed\ntargets:\n  - path: design.md\n    sha256: ${sha('design\n')}\n`);

      expect(verdictState(attack, tempDir)).toBe('stale');
      expect(staleVerdictTarget(attack, tempDir)).toEqual({ path: 'design.md', reason: 'changed' });
    });

    it.each([
      ['абсолютный путь', (file: string) => file],
      [
        'путь с .. после нормализации',
        (file: string) => `specs/../../${path.basename(path.dirname(file))}/${path.basename(file)}`,
      ],
    ])('Вердикт с чужим хешем: цель вне каталога изменения (%s) — stale и при верном хеше', (_label, declared) => {
      const outsideFile = path.join(outsideDir, 'outside.md');
      fs.writeFileSync(outsideFile, 'outside\n');
      const declaredPath = declared(outsideFile);
      writeVerdict(
        `status: passed\ntargets:\n  - path: ${JSON.stringify(declaredPath)}\n    sha256: ${sha('outside\n')}\n`
      );

      expect(verdictState(attack, tempDir)).toBe('stale');
      expect(staleVerdictTarget(attack, tempDir)).toEqual({ path: declaredPath, reason: 'outside' });
    });

    it('Вердикт с чужим хешем: цель через ссылку наружу — stale', (ctx) => {
      fs.writeFileSync(path.join(outsideDir, 'outside.md'), 'outside\n');
      try {
        // A junction needs no privileges on Windows; elsewhere it is a symlink.
        fs.symlinkSync(outsideDir, path.join(tempDir, 'linked'), 'junction');
      } catch {
        ctx.skip();
      }
      writeVerdict(`status: passed\ntargets:\n  - path: linked/outside.md\n    sha256: ${sha('outside\n')}\n`);

      expect(verdictState(attack, tempDir)).toBe('stale');
      expect(staleVerdictTarget(attack, tempDir)).toEqual({ path: 'linked/outside.md', reason: 'outside' });
    });

    it.each([
      ['target_sha256 без target', `target_sha256: ${'a'.repeat(64)}\n`, 'target'],
      ['targets не список', 'targets: design.md\n', 'targets'],
      ['запись targets без sha256', 'targets:\n  - path: design.md\n', 'targets[0]'],
      ['запись targets без path', `targets:\n  - sha256: ${'a'.repeat(64)}\n`, 'targets[0]'],
    ])('Вердикт с чужим хешем: неразборчивая цель (%s) — stale', (_label, fields, label) => {
      write('design.md', 'design\n');
      writeVerdict(`status: passed\n${fields}`);

      expect(verdictState(attack, tempDir)).toBe('stale');
      expect(staleVerdictTarget(attack, tempDir)).toEqual({ path: label, reason: 'malformed' });
    });

    it('Вердикт с чужим хешем: без полей хеша проверки нет — ok', () => {
      writeVerdict('status: passed\ntarget: decisions.json\n');

      expect(verdictState(attack, tempDir)).toBe('ok');
    });

    it('Вердикт с чужим хешем: значение не passed — mismatch, хеши не проверяются', () => {
      writeVerdict(`status: gaps_found\ntargets:\n  - path: design.md\n    sha256: ${sha('gone\n')}\n`);

      expect(verdictState(attack, tempDir)).toBe('mismatch');
      expect(staleVerdictTarget(attack, tempDir)).toBeUndefined();
    });

    it('Вердикт с чужим хешем: stale-артефакт не done, зависимые blocked', () => {
      write('design.md', 'design, edited\n');
      writeVerdict(`status: passed\ntargets:\n  - path: design.md\n    sha256: ${sha('design\n')}\n`);
      const g = ArtifactGraph.fromSchema(
        createSchema([
          attack,
          { id: 'next', generates: 'next.md', description: 'Next', template: 't.md', requires: ['attack'] },
        ])
      );
      const completed = detectCompleted(g, tempDir);

      expect(completed.has('attack')).toBe(false);
      expect(g.getNextArtifacts(completed)).toEqual(['attack']);
      expect(g.getBlocked(completed)).toEqual({ next: ['attack'] });
    });
  });

  // Fork (symphysis, C11): a stale verdict gates only until the next step has
  // begun - a file of an artifact that requires it, or (for an artifact nobody
  // requires but apply.requires names) a checked task in apply.tracks.
  describe('stale window', () => {
    const sha = (content: string): string => createHash('sha256').update(content).digest('hex');
    const write = (file: string, content: string): void => {
      fs.mkdirSync(path.dirname(path.join(tempDir, file)), { recursive: true });
      fs.writeFileSync(path.join(tempDir, file), content);
    };
    const verdict = { frontmatter: 'status', value: 'passed' };
    const graph = (): ArtifactGraph =>
      ArtifactGraph.fromSchema(
        createSchema([
          { id: 'journal', generates: 'journal.md', description: 'Journal', template: 't.md', requires: [] },
          {
            id: 'attack',
            generates: 'attack.md',
            description: 'Attack on the journal',
            template: 't.md',
            requires: ['journal'],
            optional: true,
            verdict,
          },
          {
            id: 'proposal',
            generates: 'proposal.md',
            description: 'Proposal',
            template: 't.md',
            requires: ['journal', 'attack'],
          },
          {
            id: 'notes',
            generates: 'notes/*.md',
            description: 'Notes',
            template: 't.md',
            requires: ['attack'],
          },
          { id: 'tasks', generates: 'tasks.md', description: 'Tasks', template: 't.md', requires: ['proposal'] },
          {
            id: 'review',
            generates: 'review.md',
            description: 'Review of the tasks',
            template: 't.md',
            requires: ['tasks'],
            optional: true,
            verdict,
          },
        ])
      );
    const APPLY = { requires: ['tasks', 'review'], tracks: 'tasks.md' };

    const staleAttack = (): void => {
      write('journal.md', '# Journal, edited after the attack\n');
      write('attack.md', `---\nstatus: passed\ntarget: journal.md\ntarget_sha256: ${sha('# Journal\n')}\n---\n`);
    };
    const staleReview = (tasks: string): void => {
      write('tasks.md', tasks);
      write(
        'review.md',
        `---\nstatus: passed\ntargets:\n  - path: tasks.md\n    sha256: ${sha('- [ ] 1.1 Work\n')}\n---\n`
      );
    };

    it('Окно устаревания: stale до файла зависимого — не сигнал, гейт', () => {
      staleAttack();

      expect(verdictState(graph().getArtifact('attack')!, tempDir)).toBe('stale');
      expect(detectStaleSignals(graph(), tempDir, APPLY).size).toBe(0);
    });

    it('Окно устаревания: файл зависимого есть — stale становится сигналом с именем зависимого', () => {
      staleAttack();
      write('proposal.md', '# Proposal\n');

      expect([...detectStaleSignals(graph(), tempDir, APPLY)]).toEqual([['attack', { dependent: 'proposal' }]]);
    });

    it('Окно устаревания: файл зависимого по glob тоже закрывает окно', () => {
      staleAttack();
      write('notes/one.md', '# Note\n');

      expect([...detectStaleSignals(graph(), tempDir, APPLY)]).toEqual([['attack', { dependent: 'notes' }]]);
    });

    it('Окно устаревания: mismatch после файла зависимого — не сигнал', () => {
      write('journal.md', '# Journal\n');
      write('attack.md', '---\nstatus: gaps_found\n---\n');
      write('proposal.md', '# Proposal\n');

      expect(detectStaleSignals(graph(), tempDir, APPLY).size).toBe(0);
    });

    it('Окно устаревания: артефакт без зависимых в apply.requires — гейт, пока нет отмеченной задачи', () => {
      staleReview('- [ ] 1.1 Work, edited\n- [ ] 1.2 More\n');

      expect(verdictState(graph().getArtifact('review')!, tempDir)).toBe('stale');
      expect(detectStaleSignals(graph(), tempDir, APPLY).size).toBe(0);
    });

    it('Окно устаревания: первая отмеченная задача в apply.tracks — сигнал', () => {
      staleReview('- [x] 1.1 Work\n- [ ] 1.2 More\n');

      expect([...detectStaleSignals(graph(), tempDir, APPLY)]).toEqual([['review', { tracks: 'tasks.md' }]]);
    });

    it('Окно устаревания: без apply.tracks окно не закрывается', () => {
      staleReview('- [x] 1.1 Work\n');

      expect(detectStaleSignals(graph(), tempDir, { requires: ['tasks', 'review'] }).size).toBe(0);
      expect(detectStaleSignals(graph(), tempDir, undefined).size).toBe(0);
    });

    it('Окно устаревания: артефакт без зависимых вне apply.requires — окно не закрывается', () => {
      staleReview('- [x] 1.1 Work\n');

      expect(detectStaleSignals(graph(), tempDir, { requires: ['tasks'], tracks: 'tasks.md' }).size).toBe(0);
    });
  });
});
