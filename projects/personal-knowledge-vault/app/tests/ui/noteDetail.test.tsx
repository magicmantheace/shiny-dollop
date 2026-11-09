// @vitest-environment jsdom
// Note detail view: detail rendering, source citation block, linked records,
// approve flow, reject-requires-reason flow, edit flow with required change
// summary, and the revision history panel.
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, test, vi } from 'vitest';
import NoteDetailView from '../../src/components/NoteDetailView';
import { fixtureNotes, fixtureRevisions, installMockPkv } from './mockPkv';

const noop = () => {};

describe('NoteDetailView', () => {
  test('renders detail with status badge, source label and citation block', async () => {
    installMockPkv(fixtureNotes(), fixtureRevisions());
    render(<NoteDetailView id="note-garden" onBack={noop} onOpenNote={noop} />);

    expect(await screen.findByRole('heading', { name: 'Compost ratios' })).toBeInTheDocument();
    expect(screen.getByLabelText('Status: Candidate')).toBeInTheDocument();
    const citation = screen.getByLabelText('Source citation');
    expect(within(citation).getByText('The Compost Handbook')).toBeInTheDocument();
    expect(within(citation).getByText('M. Reyes')).toBeInTheDocument();
  });

  test('shows "note not found" for an unknown id', async () => {
    installMockPkv(fixtureNotes());
    render(<NoteDetailView id="note-nope" onBack={noop} onOpenNote={noop} />);
    expect(await screen.findByRole('alert')).toHaveTextContent(/not found/i);
  });

  test('approve marks the note verified', async () => {
    const user = userEvent.setup();
    const mock = installMockPkv(fixtureNotes(), fixtureRevisions());
    render(<NoteDetailView id="note-garden" onBack={noop} onOpenNote={noop} />);

    await user.click(await screen.findByRole('button', { name: 'Approve' }));
    expect(mock.calls.approve).toEqual(['note-garden']);
    // The note's own badge flips to Verified; the linked record's badge was
    // already Verified, so scope the assertion to the review panel state.
    expect(
      await screen.findByRole('button', { name: 'Already verified' }),
    ).toBeInTheDocument();
    expect(screen.getByRole('status')).toHaveTextContent(/approved/i);
  });

  test('reject is disabled without a reason and works with one', async () => {
    const user = userEvent.setup();
    const mock = installMockPkv(fixtureNotes(), fixtureRevisions());
    render(<NoteDetailView id="note-garden" onBack={noop} onOpenNote={noop} />);
    await screen.findByRole('heading', { name: 'Compost ratios' });

    const rejectButton = screen.getByRole('button', { name: 'Reject' });
    expect(rejectButton).toBeDisabled();

    await user.type(screen.getByLabelText(/rejection reason/i), 'Outdated source.');
    expect(rejectButton).toBeEnabled();
    await user.click(rejectButton);

    expect(mock.calls.reject).toEqual([{ id: 'note-garden', reason: 'Outdated source.' }]);
    expect(await screen.findByLabelText('Status: Rejected')).toBeInTheDocument();
    expect(screen.getByText(/rejected: outdated source\./i)).toBeInTheDocument();
  });

  test('edit requires a change summary before saving', async () => {
    const user = userEvent.setup();
    const mock = installMockPkv(fixtureNotes(), fixtureRevisions());
    render(<NoteDetailView id="note-garden" onBack={noop} onOpenNote={noop} />);
    await user.click(await screen.findByRole('button', { name: 'Edit note' }));

    await user.clear(screen.getByLabelText('Title'));
    await user.type(screen.getByLabelText('Title'), 'Compost ratios (revised)');
    await user.click(screen.getByRole('button', { name: 'Save changes' }));

    // Blocked: validation message, no IPC call.
    expect(
      await screen.findByText(/change summary is required/i),
    ).toBeInTheDocument();
    expect(mock.calls.update).toHaveLength(0);

    await user.type(screen.getByLabelText(/change summary/i), 'Retitled for clarity.');
    await user.click(screen.getByRole('button', { name: 'Save changes' }));

    expect(mock.calls.update).toHaveLength(1);
    expect(mock.calls.update[0]).toMatchObject({
      id: 'note-garden',
      patch: { title: 'Compost ratios (revised)', changeSummary: 'Retitled for clarity.' },
    });
    expect(await screen.findByRole('heading', { name: 'Compost ratios (revised)' }))
      .toBeInTheDocument();
  });

  test('linked records are clickable', async () => {
    const user = userEvent.setup();
    const onOpenNote = vi.fn();
    installMockPkv(fixtureNotes(), fixtureRevisions());
    render(<NoteDetailView id="note-garden" onBack={noop} onOpenNote={onOpenNote} />);

    await user.click(await screen.findByRole('button', { name: 'Worm bin temperatures' }));
    expect(onOpenNote).toHaveBeenCalledWith('note-worms');
  });

  test('revision history shows change summaries and a body diff', async () => {
    installMockPkv(fixtureNotes(), fixtureRevisions());
    render(<NoteDetailView id="note-garden" onBack={noop} onOpenNote={noop} />);

    const panel = await screen.findByLabelText('Revision history');
    expect(within(panel).getByText('Initial capture from the handbook.')).toBeInTheDocument();
    expect(within(panel).getByText('Corrected the ratio per chapter 4.')).toBeInTheDocument();

    const diff = within(panel).getByLabelText('Body diff for revision 2');
    expect(within(diff).getByText(/− Carbon to nitrogen ratio around 25:1\./)).toBeInTheDocument();
    expect(within(diff).getByText(/\+ Carbon to nitrogen ratio around 30:1\./)).toBeInTheDocument();
    expect(within(diff).getByText(/\+ Keep moist, not soggy\./)).toBeInTheDocument();
  });

  test('revision history shows an empty state when there are no revisions', async () => {
    installMockPkv(fixtureNotes(), {});
    render(<NoteDetailView id="note-worms" onBack={noop} onOpenNote={noop} />);
    const panel = await screen.findByLabelText('Revision history');
    expect(within(panel).getByText(/no revisions recorded/i)).toBeInTheDocument();
  });

  test('review failure surfaces an error', async () => {
    const user = userEvent.setup();
    const mock = installMockPkv(fixtureNotes(), fixtureRevisions());
    mock.behavior.fail = { method: 'review.approve', message: 'review service down' };
    render(<NoteDetailView id="note-garden" onBack={noop} onOpenNote={noop} />);

    await user.click(await screen.findByRole('button', { name: 'Approve' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('review service down');
  });
});
