import type { Step, StepKind } from '../../shared/types';

export const STEP_KINDS: ReadonlyArray<{ kind: StepKind; label: string }> = [
  { kind: 'file-copy', label: 'Copy file' },
  { kind: 'file-move-to-trash', label: 'Move to trash' },
  { kind: 'folder-create', label: 'Create folder' },
  { kind: 'run-approved-script', label: 'Run approved script' },
  { kind: 'log-message', label: 'Log message' },
];

export function stepKindLabel(kind: StepKind): string {
  return STEP_KINDS.find((k) => k.kind === kind)?.label ?? kind;
}

function makeStepId(): string {
  if (
    typeof crypto !== 'undefined' &&
    typeof (crypto as Crypto).randomUUID === 'function'
  ) {
    return (crypto as Crypto).randomUUID();
  }
  return `step-${Date.now()}-${Math.floor(Math.random() * 1_000_000)}`;
}

export function newStep(kind: StepKind): Step {
  const base = { id: makeStepId(), label: '' };
  switch (kind) {
    case 'file-copy':
      return { ...base, kind, from: '', to: '' };
    case 'file-move-to-trash':
      return { ...base, kind, path: '' };
    case 'folder-create':
      return { ...base, kind, path: '' };
    case 'run-approved-script':
      return { ...base, kind, scriptId: '', args: [] };
    case 'log-message':
      return { ...base, kind, message: '' };
  }
}

/** Plain-language one-line summary of a step, for list display. */
export function describeStep(step: Step): string {
  switch (step.kind) {
    case 'file-copy':
      return `Copy ${step.from || '(no source)'} → ${step.to || '(no destination)'}`;
    case 'file-move-to-trash':
      return `Move ${step.path || '(no path)'} to trash`;
    case 'folder-create':
      return `Create folder ${step.path || '(no path)'}`;
    case 'run-approved-script':
      return `Run script ${step.scriptId || '(none selected)'}${
        step.args.length ? ` with args: ${step.args.join(' ')}` : ''
      }`;
    case 'log-message':
      return `Log: ${step.message || '(empty message)'}`;
  }
}
