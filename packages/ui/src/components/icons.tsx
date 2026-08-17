import type { ReactNode } from 'react';

interface IconProps {
  size?: number;
}

function Svg({ size = 18, children }: IconProps & { children: ReactNode }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {children}
    </svg>
  );
}

/** Tag-Cross mark (plan/09 §1.1 Option A) — tag body + pharmacy cross notch. */
export function TagCrossMark({ size = 32 }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" aria-hidden="true">
      <rect x="3" y="5" width="18" height="16" rx="3" fill="var(--accent-color)" />
      <path d="M3 5 h18 v4 h-18 z" fill="var(--accent-color)" opacity="0.35" />
      <path
        d="M9.5 9 h5 v2.5 H17 v5 h-2.5 V19 h-5 v-2.5 H7 v-5 h2.5 z"
        fill="var(--accent-contrast)"
      />
    </svg>
  );
}

export function HomeIcon(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="M4 10.5 12 4l8 6.5" />
      <path d="M6 9.5V20h12V9.5" />
      <path d="M10 20v-6h4v6" />
    </Svg>
  );
}

export function PillIcon(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="M7.5 5.5h9a2.5 2.5 0 0 1 0 5h-9a2.5 2.5 0 0 1 0-5Z" />
      <path d="m7 8 3 4" />
    </Svg>
  );
}

export function CashIcon(props: IconProps) {
  return (
    <Svg {...props}>
      <rect x="3" y="7" width="18" height="12" rx="2" />
      <circle cx="12" cy="13" r="2.5" />
      <path d="M6 11h.01M18 15h.01" />
    </Svg>
  );
}

export function CartIcon(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="M3 5h2l2.4 11.2a1.5 1.5 0 0 0 1.5 1.2H17a1.5 1.5 0 0 0 1.5-1.2L20 8H6" />
      <circle cx="10" cy="20" r="1" />
      <circle cx="17" cy="20" r="1" />
    </Svg>
  );
}

export function BoxIcon(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="m12 3 8 4v10l-8 4-8-4V7z" />
      <path d="m4 7 8 4 8-4M12 11v10" />
    </Svg>
  );
}

export function CoinsIcon(props: IconProps) {
  return (
    <Svg {...props}>
      <circle cx="9" cy="9" r="5" />
      <path d="M14 5.5a5 5 0 0 1 0 7M9 14v4.5M9 18.5h4M12 21h-2" />
    </Svg>
  );
}

export function ChartIcon(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="M4 20V4" />
      <path d="M4 20h16" />
      <path d="M8 16v-4M12 16V8M16 16v-6M20 16V6" />
    </Svg>
  );
}

export function UsersIcon(props: IconProps) {
  return (
    <Svg {...props}>
      <circle cx="9" cy="8" r="3" />
      <path d="M3.5 19a5.5 5.5 0 0 1 11 0" />
      <path d="M16 6a3 3 0 0 1 0 5M17.5 19a5.5 5.5 0 0 0-3-5" />
    </Svg>
  );
}

export function GearIcon(props: IconProps) {
  return (
    <Svg {...props}>
      <circle cx="12" cy="12" r="3" />
      <path d="M12 2v3M12 19v3M4.9 4.9l2.1 2.1M17 17l2.1 2.1M2 12h3M19 12h3M4.9 19.1 7 17M17 7l2.1-2.1" />
    </Svg>
  );
}
