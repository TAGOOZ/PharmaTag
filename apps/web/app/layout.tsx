import { ThemeProvider } from '@pharmatag/ui';
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
          {`(function(){try{var s=localStorage.getItem('pharmatag:theme');var t=s==='dark'||s==='light'?s:window.matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light';document.documentElement.setAttribute('data-theme',t);}catch(e){}})();`}
        </Script>
        <ThemeProvider>{children}</ThemeProvider>
      </body>
    </html>
  );
}
