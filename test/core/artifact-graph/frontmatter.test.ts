import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import * as fs from 'node:fs';
import * as path from 'node:path';
import * as os from 'node:os';
import { readFrontmatter } from '../../../src/core/artifact-graph/frontmatter.js';

describe('artifact-graph/frontmatter', () => {
  let tempDir: string;
  let file: string;

  const write = (content: string): void => {
    fs.writeFileSync(file, content);
  };

  beforeEach(() => {
    tempDir = fs.mkdtempSync(path.join(os.tmpdir(), 'openspec-frontmatter-test-'));
    file = path.join(tempDir, 'doc.md');
  });

  afterEach(() => {
    fs.rmSync(tempDir, { recursive: true, force: true });
  });

  describe('readFrontmatter', () => {
    it('reads frontmatter with CRLF and BOM', () => {
      write('\uFEFF---\r\nstatus: passed\r\n---\r\n# t\r\n');

      expect(readFrontmatter(file)).toEqual({ status: 'passed' });
    });

    it('reads frontmatter with LF and no BOM', () => {
      write('---\nstatus: passed\nround: 2\n---\n# t\n');

      expect(readFrontmatter(file)).toEqual({ status: 'passed', round: 2 });
    });

    it('stops at the first closing fence and ignores later fences', () => {
      write('---\nstatus: passed\n---\nbody\n---\nstatus: other\n---\n');

      expect(readFrontmatter(file)).toEqual({ status: 'passed' });
    });

    it('accepts a closing fence at end of file without trailing newline', () => {
      write('---\nstatus: passed\n---');

      expect(readFrontmatter(file)).toEqual({ status: 'passed' });
    });

    it('returns null for a missing file', () => {
      expect(readFrontmatter(path.join(tempDir, 'nope.md'))).toBeNull();
    });

    it('returns null for a directory', () => {
      expect(readFrontmatter(tempDir)).toBeNull();
    });

    it('returns null for a file without the opening fence', () => {
      write('# title\n---\nstatus: passed\n---\n');

      expect(readFrontmatter(file)).toBeNull();
    });

    it('returns null for an empty file', () => {
      write('');

      expect(readFrontmatter(file)).toBeNull();
    });

    it('returns null for an unterminated block', () => {
      write('---\nstatus: passed\n# t\n');

      expect(readFrontmatter(file)).toBeNull();
    });

    it('returns null for an empty block', () => {
      write('---\n---\n# t\n');

      expect(readFrontmatter(file)).toBeNull();
    });

    it('returns null for a whitespace-only block', () => {
      write('---\n  \n\n---\n# t\n');

      expect(readFrontmatter(file)).toBeNull();
    });

    it('returns null for invalid YAML', () => {
      write('---\nstatus: [unclosed\n---\n# t\n');

      expect(readFrontmatter(file)).toBeNull();
    });

    it('returns null when the block is a scalar', () => {
      write('---\njust text\n---\n');

      expect(readFrontmatter(file)).toBeNull();
    });

    it('returns null when the block is a list', () => {
      write('---\n- a\n- b\n---\n');

      expect(readFrontmatter(file)).toBeNull();
    });
  });
});
