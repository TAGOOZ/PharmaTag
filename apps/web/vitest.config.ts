import { fileURLToPath } from 'node:url';
import { defineConfig } from 'vitest/config';

// apps/web overrides the base tsconfig with `jsx: preserve` (for Next.js);
// vitest must still transform JSX itself, so point rolldown at a test-only
// tsconfig that re-enables the automatic React runtime.
// apps/web overrides the base tsconfig with `jsx: preserve` (for Next.js);
// vitest's oxc transform must still compile JSX, so enable the automatic
// React runtime at the transform level (vite 8 reads `oxc` here).
const config = {
  oxc: {
    jsx: 'automatic',
  },
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('.', import.meta.url)),
    },
  },
  test: {
    environment: 'happy-dom',
    include: ['app/**/*.test.{ts,tsx}', 'lib/**/*.test.{ts,tsx}'],
  },
} as never;

export default defineConfig(config);
