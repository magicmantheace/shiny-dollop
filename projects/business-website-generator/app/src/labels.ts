import type { BusinessProfile, BusinessType } from '../shared/types';

/** Human-readable labels for the four business types. */
export const BUSINESS_TYPE_LABELS: Record<BusinessType, string> = {
  trades: 'Trades & Contractors',
  author: 'Author',
  restaurant: 'Restaurant',
  localbiz: 'Local Business',
};

/** Human-readable labels for the contact fields, used in hints and errors. */
export const CONTACT_FIELD_LABELS: Record<keyof BusinessProfile['contact'], string> = {
  phone: 'Phone',
  email: 'Email',
  address: 'Address',
  website: 'Website',
};
