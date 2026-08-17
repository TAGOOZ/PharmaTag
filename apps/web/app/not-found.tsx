import { TagCrossMark } from '@pharmatag/ui';
import Link from 'next/link';

export default function NotFound() {
  return (
    <main className="flex min-h-dvh flex-col items-center justify-center gap-6 px-6 text-center">
      <TagCrossMark />
      <div>
        <h1 className="pt-title text-3xl">الصفحة غير موجودة</h1>
        <p className="pt-muted mt-2">Page not found</p>
      </div>
      <Link href="/" className="pt-link">
        العودة للرئيسية
      </Link>
    </main>
  );
}
