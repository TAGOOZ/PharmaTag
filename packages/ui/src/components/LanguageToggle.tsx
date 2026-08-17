'use client';

import { useState } from 'react';
import { applyLanguage, getDir } from '../rtl';

export interface LanguageToggleProps {
  /** Active language code (default: Arabic — plan/09 §4.3). */
  defaultLang?: 'ar' | 'en';
  /** Injectable target (document) for tests. */
  target?: { lang: string; dir: 'rtl' | 'ltr' };
}

/**
 * Bilingual flip (plan/09 P06): Arabic/RTL is the structural default; English
 * is a mirrored display mode switched by swapping dir/lang on <html>.
 */
export function LanguageToggle({ defaultLang = 'ar', target }: LanguageToggleProps) {
  const [lang, setLang] = useState<'ar' | 'en'>(() => {
    const current = target?.lang ?? document.documentElement.lang;
    return (current === 'en' ? 'en' : defaultLang) as 'ar' | 'en';
  });

  const flip = () => {
    const next = lang === 'ar' ? 'en' : 'ar';
    setLang(next);
    applyLanguage(target ?? document.documentElement, next);
  };

  return (
    <button
      type="button"
      className="pt-lang-button"
      title={lang === 'ar' ? 'English' : 'العربية'}
      onClick={flip}
    >
      {lang === 'ar' ? 'EN' : 'ع'}
    </button>
  );
}

export { getDir };
