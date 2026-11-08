/**
 * Zod schemas for window.bwg IPC arguments.
 * Shared so the renderer can reuse them for client-side validation.
 */
import { z } from 'zod';

export const businessTypeSchema = z.enum(['trades', 'author', 'restaurant', 'localbiz']);

export const newSiteInputSchema = z.object({
  name: z.string().trim().min(1, 'name is required').max(200),
  businessType: businessTypeSchema,
  themeId: z.string().trim().min(1).max(100),
});

export const siteIdSchema = z.string().trim().min(1).max(100);

const serviceItemSchema = z.object({
  title: z.string().max(200),
  description: z.string().max(2000),
});

const menuItemSchema = z.object({
  name: z.string().max(200),
  description: z.string().max(2000),
  price: z.string().max(50),
});

const menuSectionSchema = z.object({
  name: z.string().max(200),
  items: z.array(menuItemSchema).max(100),
});

const socialLinkSchema = z.object({
  label: z.string().max(100),
  url: z.string().max(500),
});

/** Partial profile patch for sites.updateProfile: nested objects merge, arrays replace. */
export const businessProfilePatchSchema = z.object({
  name: z.string().max(200).optional(),
  tagline: z.string().max(300).optional(),
  about: z.string().max(10000).optional(),
  contact: z
    .object({
      phone: z.string().max(50).optional(),
      email: z.string().max(200).optional(),
      address: z.string().max(500).optional(),
      website: z.string().max(500).optional(),
    })
    .optional(),
  hours: z
    .object({
      label: z.string().max(100).optional(),
      lines: z.array(z.string().max(200)).max(30).optional(),
    })
    .optional(),
  services: z.array(serviceItemSchema).max(100).optional(),
  menuSections: z.array(menuSectionSchema).max(30).optional(),
  social: z.array(socialLinkSchema).max(30).optional(),
  seo: z
    .object({
      title: z.string().max(200).optional(),
      description: z.string().max(500).optional(),
    })
    .optional(),
});

export const setThemeSchema = z.object({
  id: siteIdSchema,
  themeId: z.string().trim().min(1).max(100),
});

export const exportRunSchema = z.object({
  id: siteIdSchema,
  destDir: z.string().trim().min(1).max(2000),
});
