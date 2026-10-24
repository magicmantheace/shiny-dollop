import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it } from 'vitest';
import { App } from '../src/App';
import {
  callArgs,
  clearGppMock,
  installGppMock,
  mockCapabilities,
  mockJournalEntry,
  mockProfile,
  mockSnapshot,
} from './mocks';

afterEach(() => {
  clearGppMock();
});

function installFull(overrides = {}) {
  return installGppMock({
    async listProfiles() {
      return { profiles: [mockProfile()] };
    },
    async listJournal() {
      return { entries: [mockJournalEntry()] };
    },
    async listSnapshots() {
      return { snapshots: [mockSnapshot()] };
    },
    async getCapabilities() {
      return { capabilities: mockCapabilities() };
    },
    ...overrides,
  });
}

describe('App shell', () => {
  it('renders the three tabs and the profile card', async () => {
    installFull();
    render(<App />);
    expect(await screen.findByText('Test Profile')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Profiles' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Journal/ })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Snapshots' })).toBeInTheDocument();
  });

  it('shows an actionable error when the bridge is missing', async () => {
    clearGppMock();
    render(<App />);
    expect(await screen.findByText(/window\.gpp.*not available/)).toBeInTheDocument();
  });

  it('journal tab shows the entries table', async () => {
    const user = userEvent.setup();
    installFull();
    render(<App />);
    await screen.findByText('Test Profile');
    await user.click(screen.getByRole('button', { name: /Journal/ }));
    const table = await screen.findByRole('table');
    expect(within(table).getByText('Windows Game Mode')).toBeInTheDocument();
  });

  it('rollback flow confirms, calls the channel and reports what was restored', async () => {
    const user = userEvent.setup();
    const mock = installFull();
    render(<App />);
    await user.click(await screen.findByRole('button', { name: 'Roll back' }));
    const dialog = await screen.findByRole('dialog');
    await user.click(within(dialog).getByRole('button', { name: 'Roll back' }));
    await waitFor(() =>
      expect(callArgs(mock, 'rollbackProfile')[0]).toEqual({ profileId: 'profile-1' }),
    );
    expect(await screen.findByText(/Roll back complete/)).toBeInTheDocument();
    expect(screen.getByText(/1 change restored/)).toBeInTheDocument();
  });

  it('restore-all flow confirms, calls the channel and reports the count', async () => {
    const user = userEvent.setup();
    const mock = installFull();
    render(<App />);
    await screen.findByText('Test Profile');
    await user.click(screen.getByRole('button', { name: 'Restore all changes' }));
    const dialog = await screen.findByRole('dialog');
    expect(within(dialog).getByText(/live change in the journal/)).toBeInTheDocument();
    await user.click(
      within(dialog).getByRole('button', { name: /^Restore all changes$/ }),
    );
    await waitFor(() => expect(mock.calls['restoreAll']).toHaveLength(1));
    expect(await screen.findByText(/Restore all complete/)).toBeInTheDocument();
    expect(screen.getByText(/2 changes restored/)).toBeInTheDocument();
  });

  it('opening the editor and cancelling works from the app shell', async () => {
    const user = userEvent.setup();
    installFull();
    render(<App />);
    await user.click(await screen.findByRole('button', { name: 'New profile' }));
    expect(screen.getByRole('dialog')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Cancel' }));
    await waitFor(() =>
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument(),
    );
  });
});
