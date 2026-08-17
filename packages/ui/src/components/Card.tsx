import type { HTMLAttributes, ReactNode } from 'react';

export interface CardProps extends HTMLAttributes<HTMLDivElement> {
  children: ReactNode;
}

export function Card({ className, children, ...rest }: CardProps) {
  return (
    <div className={`pt-card${className ? ` ${className}` : ''}`} {...rest}>
      {children}
    </div>
  );
}
