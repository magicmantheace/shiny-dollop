// @vitest-environment jsdom
import './setup';
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import type { DabApi } from '../../shared/types';
import { WorkflowsList } from '../../src/components/WorkflowsList';
import { installFakeDab, sampleWorkflow } from './fake';

function renderList() {
  render(<WorkflowsList onOpen={() => {}} onRun={() => {}} />);
}

describe('WorkflowsList', () => {
  it('lists workflows with name, version, step count and updated time', async () => {
    installFakeDab();
    renderList();

    expect(await screen.findByText('Test workflow')).toBeInTheDocument();
    expect(screen.getByText('v1')).toBeInTheDocument();
    // 5 steps in the sample workflow
    const row = screen.getByText('Test workflow').closest('tr');
    expect(within(row as HTMLElement).getByText('5')).toBeInTheDocument();
  });

  it('surfaces import validation errors', async () => {
    installFakeDab({
      workflowsImport: (async () => {
        throw {
          code: 'IMPORT_INVALID',
          message: 'not a workflow: missing name',
        };
      }) as DabApi['workflowsImport'],
    });
    const user = userEvent.setup();
    renderList();
    await screen.findByText('Test workflow');

    await user.click(screen.getByRole('button', { name: 'Import' }));
    await user.type(
      screen.getByLabelText('Paste workflow JSON'),
      '{{not valid workflow json',
    );
    await user.click(screen.getByRole('button', { name: 'Import workflow' }));

    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent('not a workflow: missing name');
    expect(alert).toHaveTextContent('IMPORT_INVALID');
  });

  it('asks for confirmation before deleting a workflow', async () => {
    const workflowsDelete = vi.fn(async () => true);
    installFakeDab({ workflowsDelete });
    const user = userEvent.setup();
    renderList();
    await screen.findByText('Test workflow');

    await user.click(screen.getByRole('button', { name: 'Delete' }));

    const dialog = await screen.findByRole('dialog');
    expect(dialog).toHaveTextContent('Delete workflow "Test workflow"?');

    await user.click(
      within(dialog).getByRole('button', { name: 'Delete workflow' }),
    );
    expect(workflowsDelete).toHaveBeenCalledWith('wf-1');
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('creates a workflow and opens it in the editor', async () => {
    const onOpen = vi.fn();
    installFakeDab();
    const user = userEvent.setup();
    render(<WorkflowsList onOpen={onOpen} onRun={() => {}} />);
    await screen.findByText('Test workflow');

    await user.click(screen.getByRole('button', { name: 'New workflow' }));
    await user.type(screen.getByLabelText('Name'), 'Backup job');
    await user.click(
      screen.getByRole('button', { name: 'Create and edit' }),
    );
    expect(onOpen).toHaveBeenCalledWith('wf-new');
  });
});
