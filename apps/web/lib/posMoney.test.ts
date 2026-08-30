import { describe, expect, it } from 'vitest';
import {
  addDecimal,
  compareDecimal,
  isInRange,
  isMoneyValid,
  isNegative,
  isPositive,
  isQtyValid,
  isZero,
  normalizeDecimal,
  toFixed2,
  toFixed4,
} from './posMoney';

describe('normalizeDecimal', () => {
  it('strips Arabic digits and separators', () => {
    expect(normalizeDecimal('١٢٫٣٤')).toBe('12.34');
    expect(normalizeDecimal('۰۱۲٫۵۰')).toBe('012.50');
    expect(normalizeDecimal('1,000.50')).toBe('1000.50');
    expect(normalizeDecimal('1٬000٫50')).toBe('1000.50');
    expect(normalizeDecimal('1،000٫50')).toBe('1000.50');
    // NBSP/thin/regular space stripped (Excel paste "1 000" -> 1000)
    expect(normalizeDecimal('  1\u00A0\u202F 2 ')).toBe('12');
    expect(normalizeDecimal('1 000')).toBe('1000');
  });
  it('preserves leading dot for later handling', () => {
    expect(normalizeDecimal('.5')).toBe('.5');
    expect(normalizeDecimal(' .50 ')).toBe('.50');
  });
});

describe('isQtyValid / isMoneyValid', () => {
  it('allows leading .5 and caps decimals', () => {
    expect(isQtyValid('.5')).toBe(true);
    expect(isQtyValid('0.5')).toBe(true);
    expect(isQtyValid('1.2345')).toBe(true);
    expect(isQtyValid('1.23456')).toBe(false); // 5 decimals
    expect(isMoneyValid('.5')).toBe(true);
    expect(isMoneyValid('1.23')).toBe(true);
    expect(isMoneyValid('1.234')).toBe(false);
  });
  it('rejects e/x and limits int digits', () => {
    expect(isQtyValid('1e5')).toBe(false);
    expect(isQtyValid('1E5')).toBe(false);
    expect(isQtyValid('0x10')).toBe(false);
    expect(isMoneyValid('1e10')).toBe(false);
    // 16 int digits -> reject (max 15)
    expect(isQtyValid('9999999999999999')).toBe(false);
    expect(isQtyValid('999999999999999')).toBe(true); // 15
    expect(isMoneyValid('9999999999999999.99')).toBe(false);
    expect(isMoneyValid('999999999999999.99')).toBe(true);
  });
  it('rejects empty and huge paste', () => {
    expect(isQtyValid('')).toBe(false);
    expect(isMoneyValid('')).toBe(false);
    expect(isQtyValid('1'.repeat(21))).toBe(false);
  });
});

describe('toFixed helpers (string pad, half-up round)', () => {
  it('pads with half-up rounding (no Number drift)', () => {
    expect(toFixed4('.5')).toBe('0.5000');
    expect(toFixed4('1')).toBe('1.0000');
    expect(toFixed4('1.2')).toBe('1.2000');
    expect(toFixed4('1.23456')).toBe('1.2346'); // round half-up
    expect(toFixed2('.5')).toBe('0.50');
    expect(toFixed2('1.005')).toBe('1.01'); // round half-up (was truncate)
    expect(toFixed2('1.2')).toBe('1.20');
    expect(toFixed2('1.239')).toBe('1.24');
    // large stays exact
    expect(toFixed2('99999999999999.99')).toBe('99999999999999.99');
    expect(toFixed4('99999999999999.9999')).toBe('99999999999999.9999');
  });
});

describe('compareDecimal exact string comparison', () => {
  it('handles 0.10000000000000001 drift vs 0.1', () => {
    // Number("0.10000000000000001") === 0.1 in JS, but string compare sees difference
    expect(compareDecimal('0.10000000000000001', '0.1')).toBe(1);
    expect(compareDecimal('0.1', '0.10000000000000001')).toBe(-1);
    expect(Number('0.10000000000000001') === Number('0.1')).toBe(true); // drift existed
  });
  it('treats 0.1 and 0.10 as equal', () => {
    expect(compareDecimal('0.1', '0.10')).toBe(0);
    expect(compareDecimal('1.00', '1')).toBe(0);
    expect(compareDecimal('001.200', '1.2')).toBe(0);
  });
  it('handles leading .5 and negative', () => {
    expect(compareDecimal('.5', '0.5')).toBe(0);
    expect(compareDecimal('-.5', '-0.5')).toBe(0);
    expect(compareDecimal('-1', '0')).toBe(-1);
    expect(compareDecimal('0', '-0.00')).toBe(0);
  });
  it('handles large 99999999999999.99 exactly', () => {
    // Number loses precision beyond 2^53
    expect(Number('99999999999999.99') === Number('99999999999999.98')).toBe(true); // both round to same float
    expect(compareDecimal('99999999999999.99', '99999999999999.98')).toBe(1);
    expect(compareDecimal('99999999999999.98', '99999999999999.99')).toBe(-1);
    expect(compareDecimal('99999999999999.99', '99999999999999.99')).toBe(0);
    expect(compareDecimal('100000000000000', '99999999999999.99')).toBe(1);
  });
  it('orders fractional correctly', () => {
    expect(compareDecimal('1.005', '1.01')).toBe(-1);
    expect(compareDecimal('2.5', '2.50')).toBe(0);
    expect(compareDecimal('10.0000', '2')).toBe(1);
  });
});

describe('isZero/isPositive/isInRange', () => {
  it('isZero handles variants', () => {
    expect(isZero('0')).toBe(true);
    expect(isZero('0.00')).toBe(true);
    expect(isZero('000')).toBe(true);
    expect(isZero('0.0000')).toBe(true);
    expect(isZero('.00')).toBe(true);
    expect(isZero('0.0001')).toBe(false);
    expect(isZero('99999999999999.99')).toBe(false);
  });
  it('isPositive exact', () => {
    expect(isPositive('0')).toBe(false);
    expect(isPositive('0.00')).toBe(false);
    expect(isPositive('0.0001')).toBe(true);
    expect(isPositive('.5')).toBe(true);
    expect(isPositive('99999999999999.99')).toBe(true);
    expect(isPositive('0.10000000000000001')).toBe(true);
    // not using Number drift
    expect(isPositive('0')).toBe(false);
  });
  it('isNegative', () => {
    expect(isNegative('-1')).toBe(true);
    expect(isNegative('-0.01')).toBe(true);
    expect(isNegative('0')).toBe(false);
    expect(isNegative('-0.00')).toBe(false);
  });
  it('isInRange inclusive', () => {
    expect(isInRange('50', '0', '100')).toBe(true);
    expect(isInRange('0', '0', '100')).toBe(true);
    expect(isInRange('100', '0', '100')).toBe(true);
    expect(isInRange('100.00', '0', '100')).toBe(true);
    expect(isInRange('100.01', '0', '100')).toBe(false);
    expect(isInRange('-0.01', '0', '100')).toBe(false);
    expect(isInRange('0.10000000000000001', '0', '100')).toBe(true);
    expect(isInRange('99999999999999.99', '0', '99999999999999.99')).toBe(true);
    expect(isInRange('100000000000000', '0', '99999999999999.99')).toBe(false);
  });
});

describe('addDecimal exact', () => {
  it('adds 0.1+0.2 exactly 0.3 (no 0.300...04 drift)', () => {
    expect(addDecimal('0.1', '0.2')).toBe('0.3');
    expect(Number('0.1') + Number('0.2')).toBe(0.30000000000000004);
  });
  it('increments qty correctly', () => {
    expect(addDecimal('1', '1')).toBe('2');
    expect(addDecimal('1.5', '1')).toBe('2.5');
    expect(addDecimal('.5', '1')).toBe('1.5');
    expect(addDecimal('1.0000', '1')).toBe('2'); // trimmed
    expect(addDecimal('99999999999999.99', '0.01')).toBe('100000000000000');
  });
  it('handles large fractional', () => {
    expect(addDecimal('99999999999999.9999', '0.0001')).toBe('100000000000000');
  });
});
