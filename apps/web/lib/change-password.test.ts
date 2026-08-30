import { describe, expect, it } from 'vitest';
import { validateNewPassword } from './change-password';

describe('validateNewPassword', () => {
  it('accepts a strong new password that differs from the old', () => {
    expect(validateNewPassword('OldPass123', 'NewPass123!', 'NewPass123!')).toBeNull();
  });

  it('rejects empty fields', () => {
    expect(validateNewPassword('', 'NewPass123!', 'NewPass123!')).toBe('short');
    expect(validateNewPassword('OldPass123', '', '')).toBe('short');
  });

  it('enforces the 8-char minimum at the boundary', () => {
    expect(validateNewPassword('OldPass1', 'NewPass1', 'NewPass1')).toBeNull();
    expect(validateNewPassword('OldPass1', 'NewPass', 'NewPass')).toBe('short');
  });

  it('rejects a new password that exceeds the 72-byte bcrypt limit', () => {
    expect(validateNewPassword('OldPass123', 'a'.repeat(72), 'a'.repeat(72))).toBeNull();
    expect(validateNewPassword('OldPass123', 'a'.repeat(73), 'a'.repeat(73))).toBe('overlong');
  });

  it('rejects the weak default password', () => {
    expect(validateNewPassword('OldPass123', 'changeme', 'changeme')).toBe('weak');
  });

  it('rejects a new password equal to the old one', () => {
    expect(validateNewPassword('OldPass123', 'OldPass123', 'OldPass123')).toBe('same');
  });

  it('rejects a mismatched confirmation', () => {
    expect(validateNewPassword('OldPass123', 'NewPass123!', 'Different456!')).toBe('mismatch');
  });
});
