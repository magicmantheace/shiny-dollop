/**
 * Restore flow contract test: the dialog must require explicit user
 * confirmation before calling backups.restore with confirmed: true (literally).
 * There must be no pre-checked box or other way to bypass confirmation.
 */
import { describe, it, expect, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import RestoreDialog from '../../src/components/RestoreDialog';
import { installMockSaveManager, makeBackup, makeGame, type MockSaveManager } from './mockSaveManager';

let mock: MockSaveManager;

beforeEach(() => {
  mock = installMockSaveManager();
});

function renderDialog(): void {
  render(<RestoreDialog backup={makeBackup()} game={makeGame()} onClose={() => {}} />);
}

describe('RestoreDialog confirmation', () => {
  it('states that a pre-restore safety backup will be taken first', () => {
    renderDialog();
    expect(screen.getByText(/pre-restore safety backup/i)).toBeInTheDocument();
  });

  it('keeps the restore button disabled until the user types RESTORE', async () => {
    const user = userEvent.setup();
    renderDialog();
    const button = screen.getByRole('button', { name: /restore backup/i });
    expect(button).toBeDisabled();

    const input = screen.getByLabelText(/type.*RESTORE/i);
    await user.type(input, 'RESTOR');
    expect(button).toBeDisabled();

    await user.type(input, 'E');
    expect(button).toBeEnabled();
  });

  it('has no pre-checked confirmation control', () => {
    renderDialog();
    const checkboxes = screen.queryAllByRole('checkbox');
    expect(checkboxes).toHaveLength(0);
  });

  it('does not call restore without explicit confirmation', async () => {
    const user = userEvent.setup();
    renderDialog();
    // Clicking the disabled button must be impossible / a no-op.
    const button = screen.getByRole('button', { name: /restore backup/i });
    await user.click(button);
    expect(mock.calls.backupsRestore).toHaveLength(0);
  });

  it('calls backups.restore with confirmed: true after explicit confirmation', async () => {
    const user = userEvent.setup();
    renderDialog();
    await user.type(screen.getByLabelText(/type.*RESTORE/i), 'RESTORE');
    await user.click(screen.getByRole('button', { name: /restore backup/i }));

    await waitFor(() => {
      expect(mock.calls.backupsRestore).toHaveLength(1);
    });
    expect(mock.calls.backupsRestore[0]).toEqual({ backupId: 11, confirmed: true });
  });

  it('shows the post-restore verification result after restoring', async () => {
    const user = userEvent.setup();
    renderDialog();
    await user.type(screen.getByLabelText(/type.*RESTORE/i), 'RESTORE');
    await user.click(screen.getByRole('button', { name: /restore backup/i }));

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: /restore complete/i })).toBeInTheDocument();
    });
    expect(screen.getByText(/post-restore verification passed/i)).toBeInTheDocument();
    expect(screen.getByText(/safety backup/i)).toBeInTheDocument();
  });
});
