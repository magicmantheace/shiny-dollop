/**
 * Theme registry: the four original BWG themes, keyed by theme id
 * (which matches the business type each theme is designed for).
 */
import type { BusinessType, ThemeInfo } from '../../../shared/types.js';
import { theme as trades } from './trades.js';
import { theme as author } from './author.js';
import { theme as restaurant } from './restaurant.js';
import { theme as localbiz } from './localbiz.js';
import type { ThemeModule } from './common.js';

export const THEMES: Record<string, ThemeModule> = {
  trades,
  author,
  restaurant,
  localbiz,
};

export function listThemes(): ThemeInfo[] {
  return Object.values(THEMES).map((t) => t.info);
}

export function getTheme(themeId: string): ThemeModule | undefined {
  return THEMES[themeId];
}

/** Themes compatible with a given business type. */
export function themesFor(businessType: BusinessType): ThemeInfo[] {
  return listThemes().filter((t) => t.businessTypes.includes(businessType));
}

export type { ThemeModule };
