// Named error codes for the Desktop Automation Builder.
// Every IPC failure carries { code, message } so the UI can act on it.

export const DAB_ERROR_CODES = {
  WORKFLOW_NOT_FOUND: 'WORKFLOW_NOT_FOUND',
  WORKFLOW_INVALID: 'WORKFLOW_INVALID',
  PATH_OUTSIDE_SANDBOX: 'PATH_OUTSIDE_SANDBOX',
  APPROVAL_REQUIRED: 'APPROVAL_REQUIRED',
  RUN_NOT_FOUND: 'RUN_NOT_FOUND',
  RUN_NOT_CANCELLABLE: 'RUN_NOT_CANCELLABLE',
  RUN_NOT_RETRYABLE: 'RUN_NOT_RETRYABLE',
  SCRIPT_NOT_APPROVED: 'SCRIPT_NOT_APPROVED',
  SCRIPT_NOT_FOUND: 'SCRIPT_NOT_FOUND',
  STEP_FAILED: 'STEP_FAILED',
  IMPORT_VERSION_UNSUPPORTED: 'IMPORT_VERSION_UNSUPPORTED',
  IMPORT_INVALID: 'IMPORT_INVALID',
  EXPORT_FAILED: 'EXPORT_FAILED',
} as const;

export type DabErrorCode =
  (typeof DAB_ERROR_CODES)[keyof typeof DAB_ERROR_CODES];

export interface DabError {
  code: DabErrorCode;
  message: string;
}

export function dabError(code: DabErrorCode, message: string): DabError {
  return { code, message };
}
