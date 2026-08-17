import { describe, expect, it } from 'vitest';
import { splitStatements } from './migrations';

describe('splitStatements (plan/03 §4.1: schema_sqlite.sql first-run bootstrap)', () => {
  const sample = [
    '-- header comment',
    '',
    'BEGIN;',
    '',
    'CREATE TABLE branches (',
    '    id INTEGER PRIMARY KEY AUTOINCREMENT,',
    "    pharname TEXT NOT NULL DEFAULT ''",
    ');',
    '',
    '-- money stays INTEGER minor units',
    'CREATE TABLE users (id INTEGER PRIMARY KEY);',
    '',
    'CREATE INDEX ix_users_id ON users (id);',
    '',
    'COMMIT;',
  ].join('\n');

  it('returns every real statement without the BEGIN/COMMIT wrappers', () => {
    const statements = splitStatements(sample);
    expect(statements).toHaveLength(3);
    expect(statements[0]).toContain('CREATE TABLE branches');
    expect(statements[1]).toContain('CREATE TABLE users');
    expect(statements[2]).toContain('CREATE INDEX');
  });

  it('strips comment lines and blank statements', () => {
    const statements = splitStatements(sample);
    for (const s of statements) {
      expect(s.trim().startsWith('--')).toBe(false);
      expect(s.trim().length).toBeGreaterThan(0);
    }
  });

  it('never emits the transaction wrapper tokens as standalone statements', () => {
    const statements = splitStatements(sample);
    for (const s of statements) {
      expect(s.toLowerCase()).not.toBe('begin');
      expect(s.toLowerCase()).not.toBe('commit');
    }
  });

  it('handles a schema with no statements', () => {
    expect(splitStatements('-- only a comment')).toEqual([]);
  });
});
