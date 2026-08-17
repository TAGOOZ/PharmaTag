import { renderToString } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import { ThemeProvider } from './theme';

describe('ThemeProvider SSR (no window/document — node environment)', () => {
  it('renders the tree without throwing', () => {
    const html = renderToString(
      <ThemeProvider>
        <div>content</div>
      </ThemeProvider>,
    );
    expect(html).toContain('content');
  });

  it('never touches a document or localStorage during render', () => {
    expect(typeof window).toBe('undefined');
    expect(typeof document).toBe('undefined');
    const html = renderToString(
      <ThemeProvider initialSetting="dark">
        <p>ssr-safe</p>
      </ThemeProvider>,
    );
    expect(html).toContain('ssr-safe');
  });
});
