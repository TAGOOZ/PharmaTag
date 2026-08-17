// @vitest-environment happy-dom

import { act, type ReactNode } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { beforeEach, describe, expect, it } from 'vitest';
import { DrugsPage } from './DrugsPage';

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

let host: HTMLDivElement;
let root: Root;

beforeEach(() => {
  host = document.createElement('div');
  document.body.appendChild(host);
  root = createRoot(host);
});

function render(node: ReactNode) {
  act(() => {
    root.render(node);
  });
}

describe('DrugsPage (desktop offline drugs screen)', () => {
  it('shows the read-error state instead of hanging when the db failed to open', () => {
    render(<DrugsPage db={null} />);
    expect(host.textContent).toContain('خطأ القراءة');
    expect(host.textContent).toContain('تعذّرت قراءة قائمة الأدوية');
    expect(host.textContent).not.toContain('جارٍ التحميل');
  });
});
