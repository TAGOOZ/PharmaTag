import type { ReactNode } from 'react';

export type BadgeTone = 'low' | 'medium' | 'high' | 'neutral' | 'accent';

export interface BadgeProps {
  tone?: BadgeTone;
  title?: string;
  children: ReactNode;
}

export function Badge({ tone = 'neutral', title, children }: BadgeProps) {
  return (
    <span className={`pt-badge pt-badge--${tone}`} title={title}>
      {children}
    </span>
  );
}
