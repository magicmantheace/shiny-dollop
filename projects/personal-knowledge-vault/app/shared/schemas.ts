/**
 * zod schemas for every IPC payload. The main process validates all
 * incoming payloads with these before any database access, so the
 * renderer (untrusted side of the context bridge) cannot smuggle bad
 * shapes into the store.
 */
import { z } from 'zod';

const uuid = z.string().uuid({ message: 'Expected a UUID string.' });

export const noteStatusSchema = z.enum(['candidate', 'verified', 'rejected']);

const nonEmpty = (label: string) => z.string().trim().min(1, { message: `${label} must not be empty.` });

/** Tags are trimmed, deduplicated, and capped in length/count. */
const tagsSchema = z
  .array(z.string().trim().min(1).max(60))
  .max(50, { message: 'Too many tags (max 50).' })
  .default([]);

const sourceInputSchema = z
  .object({
    title: z.string().trim().max(300).optional(),
    author: z.string().trim().max(200).optional(),
    url: z.string().trim().max(2000).optional(),
    docPointer: z.string().trim().max(2000).optional(),
    accessedAt: z.string().trim().max(64).optional(),
  })
  .refine(
    (s) => Boolean(s.title?.trim() || s.url?.trim() || s.docPointer?.trim()),
    { message: 'Source needs at least one of: url, docPointer, title.' },
  );

export const createNoteSchema = z.object({
  title: nonEmpty('Title').max(300, { message: 'Title too long (max 300 chars).' }),
  body: z.string().max(200_000, { message: 'Body too long (max 200000 chars).' }).default(''),
  tags: tagsSchema,
  source: sourceInputSchema.optional(),
  links: z.array(uuid).max(100, { message: 'Too many links (max 100).' }).default([]),
});

export const updateNoteSchema = z.object({
  title: nonEmpty('Title').max(300).optional(),
  body: z.string().max(200_000).optional(),
  tags: tagsSchema.optional(),
  links: z.array(uuid).max(100).optional(),
  changeSummary: nonEmpty('Change summary'),
});

export const noteIdSchema = z.object({ id: uuid });

export const listNotesSchema = z.object({
  status: noteStatusSchema.optional(),
  tag: z.string().trim().min(1).max(60).optional(),
  sourceId: uuid.optional(),
});

export const searchNotesSchema = z.object({
  query: nonEmpty('Search query').max(500),
  status: noteStatusSchema.optional(),
  tag: z.string().trim().min(1).max(60).optional(),
});

export const approveNoteSchema = noteIdSchema;

export const rejectNoteSchema = z.object({
  id: uuid,
  reason: nonEmpty('Rejection reason').max(2000, { message: 'Reason too long (max 2000 chars).' }),
});

export const revisionsListSchema = z.object({ noteId: uuid });

export const backupImportSchema = z.object({
  json: z.string().min(1, { message: 'Import payload must not be empty.' }),
});

export const emptySchema = z.object({});

export type CreateNoteInput = z.infer<typeof createNoteSchema>;
export type UpdateNoteInput = z.infer<typeof updateNoteSchema>;
