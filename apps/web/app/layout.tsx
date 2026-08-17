import { THEME_BOOT_SCRIPT, ThemeProvider } from '@pharmatag/ui';
import type { Metadata } from 'next';
import Script from 'next/script';
import type { ReactNode } from 'react';
import '@pharmatag/ui/styles.css';
import './globals.css';

export const metadata: Metadata = {
  title: 'فارما تاج | PharmaTag',
  description: 'نظام إدارة الصيدليات — فارما تاج',
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="ar" dir="rtl" suppressHydrationWarning>
      <body>
        <Script id="theme-boot" strategy="beforeInteractive">
          {THEME_BOOT_SCRIPT}
        </Script>
        <ThemeProvider>{children}</ThemeProvider>
      </body>
    </html>
  );
}
