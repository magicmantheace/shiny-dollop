import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ProfilesList } from '../src/components/ProfilesList';
import {
  clearGppMock,
  installGppMock,
  mockCapabilities,
  mockJournalEntry,
  mockProfile,
} from './mocks';

afterEach(() => {
  clearGppMock();
});

function renderList(overrides: Partial<Parameters<typeof ProfilesList>[0]> = {}) {
  const props = {
    profiles: [mockProfile()],
    capabilities: mockCapabilities(),
    journal: [],
    onNew: vi.fn(),
    onEdit: vi.fn(),
    onPreview: vi.fn(),
    onRollback: vi.fn(),
    onChanged: vi.fn(),
    ...overrides,
  };
  const view = render(<ProfilesList {...props} />);
  return { view, props };
}

describe('ProfilesList', () => {
  it('shows an empty state with a call to action', () => {
    renderList({ profiles: [] });
    expect(screen.getByText('No performance profiles yet.')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'New profile' })).toBeInTheDocument();
  });

  it('empty-state New profile button fires onNew', async () => {
    const user = userEvent.setup();
    const { props } = renderList({ profiles: [] });
    await user.click(screen.getByRole('button', { name: 'New profile' }));
    expect(props.onNew).toHaveBeenCalledTimes(1);
  });

  it('renders a card per profile with change count', () => {
    renderList({ profiles: [mockProfile(), mockProfile({ id: 'p2', name: 'Second' })] });
    expect(screen.getByText('Test Profile')).toBeInTheDocument();
    expect(screen.getByText('Second')).toBeInTheDocument();
    expect(screen.getAllByText('2 changes')).toHaveLength(2);
  });

  it('shows capability badges per change', () => {
    renderList();
    const badges = screen.getAllByText('supported');
    expect(badges.length).toBeGreaterThanOrEqual(2);
  });

  it('shows unsupported badge when a capability is unsupported', () => {
    renderList({
      capabilities: mockCapabilities({
        'power-plan': { supported: false, reason: 'needs admin' },
      }),
    });
    expect(screen.getByText('unsupported')).toBeInTheDocument();
  });

  it('marks a profile applied when the journal has a live entry', () => {
    renderList({ journal: [mockJournalEntry()] });
    expect(screen.getByText('applied')).toBeInTheDocument();
    expect(screen.queryByText('not applied')).not.toBeInTheDocument();
  });

  it('marks a profile not applied when journal entries are rolled back', () => {
    renderList({
      journal: [mockJournalEntry({ rolledBackAt: '2026-10-23T12:00:00Z' })],
    });
    expect(screen.getByText('not applied')).toBeInTheDocument();
  });

  it('enables Roll back only when the profile is applied', () => {
    renderList({ journal: [] });
    expect(screen.getByRole('button', { name: 'Roll back' })).toBeDisabled();
  });

  it('Roll back button fires onRollback when applied', async () => {
    const user = userEvent.setup();
    const { props } = renderList({ journal: [mockJournalEntry()] });
    await user.click(screen.getByRole('button', { name: 'Roll back' }));
    expect(props.onRollback).toHaveBeenCalledTimes(1);
    expect(props.onRollback).toHaveBeenCalledWith(expect.objectContaining({ id: 'profile-1' }));
  });

  it('Preview & activate fires onPreview', async () => {
    const user = userEvent.setup();
    const { props } = renderList();
    await user.click(screen.getByRole('button', { name: 'Preview & activate' }));
    expect(props.onPreview).toHaveBeenCalledTimes(1);
  });

  it('delete asks for confirmation then calls the bridge and refreshes', async () => {
    const user = userEvent.setup();
    installGppMock();
    const { props } = renderList();
    await user.click(screen.getByRole('button', { name: 'Delete' }));
    expect(screen.getByRole('dialog')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Delete profile' }));
    const mock = (window as unknown as { gpp: ReturnType<typeof installGppMock> }).gpp;
    expect(mock.calls['deleteProfile'][0]).toEqual([{ id: 'profile-1' }]);
    expect(props.onChanged).toHaveBeenCalledTimes(1);
  });

  it('delete dialog explains it does not undo OS changes', async () => {
    const user = userEvent.setup();
    installGppMock();
    renderList();
    await user.click(screen.getByRole('button', { name: 'Delete' }));
    expect(screen.getByText(/does not undo OS changes/)).toBeInTheDocument();
  });
});
