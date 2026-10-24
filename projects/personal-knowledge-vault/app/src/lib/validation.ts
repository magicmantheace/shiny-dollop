// Client-side validation for the note create/edit forms.
// Mirrors the server-side rules in spirit; the main process re-validates.

export interface NoteFormValues {
  title: string;
  body: string;
  tagsText: string;
  sourceTitle: string;
  sourceAuthor: string;
  sourceUrl: string;
  sourceDocPointer: string;
  sourceAccessedAt: string;
  changeSummary: string;
}

export interface FormErrors {
  [field: string]: string | undefined;
}

export const EMPTY_FORM: NoteFormValues = {
  title: '',
  body: '',
  tagsText: '',
  sourceTitle: '',
  sourceAuthor: '',
  sourceUrl: '',
  sourceDocPointer: '',
  sourceAccessedAt: '',
  changeSummary: '',
};

export function parseTags(text: string): string[] {
  return text
    .split(',')
    .map((t) => t.trim())
    .filter((t) => t.length > 0);
}

function isValidUrl(value: string): boolean {
  try {
    const u = new URL(value);
    return u.protocol === 'http:' || u.protocol === 'https:';
  } catch {
    return false;
  }
}

/**
 * Validate the note form. `requireChangeSummary` is true for the edit form
 * (a correction must say what changed); the create form does not ask for one.
 */
export function validateNoteForm(
  values: NoteFormValues,
  opts: { requireChangeSummary: boolean },
): FormErrors {
  const errors: FormErrors = {};
  if (values.title.trim().length === 0) {
    errors.title = 'Title is required.';
  }
  if (values.title.trim().length > 200) {
    errors.title = 'Title must be 200 characters or fewer.';
  }
  if (values.body.trim().length === 0) {
    errors.body = 'Body is required.';
  }
  if (values.sourceUrl.trim().length > 0 && !isValidUrl(values.sourceUrl.trim())) {
    errors.sourceUrl = 'Source URL must be a valid http(s) URL.';
  }
  if (opts.requireChangeSummary && values.changeSummary.trim().length === 0) {
    errors.changeSummary = 'A change summary is required so the correction stays auditable.';
  }
  return errors;
}

export function hasErrors(errors: FormErrors): boolean {
  return Object.values(errors).some((e) => e !== undefined && e.length > 0);
}
