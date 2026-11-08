import { describe, expect, it } from 'vitest';
import type { Item } from '../../shared/types';
import {
  daysBetween,
  daysUntilWarrantyEnd,
  expiringWarranties,
  matchesSearch,
  parseDateStrict,
  warrantyStatus,
} from '../../engine/inventory';

function makeItem(overrides: Partial<Item> = {}): Item {
  return {
    id: '00000000-0000-4000-8000-000000000000',
    name: 'Test Item',
    category: 'Appliances',
    location: 'Kitchen',
    purchasePriceCents: null,
    purchaseDate: null,
    serialNumber: null,
    notes: '',
    warrantyStart: null,
    warrantyEnd: null,
    createdAt: '2026-01-01T00:00:00.000Z',
    updatedAt: '2026-01-01T00:00:00.000Z',
    ...overrides,
  };
}

describe('parseDateStrict', () => {
  it('accepts well-formed real dates', () => {
    expect(parseDateStrict('2024-02-29')).toBe('2024-02-29'); // leap day
    expect(parseDateStrict('2026-10-23')).toBe('2026-10-23');
    expect(parseDateStrict('2000-01-01')).toBe('2000-01-01');
  });

  it('rejects impossible calendar dates', () => {
    expect(parseDateStrict('2023-02-29')).toBeNull(); // not a leap year
    expect(parseDateStrict('2024-02-30')).toBeNull();
    expect(parseDateStrict('2026-13-01')).toBeNull();
    expect(parseDateStrict('2026-00-10')).toBeNull();
    expect(parseDateStrict('2026-04-31')).toBeNull();
  });

  it('rejects malformed shapes', () => {
    expect(parseDateStrict('not-a-date')).toBeNull();
    expect(parseDateStrict('2026-1-1')).toBeNull();
    expect(parseDateStrict('2026/10/23')).toBeNull();
    expect(parseDateStrict('')).toBeNull();
    expect(parseDateStrict(' 2026-10-23')).toBeNull();
  });
});

describe('daysBetween', () => {
  it('counts whole days between UTC calendar dates', () => {
    expect(daysBetween('2026-10-23', '2026-10-23')).toBe(0);
    expect(daysBetween('2026-10-23', '2026-10-24')).toBe(1);
    expect(daysBetween('2026-10-24', '2026-10-23')).toBe(-1);
    expect(daysBetween('2024-02-28', '2024-03-01')).toBe(2); // across leap day
    expect(daysBetween('2023-02-28', '2023-03-01')).toBe(1);
    expect(daysBetween('2026-01-01', '2026-12-31')).toBe(364);
  });

  it('throws on invalid dates', () => {
    expect(() => daysBetween('2023-02-29', '2026-01-01')).toThrow();
  });
});

describe('daysUntilWarrantyEnd', () => {
  it('handles the boundary dates', () => {
    expect(daysUntilWarrantyEnd('2026-10-23', '2026-10-23')).toBe(0); // today
    expect(daysUntilWarrantyEnd('2026-10-24', '2026-10-23')).toBe(1); // tomorrow
    expect(daysUntilWarrantyEnd('2026-10-22', '2026-10-23')).toBe(-1); // yesterday
  });
});

describe('warrantyStatus', () => {
  const today = '2026-10-23';
  const within = 90;

  it('returns none when there is no warranty end', () => {
    expect(warrantyStatus(null, today, within)).toBe('none');
  });

  it('marks yesterday as expired and today as expiring', () => {
    expect(warrantyStatus('2026-10-22', today, within)).toBe('expired');
    expect(warrantyStatus('2026-10-23', today, within)).toBe('expiring');
  });

  it('marks tomorrow as expiring', () => {
    expect(warrantyStatus('2026-10-24', today, within)).toBe('expiring');
  });

  it('respects the withinDays boundary exactly', () => {
    expect(warrantyStatus('2027-01-21', today, within)).toBe('expiring'); // today + 90
    expect(warrantyStatus('2027-01-22', today, within)).toBe('active'); // today + 91
  });
});

describe('expiringWarranties', () => {
  const today = '2026-10-23';

  it('includes expired + expiring, excludes active and none, sorts by daysLeft then name', () => {
    const items = [
      makeItem({ id: 'a', name: 'Zulu Toaster', warrantyEnd: '2026-10-28' }), // +5
      makeItem({ id: 'b', name: 'Alpha Fridge', warrantyEnd: '2026-10-20' }), // -3 expired
      makeItem({ id: 'c', name: 'Beta Mixer', warrantyEnd: '2026-10-28' }), // +5, name sorts first
      makeItem({ id: 'd', name: 'Far Oven', warrantyEnd: '2028-01-01' }), // active
      makeItem({ id: 'e', name: 'No Warranty Lamp', warrantyEnd: null }), // none
    ];
    const result = expiringWarranties(items, 90, today);
    expect(result.map((r) => r.item.id)).toEqual(['b', 'c', 'a']);
    expect(result[0]).toMatchObject({ daysLeft: -3, status: 'expired' });
    expect(result[1]).toMatchObject({ daysLeft: 5, status: 'expiring' });
    expect(result[2]).toMatchObject({ daysLeft: 5, status: 'expiring' });
  });

  it('returns an empty list when nothing needs attention', () => {
    const items = [
      makeItem({ warrantyEnd: '2028-01-01' }),
      makeItem({ warrantyEnd: null }),
    ];
    expect(expiringWarranties(items, 90, today)).toEqual([]);
  });
});

describe('matchesSearch', () => {
  const item = makeItem({
    name: 'KitchenAid Mixer',
    category: 'Appliances',
    location: 'Pantry Shelf',
    serialNumber: 'KM-8842-X',
    notes: 'Bought during the spring sale',
  });

  it('matches case-insensitively across every searchable field', () => {
    expect(matchesSearch(item, 'kitchenaid')).toBe(true);
    expect(matchesSearch(item, 'APPLIANCES')).toBe(true);
    expect(matchesSearch(item, 'pantry shelf')).toBe(true);
    expect(matchesSearch(item, 'km-8842')).toBe(true);
    expect(matchesSearch(item, 'SPRING SALE')).toBe(true);
  });

  it('matches a blank query and rejects non-matches', () => {
    expect(matchesSearch(item, '')).toBe(true);
    expect(matchesSearch(item, '   ')).toBe(true);
    expect(matchesSearch(item, 'blender')).toBe(false);
    expect(matchesSearch(item, 'km-8843')).toBe(false);
  });
});
