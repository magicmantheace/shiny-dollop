// @vitest-environment jsdom
import './setup';
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import type { Workflow } from '../../shared/types';
import { WorkflowEditor } from '../../src/components/WorkflowEditor';
import { installFakeDab, sampleWorkflow } from './fake';

function renderEditor() {
  render(<WorkflowEditor workflowId="wf-1" onBack={() => {}} onRun={() => {}} />);
}

describe('WorkflowEditor', () => {
  it('renders per-kind form fields for every step kind', async () => {
    installFakeDab();
    renderEditor();
    await screen.findByTestId('step-s1');

    const copy = within(screen.getByTestId('step-s1'));
    expect(copy.getByLabelText('From')).toHaveValue('a.txt');
    expect(copy.getByLabelText('To')).toHaveValue('b.txt');

    const trash = within(screen.getByTestId('step-s2'));
    expect(trash.getByLabelText('Path to move')).toHaveValue('old.txt');

    const folder = within(screen.getByTestId('step-s3'));
    expect(folder.getByLabelText('Folder path')).toHaveValue('out');

    const script = within(screen.getByTestId('step-s4'));
    expect(script.getByLabelText('Script')).toHaveValue('script-1');
    expect(script.getByLabelText('Arguments (one per line)')).toHaveValue(
      '--fast',
    );

    const log = within(screen.getByTestId('step-s5'));
    expect(log.getByLabelText('Message')).toHaveValue('done');

    // every step has a label field
    expect(screen.getAllByLabelText('Step label')).toHaveLength(5);
  });

  it('adds a step of the chosen kind', async () => {
    installFakeDab();
    const user = userEvent.setup();
    renderEditor();
    await screen.findByTestId('step-s1');

    await user.selectOptions(
      screen.getByLabelText('Add step of kind'),
      'log-message',
    );
    await user.click(screen.getByRole('button', { name: 'Add step' }));

    const steps = screen.getAllByTestId(/^step-/);
    expect(steps).toHaveLength(6);
    const added = steps[5];
    if (!added) throw new Error('expected a sixth step element');
    expect(within(added).getByLabelText('Message')).toBeInTheDocument();
  });

  it('removes a step after confirmation and saves the remainder', async () => {
    const workflowsUpdate = vi.fn(
      async (
        id: string,
        patch: {
          name?: string;
          sandboxRoot?: string;
          steps?: Workflow['steps'];
        },
      ): Promise<Workflow> => ({ ...sampleWorkflow(), id, ...patch, version: 2 }),
    );
    installFakeDab({ workflowsUpdate });
    const user = userEvent.setup();
    renderEditor();
    await screen.findByTestId('step-s1');

    await user.click(
      within(screen.getByTestId('step-s2')).getByRole('button', {
        name: /Remove step/,
      }),
    );
    // confirm dialog appears
    const dialog = screen.getByRole('dialog');
    await user.click(
      within(dialog).getByRole('button', { name: 'Remove step' }),
    );

    expect(screen.queryByTestId('step-s2')).not.toBeInTheDocument();
    expect(screen.getAllByTestId(/^step-/)).toHaveLength(4);

    await user.click(screen.getByRole('button', { name: 'Save workflow' }));
    await screen.findByText(/Saved — now at version 2/);

    expect(workflowsUpdate).toHaveBeenCalledTimes(1);
    const call = workflowsUpdate.mock.calls[0];
    if (!call) throw new Error('expected workflowsUpdate to have been called');
    const patch = call[1];
    expect(patch.steps).toHaveLength(4);
    expect(patch.steps?.map((s) => s.id)).not.toContain('s2');
  });

  it('reorders steps with move up/down', async () => {
    installFakeDab();
    const user = userEvent.setup();
    renderEditor();
    await screen.findByTestId('step-s1');

    await user.click(
      within(screen.getByTestId('step-s1')).getByRole('button', {
        name: /down/i,
      }),
    );

    const steps = screen.getAllByTestId(/^step-/);
    expect(steps[0]).toHaveAttribute('data-testid', 'step-s2');
    expect(steps[1]).toHaveAttribute('data-testid', 'step-s1');
  });

  it('fills the sandbox root from pickDirectory via Browse', async () => {
    installFakeDab({ pickDirectory: async () => '/chosen/dir' });
    const user = userEvent.setup();
    renderEditor();
    await screen.findByTestId('step-s1');

    await user.click(screen.getByRole('button', { name: 'Browse…' }));
    expect(screen.getByLabelText('Sandbox root')).toHaveValue('/chosen/dir');
  });

  it('lists version history for inspection', async () => {
    installFakeDab();
    renderEditor();
    await screen.findByTestId('step-s1');

    expect(screen.getByText('Version history')).toBeInTheDocument();
    expect(screen.getByText('v1')).toBeInTheDocument();
  });
});
