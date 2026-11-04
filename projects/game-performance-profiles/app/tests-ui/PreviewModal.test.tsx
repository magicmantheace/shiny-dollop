import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { PreviewModal } from '../src/components/PreviewModal';
import {
  callArgs,
  clearGppMock,
  installGppMock,
  mockActivationResult,
  mockPlanned,
  mockProfile,
} from './mocks';

afterEach(() => {
  clearGppMock();
});

function renderModal(planned = [mockPlanned()], overrides = {}) {
  const mock = installGppMock({
    async previewProfile() {
      return { planned };
    },
    ...overrides,
  });
  const props = {
    profile: mockProfile(),
    onClose: vi.fn(),
    onChanged: vi.fn(),
  };
  const view = render(<PreviewModal {...props} />);
  return { view, props, mock };
}

async function tickApproval(user: ReturnType<typeof userEvent.setup>) {
  const checkbox = await screen.findByRole('checkbox', {
    name: /I understand these changes and approve/,
  });
  await user.click(checkbox);
}

/** Ticks approval, waits for Activate to enable (React state settles), then clicks. */
async function approveAndActivate(user: ReturnType<typeof userEvent.setup>) {
  await tickApproval(user);
  const activate = await screen.findByRole('button', { name: 'Activate' });
  await waitFor(() => expect(activate).toBeEnabled());
  await user.click(activate);
}

describe('PreviewModal', () => {
  it('renders each planned change with from → to', async () => {
    renderModal([
      mockPlanned({ changeId: 'c1', kind: 'game-mode', from: 'off', to: 'on' }),
      mockPlanned({
        changeId: 'c2',
        kind: 'power-plan',
        target: 'Power plan X',
        from: 'balanced',
        to: 'high performance',
      }),
    ]);
    expect(await screen.findByText('off')).toBeInTheDocument();
    expect(screen.getByText('on')).toBeInTheDocument();
    expect(screen.getByText('balanced')).toBeInTheDocument();
    expect(screen.getByText('high performance')).toBeInTheDocument();
  });

  it('shows reversible badges', async () => {
    renderModal([mockPlanned({ reversible: true }), mockPlanned({ changeId: 'c2', reversible: false })]);
    expect(await screen.findByText('reversible')).toBeInTheDocument();
    expect(screen.getByText('not reversible')).toBeInTheDocument();
  });

  it('shows unsupported rows with their reasons', async () => {
    renderModal([
      mockPlanned({ supported: false, unsupportedReason: 'needs admin rights' }),
    ]);
    const badge = await screen.findByText(/unsupported: needs admin rights/);
    expect(badge).toBeInTheDocument();
  });

  it('keeps Activate disabled until the approval checkbox is ticked', async () => {
    const user = userEvent.setup();
    renderModal();
    const activate = await screen.findByRole('button', { name: 'Activate' });
    expect(activate).toBeDisabled();
    await tickApproval(user);
    await waitFor(() => expect(activate).toBeEnabled());
  });
  it('blocks activation when any change is unsupported, even with the checkbox', async () => {
    const user = userEvent.setup();
    renderModal([
      mockPlanned({ supported: true }),
      mockPlanned({ changeId: 'c2', supported: false, unsupportedReason: 'no admin' }),
    ]);
    const checkbox = await screen.findByRole('checkbox', {
      name: /I understand these changes and approve/,
    });
    await user.click(checkbox);
    const activate = screen.getByRole('button', { name: 'Activate' });
    expect(activate).toBeDisabled();
    expect(screen.getByText('Activation is blocked.')).toBeInTheDocument();
    // The reason appears both on the row badge and in the blocked list.
    expect(screen.getAllByText(/no admin/).length).toBeGreaterThanOrEqual(2);
  });

  it('calls activate with approved: true and shows the completion', async () => {
    const user = userEvent.setup();
    const { props, mock } = renderModal();
    await approveAndActivate(user);
    await waitFor(() =>
      expect(callArgs(mock, 'activateProfile')[0]).toEqual({
        profileId: 'profile-1',
        approved: true,
      }),
    );
    expect(await screen.findByText('Activation complete.')).toBeInTheDocument();
    expect(props.onChanged).toHaveBeenCalled();
  });

  it('renders progress events while activating', async () => {
    const user = userEvent.setup();
    // The mock pauses mid-activation until the test has observed the live
    // progress list, so there is no timing race with React's render flush.
    let release!: () => void;
    const gate = new Promise<void>((resolve) => {
      release = resolve;
    });
    renderModal([mockPlanned()], {
      async activateProfile() {
        const m = (window as unknown as { gpp: ReturnType<typeof installGppMock> }).gpp;
        m.emitProgress({
          changeId: 'c1',
          kind: 'game-mode',
          target: 'Windows Game Mode',
          index: 0,
          total: 1,
          phase: 'applying',
        });
        await gate;
        m.emitProgress({
          changeId: 'c1',
          kind: 'game-mode',
          target: 'Windows Game Mode',
          index: 0,
          total: 1,
          phase: 'applied',
        });
        return { result: mockActivationResult() };
      },
    });
    await approveAndActivate(user);
    // Exact string match: the phase badge reads exactly "applying", while the
    // section header is a longer sentence.
    expect(await screen.findByText('applying')).toBeInTheDocument();
    release();
    expect(await screen.findByText('Activation complete.')).toBeInTheDocument();
  });

  it('shows the error and the automatic-rollback notice on failure', async () => {
    const user = userEvent.setup();
    renderModal([mockPlanned()], {
      async activateProfile() {
        return {
          result: mockActivationResult({
            ok: false,
            error: 'powercfg exited 1',
            applied: [],
            rolledBack: ['journal-9'],
          }),
        };
      },
    });
    await approveAndActivate(user);
    expect(await screen.findByText('Activation failed.')).toBeInTheDocument();
    expect(screen.getByText(/powercfg exited 1/)).toBeInTheDocument();
    expect(screen.getByText(/Automatic rollback/)).toBeInTheDocument();
    expect(screen.getByText(/journal-9/)).toBeInTheDocument();
  });

  it('shows skipped changes in the result', async () => {
    const user = userEvent.setup();
    renderModal([mockPlanned()], {
      async activateProfile() {
        return {
          result: mockActivationResult({
            skipped: [
              {
                changeId: 'c2',
                kind: 'power-plan',
                target: 'Power plan X',
                reason: 'unsupported on this OS build',
              },
            ],
          }),
        };
      },
    });
    await approveAndActivate(user);
    expect(await screen.findByText('Skipped:')).toBeInTheDocument();
    expect(screen.getByText(/unsupported on this OS build/)).toBeInTheDocument();
  });

  it('shows a loading state and a preview error', async () => {
    installGppMock({
      async previewProfile() {
        return { error: 'profile not found' };
      },
    });
    const props = { profile: mockProfile(), onClose: vi.fn(), onChanged: vi.fn() };
    render(<PreviewModal {...props} />);
    expect(await screen.findByText(/profile not found/)).toBeInTheDocument();
  });

  it('Escape closes the modal', async () => {
    const user = userEvent.setup();
    const { props } = renderModal();
    await screen.findByRole('dialog');
    await user.keyboard('{Escape}');
    expect(props.onClose).toHaveBeenCalledTimes(1);
  });
});
