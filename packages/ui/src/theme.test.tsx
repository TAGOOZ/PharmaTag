// @vitest-environment happy-dom

import { act, type ReactNode } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { beforeEach, describe, expect, it } from 'vitest';
import { ThemeProvider, ThemeToggle } from './theme';

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

let host: HTMLDivElement;
let root: Root;

beforeEach(() => {
  window.localStorage.clear();
  document.documentElement.removeAttribute('data-theme');
  host = document.createElement('div');
  document.body.appendChild(host);
  root = createRoot(host);
});

function render(node: ReactNode) {
  act(() => {
    root.render(node);
  });
}

function buttonByText(text: string): HTMLButtonElement {
  const button = [...host.querySelectorAll('button')].find((b) => b.textContent?.trim() === text);
  if (!button) throw new Error(`no button with text "${text}"`);
  return button as HTMLButtonElement;
}

function installControllableMatchMedia(): { setDark(dark: boolean): void } {
  const listeners = new Set<(e: MediaQueryListEvent) => void>();
  const state = { matches: false };
  const query = {
    get matches() {
      return state.matches;
    },
    media: '(prefers-color-scheme: dark)',
    onchange: null,
    addEventListener: (_: string, cb: (e: MediaQueryListEvent) => void) => listeners.add(cb),
    removeEventListener: (_: string, cb: (e: MediaQueryListEvent) => void) => listeners.delete(cb),
    addListener: () => {},
    removeListener: () => {},
    dispatchEvent: () => false,
  } as unknown as MediaQueryList;
  window.matchMedia = () => query;
  return {
    setDark(dark: boolean) {
      state.matches = dark;
      listeners.forEach((cb) => {
        cb({ matches: dark } as MediaQueryListEvent);
      });
    },
  };
}

describe('ThemeProvider + ThemeToggle (plan/09 §4.2 through the public interface)', () => {
  it('applies light on <html> by default (P02: light is the brand default)', () => {
    render(
      <ThemeProvider>
        <div />
      </ThemeProvider>,
    );
    expect(document.documentElement.dataset.theme).toBe('light');
  });

  it('switches to dark and persists the choice when the user picks dark', () => {
    render(
      <ThemeProvider>
        <ThemeToggle />
      </ThemeProvider>,
    );
    act(() => buttonByText('داكن').click());
    expect(document.documentElement.dataset.theme).toBe('dark');
    expect(window.localStorage.getItem('pharmatag:theme')).toBe('dark');
  });

  it('honours a stored dark choice on next load (no flash back to light)', () => {
    window.localStorage.setItem('pharmatag:theme', 'dark');
    render(
      <ThemeProvider>
        <div />
      </ThemeProvider>,
    );
    expect(document.documentElement.dataset.theme).toBe('dark');
  });

  it('follows the OS preference when the setting is system', () => {
    const realMatchMedia = window.matchMedia.bind(window);
    window.matchMedia = () =>
      ({
        matches: true,
        media: '(prefers-color-scheme: dark)',
        onchange: null,
        addEventListener: () => {},
        removeEventListener: () => {},
        addListener: () => {},
        removeListener: () => {},
        dispatchEvent: () => false,
      }) as MediaQueryList;

    try {
      window.localStorage.setItem('pharmatag:theme', 'system');
      render(
        <ThemeProvider>
          <div />
        </ThemeProvider>,
      );
      expect(document.documentElement.dataset.theme).toBe('dark');
    } finally {
      window.matchMedia = realMatchMedia;
    }
  });

  it('re-resolves at runtime when the OS preference changes while setting=system', () => {
    const realMatchMedia = window.matchMedia.bind(window);
    const mq = installControllableMatchMedia();
    try {
      window.localStorage.setItem('pharmatag:theme', 'system');
      render(
        <ThemeProvider>
          <div />
        </ThemeProvider>,
      );
      expect(document.documentElement.dataset.theme).toBe('light');
      act(() => mq.setDark(true));
      expect(document.documentElement.dataset.theme).toBe('dark');
      act(() => mq.setDark(false));
      expect(document.documentElement.dataset.theme).toBe('light');
    } finally {
      window.matchMedia = realMatchMedia;
    }
  });

  it('keeps multiple toggles in sync with the shared setting', () => {
    render(
      <ThemeProvider>
        <ThemeToggle />
        <ThemeToggle />
      </ThemeProvider>,
    );
    const darkButtons = [...host.querySelectorAll('button')].filter(
      (b) => b.textContent?.trim() === 'داكن',
    );
    expect(darkButtons.length).toBe(2);
    act(() => darkButtons[0]?.click());
    expect(darkButtons.every((b) => b.getAttribute('aria-pressed') === 'true')).toBe(true);
    expect(document.documentElement.dataset.theme).toBe('dark');
    expect(window.localStorage.getItem('pharmatag:theme')).toBe('dark');
  });

  it('falls back to light (P02) for an unknown stored value — never the OS flash', () => {
    window.localStorage.setItem('pharmatag:theme', 'rainbow');
    render(
      <ThemeProvider>
        <div />
      </ThemeProvider>,
    );
    expect(document.documentElement.dataset.theme).toBe('light');
  });
});
