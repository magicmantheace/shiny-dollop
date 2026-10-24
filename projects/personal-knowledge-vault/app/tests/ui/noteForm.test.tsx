// @vitest-environment jsdom
// New-note form: validation, create flow with source + tags + links,
// link picker with provenance on every candidate.
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, test, vi } from 'vitest';
import NoteFormView from '../../src/components/NoteFormView';
import { fixtureNotes, installMockPkv } from './mockPkv';

describe('NoteFormView', () => {
  test('blocks submit when the title is missing', async () => {
    const user = userEvent.setup();
    const mock = installMockPkv(fixtureNotes());
    const onCreated = vi.fn();
    render(<NoteFormView onCreated={onCreated} />);

    await user.type(screen.getByLabelText('Body'), 'Some body text.');
    await user.click(screen.getByRole('button', { name: 'Create note' }));

    expect(await screen.findByText('Title is required.')).toBeInTheDocument();
    expect(mock.calls.create).toHaveLength(0);
    expect(onCreated).not.toHaveBeenCalled();
  });

  test('rejects an invalid source URL', async () => {
    const user = userEvent.setup();
    installMockPkv(fixtureNotes());
    render(<NoteFormView onCreated={vi.fn()} />);

    await user.type(screen.getByLabelText('Title'), 'T');
    await user.type(screen.getByLabelText('Body'), 'B');
    await user.type(screen.getByLabelText('URL'), 'not-a-url');
    await user.click(screen.getByRole('button', { name: 'Create note' }));

    expect(await screen.findByText(/must be a valid http\(s\) URL/i)).toBeInTheDocument();
  });

  test('creates a candidate note with source, tags and links', async () => {
    const user = userEvent.setup();
    const mock = installMockPkv(fixtureNotes());
    const onCreated = vi.fn();
    render(<NoteFormView onCreated={onCreated} />);

    await user.type(screen.getByLabelText('Title'), 'Seed starting mix');
    await user.type(screen.getByLabelText('Body'), 'Equal parts compost and vermiculite.');
    await user.type(screen.getByLabelText('Tags (comma-separated)'), 'gardening, seeds');
    await user.type(screen.getByLabelText('Source title'), 'Nursery notes');
    await user.type(screen.getByLabelText('Author'), 'J. Doe');
    await user.type(screen.getByLabelText('Accessed date'), '2026-10-22');
    await user.click(screen.getByLabelText(/worm bin temperatures/i));
    await user.click(screen.getByRole('button', { name: 'Create note' }));

    expect(mock.calls.create).toHaveLength(1);
    expect(mock.calls.create[0]).toMatchObject({
      title: 'Seed starting mix',
      body: 'Equal parts compost and vermiculite.',
      tags: ['gardening', 'seeds'],
      links: ['note-worms'],
      source: { title: 'Nursery notes', author: 'J. Doe', accessedAt: '2026-10-22' },
    });
    const createdId = mock.store[mock.store.length - 1]?.id as string;
    expect(onCreated).toHaveBeenCalledWith(createdId);
    expect(mock.store[mock.store.length - 1]?.status).toBe('candidate');
  });

  test('link picker shows candidates with status badge and source', async () => {
    installMockPkv(fixtureNotes());
    render(<NoteFormView onCreated={vi.fn()} />);

    const picker = await screen.findByLabelText('Link picker');
    expect(picker).toHaveTextContent('Worm bin temperatures');
    expect(picker).toHaveTextContent('Source: Vermiculture blog');
  });

  test('create failure surfaces an error', async () => {
    const user = userEvent.setup();
    const mock = installMockPkv(fixtureNotes());
    mock.behavior.fail = { method: 'notes.create', message: 'disk full' };
    render(<NoteFormView onCreated={vi.fn()} />);

    await user.type(screen.getByLabelText('Title'), 'T');
    await user.type(screen.getByLabelText('Body'), 'B');
    await user.click(screen.getByRole('button', { name: 'Create note' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('disk full');
  });
});
