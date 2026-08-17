/**
 * SQLite bootstrap for the offline twin (plan/03 §4.1).
 *
 * The canonical `schema/schema_sqlite.sql` is bundled into the app bundle
 * (`src/resources/schema_sqlite.sql`, Vite `?raw`) and applied on first run.
 * The file is `BEGIN; ... COMMIT;`-wrapped with `--` comment lines; we split it
 * into individual statements and let tauri-plugin-sql execute them in order.
 */
export function splitStatements(sql: string): string[] {
  const withoutComments = sql
    .split('\n')
    .filter((line) => !line.trim().startsWith('--'))
    .join('\n');

  return withoutComments
    .split(';')
    .map((statement) => statement.trim())
    .filter((statement) => {
      if (statement.length === 0) return false;
      const lowered = statement.toLowerCase();
      return lowered !== 'begin' && lowered !== 'commit';
    });
}
