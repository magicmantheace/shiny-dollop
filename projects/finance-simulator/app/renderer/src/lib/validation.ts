// Pure validation helpers for the Debts and Income forms.
// Each returns a field-keyed error map; an empty object means valid.

import { dollarsToCents } from './money';
import { INCOME_FREQUENCIES, type IncomeFrequency } from '../types';

export interface DebtFormErrors {
  name?: string;
  balance?: string;
  apr?: string;
  minimum?: string;
}

export interface DebtFormValues {
  name: string;
  balance: string; // dollars as typed
  apr: string; // percent as typed, e.g. "9.94"
  minimum: string; // dollars as typed
}

export function validateDebt(values: DebtFormValues): DebtFormErrors {
  const errors: DebtFormErrors = {};

  if (values.name.trim() === '') {
    errors.name = 'Name is required.';
  }

  const balanceCents = dollarsToCents(values.balance);
  if (balanceCents === null) {
    errors.balance = 'Enter a valid balance, e.g. 5000.00.';
  }

  const apr = Number(values.apr.trim());
  if (values.apr.trim() === '' || !Number.isFinite(apr)) {
    errors.apr = 'Enter a valid APR, e.g. 9.94.';
  } else if (apr < 0 || apr > 100) {
    errors.apr = 'APR must be between 0 and 100.';
  }

  const minCents = dollarsToCents(values.minimum);
  if (minCents === null) {
    errors.minimum = 'Enter a valid minimum payment, e.g. 125.00.';
  }

  return errors;
}

export interface IncomeFormErrors {
  name?: string;
  amount?: string;
  frequency?: string;
}

export interface IncomeFormValues {
  name: string;
  amount: string; // dollars as typed
  frequency: string;
}

export function isIncomeFrequency(value: string): value is IncomeFrequency {
  return (INCOME_FREQUENCIES as string[]).includes(value);
}

export function validateIncome(values: IncomeFormValues): IncomeFormErrors {
  const errors: IncomeFormErrors = {};

  if (values.name.trim() === '') {
    errors.name = 'Name is required.';
  }

  const amountCents = dollarsToCents(values.amount);
  if (amountCents === null) {
    errors.amount = 'Enter a valid amount, e.g. 1557.51.';
  }

  if (!isIncomeFrequency(values.frequency)) {
    errors.frequency = 'Choose a frequency.';
  }

  return errors;
}

/** Validate the extra-monthly-payment simulator input. Returns an error string or undefined. */
export function validateExtraPayment(value: string): string | undefined {
  if (value.trim() === '') return undefined; // blank means zero
  const cents = dollarsToCents(value);
  if (cents === null) return 'Enter a valid extra payment, e.g. 100.00.';
  return undefined;
}
