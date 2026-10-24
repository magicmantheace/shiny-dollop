// @vitest-environment jsdom
import './setup';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import type { DabApi, Run } from '../../shared/types';
import { RunView } from '../../src/components/RunView';
import { installFakeDab, samplePreview, sampleRun } from './fake';

function renderRunView() {
  render(<RunView workflowId="wf-1" onBack={() => {}} />);
}

describe('RunView approval gating', () => {
  it('requires explicit approval before runsStart, and previews first', async () => {
    const calls: string[] = [];
    const runsStart = vi.fn(
      async (workflowId: string, approved: boolean): Promise<Run> => {
        expect(approved).toBe(true);
        return sampleRun('completed');
      },
    );
    installFakeDab({
      runsPreview: (async () => {
        calls.push('runsPreview');
        return samplePreview();
      }) as DabApi['runsPreview'],
      runsStart: (async (workflowId: string, approved: boolean) => {
        calls.push('runsStart');
        return runsStart(workflowId, approved);
      }) as DabApi['runsStart'],
    });
    const user = userEvent.setup();
    renderRunView();

    await user.click(await screen.findByRole('button', { name: 'Preview' }));

    // modal lists planned actions in plain language
    const dialog = await screen.findByRole('dialog');
    expect(dialog).toHaveTextContent(
      'Copy a.txt to b.txt inside the sandbox',
    );
    expect(dialog).toHaveTextContent('Move old.txt to the sandbox trash');

    const approveBtn = screen.getByRole('button', { name: 'Approve & run' });
    expect(approveBtn).toBeDisabled();
    expect(calls).toEqual(['runsPreview']);
    expect(runsStart).not.toHaveBeenCalled();

    await user.click(
      screen.getByRole('checkbox', {
        name: /I have reviewed the planned actions/i,
      }),
    );
    expect(approveBtn).toBeEnabled();

    await user.click(approveBtn);

    expect(runsStart).toHaveBeenCalledTimes(1);
    expect(runsStart).toHaveBeenCalledWith('wf-1', true);
    // preview was requested before the run was started
    expect(calls.indexOf('runsPreview')).toBeLessThan(
      calls.indexOf('runsStart'),
    );
  });
});

describe('RunView run log', () => {
  it('renders per-step outcomes and detail', async () => {
    installFakeDab({
      runsList: async () => [sampleRun('failed')],
      runsGet: async () => sampleRun('failed'),
    });
    renderRunView();

    await screen.findByText('disk is full');
    expect(screen.getAllByText('succeeded').length).toBeGreaterThan(0);
    expect(screen.getAllByText('failed').length).toBeGreaterThan(0);
    expect(screen.getByText('copied 12 bytes')).toBeInTheDocument();
  });

  it('shows the retry button only on failed runs', async () => {
    const runsRetry = vi.fn(
      async (): Promise<Run> => sampleRun('running'),
    );
    installFakeDab({
      runsList: async () => [sampleRun('failed')],
      runsGet: async () => sampleRun('failed'),
      runsRetry,
    });
    const user = userEvent.setup();
    renderRunView();
    const retry = await screen.findByRole('button', { name: /retry/i });
    expect(retry).toBeInTheDocument();
    await user.click(retry);
    // retry starts a fresh run from the failed step
    expect(runsRetry).toHaveBeenCalledWith('run-1');
  });

  it('hides the retry button when the run completed', async () => {
    installFakeDab({
      runsList: async () => [sampleRun('completed')],
      runsGet: async () => sampleRun('completed'),
    });
    renderRunView();
    await screen.findByText('copied 12 bytes');
    expect(
      screen.queryByRole('button', { name: /retry/i }),
    ).not.toBeInTheDocument();
  });

  it('cancels an in-flight run', async () => {
    const runsCancel = vi.fn(async (): Promise<Run> =>
      sampleRun('cancelled'),
    );
    installFakeDab({
      runsList: async () => [sampleRun('running')],
      runsGet: async () => sampleRun('running'),
      runsCancel,
    });
    const user = userEvent.setup();
    renderRunView();

    await user.click(
      await screen.findByRole('button', { name: /cancel run/i }),
    );
    expect(runsCancel).toHaveBeenCalledWith('run-1');
    const badges = await screen.findAllByText('cancelled');
    expect(badges.length).toBeGreaterThan(0);
  });
});

describe('RunView non-blocking start', () => {
  it('closes the approval modal and exposes cancel as soon as the running record returns', async () => {
    installFakeDab({
      runsStart: async () => sampleRun('running'),
      runsGet: async () => sampleRun('running'),
    });
    const user = userEvent.setup();
    renderRunView();

    await user.click(await screen.findByRole('button', { name: 'Preview' }));
    await screen.findByRole('dialog');
    await user.click(
      screen.getByRole('checkbox', { name: /I have reviewed the planned actions/i }),
    );
    await user.click(screen.getByRole('button', { name: 'Approve & run' }));

    // runsStart resolved with the still-running record: the modal is gone
    // and the in-flight run can be inspected / cancelled immediately.
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    expect(
      await screen.findByRole('button', { name: /cancel run/i }),
    ).toBeInTheDocument();
  });
});
