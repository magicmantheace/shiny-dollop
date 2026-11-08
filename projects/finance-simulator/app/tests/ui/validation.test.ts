import { describe, expect, it } from 'vitest';
import {
  validateDebt,
  validateExtraPayment,
  validateIncome,
} from '../../renderer/src/lib/validation';

describe('validateDebt', () => {
  const valid = { name: 'Visa', balance: '5000.00', apr: '9.94', minimum: '125.00' };

  it('accepts a fully valid debt', () => {
    expect(validateDebt(valid)).toEqual({});
  });
  it('requires a name', () => {
    expect(validateDebt({ ...valid, name: '  ' }).name).toBeDefined();
  });
  it('rejects a zero balance? (balance must be >= 0, zero is allowed)', () => {
    expect(validateDebt({ ...valid, balance: '0' })).toEqual({});
  });
  it('rejects malformed balance', () => {
    expect(validateDebt({ ...valid, balance: 'abc' }).balance).toBeDefined();
  });
  it('rejects APR above 100 and below 0', () => {
    expect(validateDebt({ ...valid, apr: '101' }).apr).toBeDefined();
    expect(validateDebt({ ...valid, apr: '-1' }).apr).toBeDefined();
  });
  it('accepts boundary APRs 0 and 100', () => {
    expect(validateDebt({ ...valid, apr: '0' }).apr).toBeUndefined();
    expect(validateDebt({ ...valid, apr: '100' }).apr).toBeUndefined();
  });
  it('rejects malformed minimum payment', () => {
    expect(validateDebt({ ...valid, minimum: 'ten' }).minimum).toBeDefined();
  });
});

describe('validateIncome', () => {
  it('accepts valid income', () => {
    expect(validateIncome({ name: 'Paycheck', amount: '1557.51', frequency: 'biweekly' })).toEqual({});
  });
  it('requires a name', () => {
    expect(validateIncome({ name: '', amount: '100', frequency: 'monthly' }).name).toBeDefined();
  });
  it('rejects malformed amount', () => {
    expect(validateIncome({ name: 'X', amount: 'x', frequency: 'monthly' }).amount).toBeDefined();
  });
  it('rejects unknown frequency', () => {
    expect(validateIncome({ name: 'X', amount: '100', frequency: 'fortnightly' }).frequency).toBeDefined();
  });
});

describe('validateExtraPayment', () => {
  it('allows blank (means zero)', () => {
    expect(validateExtraPayment('')).toBeUndefined();
  });
  it('accepts a valid amount', () => {
    expect(validateExtraPayment('100.00')).toBeUndefined();
  });
  it('rejects garbage', () => {
    expect(validateExtraPayment('lots')).toBeDefined();
  });
});
