import { describe, expect, it } from 'vitest';
import {
  fieldToSectionId,
  isValidEmail,
  isValidPhone,
  isValidUrl,
  validateOptionalEmail,
  validateOptionalPhone,
  validateOptionalUrl,
  validateRequiredName,
} from '../../src/validation';

describe('editor validation', () => {
  it('blocks bad emails', () => {
    expect(validateOptionalEmail('not-an-email')).not.toBeNull();
    expect(validateOptionalEmail('missing@domain')).not.toBeNull();
    expect(validateOptionalEmail('a@b')).not.toBeNull();
    expect(validateOptionalEmail('user name@example.com')).not.toBeNull();
    expect(isValidEmail('not-an-email')).toBe(false);
  });

  it('accepts good emails and empty (optional) emails', () => {
    expect(validateOptionalEmail('')).toBeNull();
    expect(validateOptionalEmail('   ')).toBeNull();
    expect(validateOptionalEmail('hello@example.com')).toBeNull();
    expect(validateOptionalEmail('first.last+tag@sub.example.co')).toBeNull();
  });

  it('blocks URLs that do not start with http(s)://', () => {
    expect(validateOptionalUrl('example.com')).not.toBeNull();
    expect(validateOptionalUrl('ftp://example.com')).not.toBeNull();
    expect(validateOptionalUrl('www.example.com/page')).not.toBeNull();
    expect(isValidUrl('example.com')).toBe(false);
  });

  it('accepts http/https URLs and empty URLs', () => {
    expect(validateOptionalUrl('')).toBeNull();
    expect(validateOptionalUrl('http://example.com')).toBeNull();
    expect(validateOptionalUrl('https://example.com/page?q=1')).toBeNull();
  });

  it('blocks malformed phone numbers but stays loose', () => {
    expect(validateOptionalPhone('abc-defg')).not.toBeNull();
    expect(validateOptionalPhone('123')).not.toBeNull(); // too few digits
    expect(validateOptionalPhone('555-01!23')).not.toBeNull();
    expect(isValidPhone('nope')).toBe(false);
  });

  it('accepts common phone formats and empty phones', () => {
    expect(validateOptionalPhone('')).toBeNull();
    expect(validateOptionalPhone('+1 403-555-0123')).toBeNull();
    expect(validateOptionalPhone('(403) 555-0123')).toBeNull();
    expect(validateOptionalPhone('403.555.0123')).toBeNull();
  });

  it('requires a site name', () => {
    expect(validateRequiredName('')).not.toBeNull();
    expect(validateRequiredName('   ')).not.toBeNull();
    expect(validateRequiredName('Acme Plumbing')).toBeNull();
  });

  it('maps issue fields to editor sections', () => {
    expect(fieldToSectionId('profile.contact.email')).toBe('section-contact');
    expect(fieldToSectionId('profile.seo.title')).toBe('section-seo');
    expect(fieldToSectionId('profile.services[0].title')).toBe('section-services');
    expect(fieldToSectionId('profile.menuSections')).toBe('section-menu');
    expect(fieldToSectionId('profile.hours.lines')).toBe('section-hours');
    expect(fieldToSectionId('profile.social[1].url')).toBe('section-social');
    expect(fieldToSectionId('profile.name')).toBe('section-identity');
    expect(fieldToSectionId(undefined)).toBe('section-identity');
  });
});
