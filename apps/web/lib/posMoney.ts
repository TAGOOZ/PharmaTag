export function errorForStatus(status: number, detail?: string): string {
  if (status === 400) {
    const d = (detail ?? '').toLowerCase();
    if (d.includes('discount exceeds')) return 'الخصم يتجاوز الإجمالي — قلّل نسبة الخصم';
    if (d.includes('credit limit exceeded')) return 'تجاوز حد الائتمان للعميل';
    if (d.includes('payment total does not match'))
      return 'إجمالي طرق الدفع لا يطابق إجمالي الفاتورة';
    if (d.includes('drug is inactive')) return 'الدواء غير نشط';
    if (d.includes('customer')) return 'العميل غير صالح';
    if (d.includes('qty must be positive')) return 'الكمية يجب أن تكون موجبة';
    if (
      d.includes('remaining') ||
      d.includes('exceeds remaining') ||
      d.includes('already returned')
    )
      return 'الكمية المتبقية للإرجاع غير كافية — تم إرجاع جزء منها سابقاً';
    if (d.includes('qty')) return 'خطأ في الكمية المدخلة';
    return 'خطأ في البيانات — تحقّق من الكميات والخصم وطريقة الدفع';
  }
  if (status === 401) return 'انتهت الجلسة — سجّل الدخول مجدداً';
  if (status === 403) return 'ليس لديك صلاحية إنشاء/عرض المبيعات (sale.create)';
  if (status === 404) return 'الدواء أو الفاتورة غير موجودة';
  if (status === 409) {
    const d = (detail ?? '').toLowerCase();
    if (d.includes('insufficient stock') || d.includes('no stock'))
      return 'الرصيد غير كافي — الكمية المطلوبة غير متوفرة';
    if (d.includes('already exists') || d.includes('duplicate'))
      return 'رقم الفاتورة مكرر — حاول مجدداً';
    return 'تعارض بالبيانات — الرصيد غير كافي أو العملية مكررة';
  }
  if (status === 0) return 'النافذة المنبثقة محجوبة — اسمح بالنوافذ المنبثقة للطباعة';
  if (status === 422) {
    const d = (detail ?? '').toLowerCase();
    if (d.includes('loc') || d.includes('msg') || d.includes('detail'))
      return 'بيانات غير صالحة — تحقّق من الحقول المطلوبة';
    return 'بيانات غير صالحة — تحقّق من الحقول المطلوبة';
  }
  if (status === 429) return 'كثرة الطلبات — حاول لاحقاً (429)';
  if (status === 415) return 'نوع المحتوى غير مدعوم (415)';
  if (status >= 500) return 'خطأ بالخادم — حاول لاحقاً';
  return `تعذّر إتمام العملية (HTTP ${status})`;
}

export function normalizeDecimal(raw: string): string {
  return raw
    .trim()
    .replace(/[\u00A0\u202F\u2009\u200A\u2002\u2003\u200C ]/g, '') // NBSP/thin/ZWNJ/regular space from Excel
    .replace(/[٬,،]/g, '') // thousands separators: Arabic thousands U+066C, comma, Arabic comma U+060C
    .replace(/٫/g, '.') // Arabic decimal separator
    .replace(/[٠-٩]/g, (c) => String(c.charCodeAt(0) - 0x0660))
    .replace(/[۰-۹]/g, (c) => String(c.charCodeAt(0) - 0x06f0));
}

export function isQtyValid(s: string): boolean {
  if (!s || s.length > 20) return false; // guard huge paste
  // allow .5 -> 0.5, reject e/x, cap 4 decimals, integer part <=15 digits (server max_digits 18)
  if (!/^(?:\d+(\.\d{1,4})?|\.\d{1,4})$/.test(s)) return false;
  const intPart = s.split('.')[0] ?? '';
  const digits = intPart.replace(/^0+/, '') || '0';
  if (digits.length > 15) return false;
  if (/[eExX]/.test(s)) return false;
  return true;
}

export function isMoneyValid(s: string): boolean {
  if (!s || s.length > 20) return false;
  if (!/^(?:\d+(\.\d{1,2})?|\.\d{1,2})$/.test(s)) return false;
  const intPart = s.split('.')[0] ?? '';
  const digits = intPart.replace(/^0+/, '') || '0';
  if (digits.length > 15) return false;
  if (/[eExX]/.test(s)) return false;
  return true;
}

function roundTo(s: string, n: number): string {
  const norm = s.startsWith('.') ? `0${s}` : s.startsWith('-.') ? `-0${s.slice(1)}` : s;
  const isNeg = norm.startsWith('-');
  const abs = isNeg ? norm.slice(1) : norm;
  const [iRaw, fRaw = ''] = abs.split('.');
  const i = iRaw || '0';
  const fPadded = `${fRaw}0000000000`.slice(0, n + 1);
  const keep = fPadded.slice(0, n).padEnd(n, '0');
  const roundDigit = Number(fPadded[n] ?? '0');
  if (roundDigit < 5) {
    return `${isNeg ? '-' : ''}${i}.${keep.padEnd(n, '0')}`.replace(/\.0+$/, (m) =>
      n === 0 ? '' : m,
    );
  }
  // need to round up keep
  let carry = 1;
  let newKeep = '';
  for (let k = n - 1; k >= 0; k--) {
    const d = Number(keep[k] ?? '0') + carry;
    carry = d >= 10 ? 1 : 0;
    newKeep = String(d % 10) + newKeep;
  }
  let newInt = i;
  if (carry) {
    newInt = (BigInt(i || '0') + 1n).toString();
    newKeep = '0'.repeat(n);
  } else {
    newKeep = newKeep.padStart(n, '0');
  }
  if (n === 0) return `${isNeg ? '-' : ''}${newInt}`;
  return `${isNeg ? '-' : ''}${newInt}.${newKeep}`;
}

export function toFixed4(s: string): string {
  return roundTo(s, 4);
}

export function toFixed2(s: string): string {
  return roundTo(s, 2);
}

// ---- exact-decimal helpers (string-based, no Number() drift) ----
type DecimalParts = { isNegative: boolean; intPart: string; fracPart: string };

function parseDecimalParts(raw: string): DecimalParts {
  let s = raw.trim();
  if (!s) return { isNegative: false, intPart: '0', fracPart: '' };
  let isNegative = false;
  if (s[0] === '-' || s[0] === '+') {
    isNegative = s[0] === '-';
    s = s.slice(1);
  }
  if (s.startsWith('.')) s = `0${s}`;
  // handle "-.5" already stripped sign -> ".5" -> "0.5"
  const dotIndex = s.indexOf('.');
  let intPart: string;
  let fracPart: string;
  if (dotIndex === -1) {
    intPart = s;
    fracPart = '';
  } else {
    intPart = s.slice(0, dotIndex);
    fracPart = s.slice(dotIndex + 1);
  }
  // keep only digits for parts (invalid chars become part of compare but should not happen for validated input)
  // normalize intPart leading zeros
  intPart = intPart.replace(/^0+/, '') || '0';
  // fracPart keep as-is (digits); don't strip trailing zeros here — caller decides
  // normalize -0 to +0
  if (intPart === '0' && /^0*$/.test(fracPart)) isNegative = false;
  return { isNegative, intPart, fracPart };
}

function compareMagnitude(a: DecimalParts, b: DecimalParts): number {
  if (a.intPart.length !== b.intPart.length) return a.intPart.length < b.intPart.length ? -1 : 1;
  if (a.intPart !== b.intPart) return a.intPart < b.intPart ? -1 : 1;
  const maxLen = Math.max(a.fracPart.length, b.fracPart.length);
  const af = a.fracPart.padEnd(maxLen, '0');
  const bf = b.fracPart.padEnd(maxLen, '0');
  if (af === bf) return 0;
  return af < bf ? -1 : 1;
}

export function compareDecimal(a: string, b: string): number {
  const pa = parseDecimalParts(a);
  const pb = parseDecimalParts(b);
  if (pa.isNegative !== pb.isNegative) return pa.isNegative ? -1 : 1;
  const cmp = compareMagnitude(pa, pb);
  if (cmp === 0) return 0;
  return pa.isNegative ? -cmp : cmp;
}

export function isZero(s: string): boolean {
  return compareDecimal(s, '0') === 0;
}

export function isPositive(s: string): boolean {
  return compareDecimal(s, '0') > 0;
}

export function isNegative(s: string): boolean {
  return compareDecimal(s, '0') < 0;
}

export function isInRange(s: string, min: string, max: string): boolean {
  return compareDecimal(s, min) >= 0 && compareDecimal(s, max) <= 0;
}

export function addDecimal(a: string, b: string): string {
  let aTrim = a.trim();
  let bTrim = b.trim();
  if (!aTrim) aTrim = '0';
  if (!bTrim) bTrim = '0';
  let aNeg = false;
  let bNeg = false;
  if (aTrim[0] === '-' || aTrim[0] === '+') {
    aNeg = aTrim[0] === '-';
    aTrim = aTrim.slice(1);
  }
  if (bTrim[0] === '-' || bTrim[0] === '+') {
    bNeg = bTrim[0] === '-';
    bTrim = bTrim.slice(1);
  }
  if (aTrim.startsWith('.')) aTrim = `0${aTrim}`;
  if (bTrim.startsWith('.')) bTrim = `0${bTrim}`;
  const aDot = aTrim.indexOf('.');
  const aIntRaw = aDot === -1 ? aTrim : aTrim.slice(0, aDot);
  const aFracRaw = aDot === -1 ? '' : aTrim.slice(aDot + 1);
  const bDot = bTrim.indexOf('.');
  const bIntRaw = bDot === -1 ? bTrim : bTrim.slice(0, bDot);
  const bFracRaw = bDot === -1 ? '' : bTrim.slice(bDot + 1);
  const maxFrac = Math.max(aFracRaw.length, bFracRaw.length);
  const aInt = (aIntRaw.replace(/^0+/, '') || '0') + aFracRaw.padEnd(maxFrac, '0');
  const bInt = (bIntRaw.replace(/^0+/, '') || '0') + bFracRaw.padEnd(maxFrac, '0');
  const aScaledStr = aInt.replace(/^0+/, '') || '0';
  const bScaledStr = bInt.replace(/^0+/, '') || '0';
  let aScaled = BigInt(aScaledStr);
  let bScaled = BigInt(bScaledStr);
  if (aNeg) aScaled = -aScaled;
  if (bNeg) bScaled = -bScaled;
  const sum = aScaled + bScaled;
  const isNeg = sum < 0n;
  const absStr = (isNeg ? (-sum).toString() : sum.toString()).padStart(maxFrac + 1, '0');
  let intPart: string;
  let fracPart: string;
  if (maxFrac === 0) {
    intPart = absStr;
    fracPart = '';
  } else {
    intPart = absStr.slice(0, -maxFrac) || '0';
    fracPart = absStr.slice(-maxFrac);
    intPart = intPart.replace(/^0+/, '') || '0';
    fracPart = fracPart.replace(/0+$/, '');
  }
  let result = fracPart ? `${intPart}.${fracPart}` : intPart;
  if (isNeg && result !== '0') result = `-${result}`;
  return result;
}
