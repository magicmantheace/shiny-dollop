// @vitest-environment jsdom
// Backup view: export summary, export failure, import result summary,
// import validation errors (thrown + forward-compat errors array),
// empty-file handling.
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, test } from 'vitest';
import BackupView from '../../src/components/BackupView';
import { fixtureNotes, installMockPkv } from './mockPkv';

function jsonFile(payload: string, name = 'backup.json'): File {
  return new File([payload], name, { type: 'application/json' });
}

describe('BackupView', () => {
  test('export shows the note count from the payload', async () => {
    const user = userEvent.setup();
    const mock = installMockPkv(fixtureNotes());
    render(<BackupView />);

    await user.click(screen.getByRole('button', { name: 'Export backup' }));

    expect(mock.calls.export).toBe(1);
    expect(await screen.findByRole('status')).toHaveTextContent(
      'Backup prepared with 3 notes. The app showed a save dialog for the file.',
    );
  });

  test('export failure shows an error', async () => {
    const user = userEvent.setup();
    const mock = installMockPkv(fixtureNotes());
    mock.behavior.exportError = 'disk unavailable';
    render(<BackupView />);

    await user.click(screen.getByRole('button', { name: 'Export backup' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('disk unavailable');
  });

  test('import shows imported/skipped summary', async () => {
    const user = userEvent.setup();
    const mock = installMockPkv(fixtureNotes());
    render(<BackupView />);

    const payload = JSON.stringify({
      formatVersion: '1.0.0',
      notes: [{ id: 'note-garden' }, { id: 'note-brand-new' }],
    });
    await user.upload(screen.getByLabelText(/backup file/i), jsonFile(payload));

    expect(mock.calls.import).toHaveLength(1);
    const summary = await screen.findByLabelText('Import result');
    expect(summary).toHaveTextContent('Imported 1 note, skipped 1.');
  });

  test('import of malformed JSON shows the validation error', async () => {
    const user = userEvent.setup();
    installMockPkv(fixtureNotes());
    render(<BackupView />);

    await user.upload(screen.getByLabelText(/backup file/i), jsonFile('{not json'));
    expect(await screen.findByRole('alert')).toHaveTextContent(/not valid JSON/i);
  });

  test('import surfaces a per-record errors array when the backend returns one', async () => {
    const user = userEvent.setup();
    const mock = installMockPkv(fixtureNotes());
    mock.behavior.importResult = {
      imported: 1,
      skipped: 2,
      errors: ['notes[1]: "title" is required.', 'notes[2]: "body" must be a string.'],
    };
    render(<BackupView />);

    await user.upload(
      screen.getByLabelText(/backup file/i),
      jsonFile(JSON.stringify({ notes: [] })),
    );
    const summary = await screen.findByLabelText('Import result');
    expect(summary).toHaveTextContent('Imported 1 note, skipped 2.');
    expect(summary).toHaveTextContent('notes[1]: "title" is required.');
    expect(summary).toHaveTextContent('notes[2]: "body" must be a string.');
  });

  test('import of an empty file shows an error', async () => {
    const user = userEvent.setup();
    installMockPkv(fixtureNotes());
    render(<BackupView />);

    await user.upload(screen.getByLabelText(/backup file/i), jsonFile('   '));
    expect(await screen.findByRole('alert')).toHaveTextContent(/empty/i);
  });
});
