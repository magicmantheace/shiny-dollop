// @vitest-environment jsdom
// Notes list view: rendering, status badge + source on every record,
// status/tag filters, search wiring, row navigation.
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, test, vi } from 'vitest';
import NotesListView from '../../src/components/NotesListView';
import { fixtureNotes, installMockPkv } from './mockPkv';

describe('NotesListView', () => {
  test('renders every note with a status badge and a source label', async () => {
    installMockPkv(fixtureNotes());
    render(<NotesListView onOpenNote={() => {}} />);

    const rows = await screen.findAllByRole('button', { name: /open note:/i });
    expect(rows).toHaveLength(3);

    // Every record carries its provenance: status badge + source label.
    expect(screen.getByRole('button', { name: /open note: compost ratios/i })).toHaveTextContent(
      'Source: The Compost Handbook',
    );
    const badgeLabels = ['Status: Candidate', 'Status: Verified', 'Status: Rejected'];
    for (const label of badgeLabels) {
      expect(screen.getByLabelText(label)).toBeInTheDocument();
    }
    // A note without a source still shows the source slot explicitly.
    expect(
      screen.getByRole('button', { name: /open note: moon planting myth/i }),
    ).toHaveTextContent('Source: No source recorded');
  });

  test('status filter narrows the list via notes.list', async () => {
    const user = userEvent.setup();
    const mock = installMockPkv(fixtureNotes());
    render(<NotesListView onOpenNote={() => {}} />);

    await screen.findAllByRole('button', { name: /open note:/i });
    await user.selectOptions(screen.getByLabelText('Status'), 'verified');

    const lastCall = mock.calls.list[mock.calls.list.length - 1];
    expect(lastCall).toMatchObject({ status: 'verified' });
    const rows = await screen.findAllByRole('button', { name: /open note:/i });
    expect(rows).toHaveLength(1);
    expect(rows[0]).toHaveTextContent('Worm bin temperatures');
  });

  test('tag filter passes the tag to notes.list', async () => {
    const user = userEvent.setup();
    const mock = installMockPkv(fixtureNotes());
    render(<NotesListView onOpenNote={() => {}} />);

    await screen.findAllByRole('button', { name: /open note:/i });
    await user.type(screen.getByLabelText('Tag'), 'soil');

    const lastCall = mock.calls.list[mock.calls.list.length - 1];
    expect(lastCall).toMatchObject({ tag: 'soil' });
    const rows = await screen.findAllByRole('button', { name: /open note:/i });
    expect(rows).toHaveLength(1);
    expect(rows[0]).toHaveTextContent('Compost ratios');
  });

  test('search box wires the query to notes.search', async () => {
    const user = userEvent.setup();
    const mock = installMockPkv(fixtureNotes());
    render(<NotesListView onOpenNote={() => {}} />);

    await screen.findAllByRole('button', { name: /open note:/i });
    await user.type(screen.getByLabelText('Search'), 'worm');

    const lastSearch = mock.calls.search[mock.calls.search.length - 1];
    expect(lastSearch?.query).toBe('worm');
    const rows = await screen.findAllByRole('button', { name: /open note:/i });
    expect(rows).toHaveLength(1);
    expect(rows[0]).toHaveTextContent('Worm bin temperatures');
  });

  test('clicking a row opens that note', async () => {
    const user = userEvent.setup();
    const onOpenNote = vi.fn();
    installMockPkv(fixtureNotes());
    render(<NotesListView onOpenNote={onOpenNote} />);

    await user.click(
      await screen.findByRole('button', { name: /open note: compost ratios/i }),
    );
    expect(onOpenNote).toHaveBeenCalledWith('note-garden');
  });

  test('shows an empty-state message when nothing matches', async () => {
    installMockPkv([]);
    render(<NotesListView onOpenNote={() => {}} />);
    expect(await screen.findByText(/no notes match/i)).toBeInTheDocument();
    expect(
      within(document.body).queryByRole('button', { name: /open note:/i }),
    ).not.toBeInTheDocument();
  });

  test('shows an error when the backend fails', async () => {
    const mock = installMockPkv(fixtureNotes());
    mock.behavior.fail = { method: 'notes.list', message: 'database locked' };
    render(<NotesListView onOpenNote={() => {}} />);
    expect(await screen.findByRole('alert')).toHaveTextContent('database locked');
  });
});
