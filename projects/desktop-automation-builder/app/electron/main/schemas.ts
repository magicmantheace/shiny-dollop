// Zod schemas for every IPC input. All renderer-supplied data is validated
// in the main process before it touches the store or the executor.
import { z } from 'zod';

const stepBase = z.object({
  id: z.string().min(1).max(200),
  label: z.string().min(1).max(500),
});

const pathField = z.string().min(1).max(4096);

export const fileCopyStepSchema = stepBase.extend({
  kind: z.literal('file-copy'),
  from: pathField,
  to: pathField,
});

export const fileMoveToTrashStepSchema = stepBase.extend({
  kind: z.literal('file-move-to-trash'),
  path: pathField,
});

export const folderCreateStepSchema = stepBase.extend({
  kind: z.literal('folder-create'),
  path: pathField,
});

export const runApprovedScriptStepSchema = stepBase.extend({
  kind: z.literal('run-approved-script'),
  scriptId: z.string().min(1).max(200),
  args: z.array(z.string().max(4096)).max(64),
});

export const logMessageStepSchema = stepBase.extend({
  kind: z.literal('log-message'),
  message: z.string().min(1).max(10000),
});

export const stepSchema = z.discriminatedUnion('kind', [
  fileCopyStepSchema,
  fileMoveToTrashStepSchema,
  folderCreateStepSchema,
  runApprovedScriptStepSchema,
  logMessageStepSchema,
]);

export const stepsSchema = z
  .array(stepSchema)
  .max(500)
  .superRefine((steps, ctx) => {
    // Step IDs must be unique within a workflow. Steps are addressed by
    // ID when a failed run is retried (`retryRun` resumes at the step
    // whose ID matches the failed step log), so a duplicate ID makes the
    // resume position ambiguous — the first match wins and a later step
    // with the same ID could be skipped or re-run. Reject duplicates at
    // this shared schema so EVERY persistence path (workflow update and
    // import alike) is covered before anything is written.
    const seen = new Map<string, number>();
    steps.forEach((step, index) => {
      const firstIndex = seen.get(step.id);
      if (firstIndex !== undefined) {
        ctx.addIssue({
          code: 'custom',
          message: `Duplicate step id "${step.id}" (steps ${firstIndex} and ${index}); step ids must be unique within a workflow.`,
          path: [index, 'id'],
        });
      } else {
        seen.set(step.id, index);
      }
    });
  });

const workflowIdSchema = z.string().min(1).max(200);
const nonEmptyName = z.string().trim().min(1).max(200);

export const workflowsCreateSchema = z.tuple([nonEmptyName, z.string().trim().min(1).max(4096)]);

export const workflowsGetSchema = z.tuple([workflowIdSchema]);
export const workflowsDeleteSchema = z.tuple([workflowIdSchema]);
export const workflowsExportSchema = z.tuple([workflowIdSchema]);

export const workflowsUpdateSchema = z.tuple([
  workflowIdSchema,
  z
    .object({
      name: nonEmptyName.optional(),
      sandboxRoot: z.string().trim().min(1).max(4096).optional(),
      steps: stepsSchema.optional(),
    })
    .strict(),
]);

const importWorkflowSchema = z
  .object({
    id: z.string().optional(),
    name: nonEmptyName,
    sandboxRoot: z.string().trim().min(1).max(4096),
    steps: stepsSchema,
    version: z.number().int().min(1).optional(),
  })
  .strict();

export const importEnvelopeSchema = z
  .object({
    formatVersion: z.string().min(1).max(32),
    exportedAt: z.string().min(1).max(64),
    workflow: importWorkflowSchema,
  })
  .strict();

export const workflowsImportSchema = z.tuple([z.string().min(1).max(10_000_000)]);

export const scriptsRegisterSchema = z.tuple([nonEmptyName, z.string().trim().min(1).max(4096)]);

export const scriptIdSchema = z.tuple([z.string().min(1).max(200)]);

export const runsPreviewSchema = z.tuple([workflowIdSchema]);

export const runsStartSchema = z.tuple([workflowIdSchema, z.boolean()]);

export const runIdSchema = z.tuple([z.string().min(1).max(200)]);

export const runsListSchema = z.tuple([workflowIdSchema.optional()]);
