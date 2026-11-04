/**
 * Error codes render as readable, actionable messages — never raw codes alone.
 */
import { describe, it, expect, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { friendlyError, errorSummary } from '../../src/errorMessages';
import GameDetail from '../../src/components/GameDetail';
import { SaveManagerProvider } from '../../src/store';
import { installMockSaveManager, makeGame, type MockSaveManager } from './mockSaveManager';

let mock: MockSaveManager;

beforeEach(() => {
  mock = installMockSaveManager();
});

describe('friendlyError', () => {
  it('maps SAVE_DIR_MISSING to an actionable message', () => {
    const f = friendlyError('SAVE_DIR_MISSING', 'Save dir gone');
    expect(f.title).toMatch(/save folder is missing/i);
    expect(f.detail).toMatch(/no longer exists/i);
  });

  it('maps RESTORE_NOT_CONFIRMED', () => {
    expect(friendlyError('RESTORE_NOT_CONFIRMED').title).toMatch(/not confirmed/i);
  });

  it('maps GAME_NOT_FOUND, BACKUP_NOT_FOUND, BACKUP_DIR_MISSING, INVALID_INPUT, INTERNAL_ERROR, BACKUP_FAILED', () => {
    for (const code of [
      'GAME_NOT_FOUND',
      'BACKUP_NOT_FOUND',
      'BACKUP_DIR_MISSING',
      'INVALID_INPUT',
      'INTERNAL_ERROR',
      'BACKUP_FAILED',
    ]) {
      const f = friendlyError(code, 'detail');
      expect(f.title.length).toBeGreaterThan(0);
      expect(f.detail.length).toBeGreaterThan(0);
      expect(f.title).not.toContain('_');
    }
  });

  it('falls back to the raw message for unknown codes instead of swallowing it', () => {
    const f = friendlyError('WEIRD_CODE', 'something odd happened');
    expect(f.detail).toContain('something odd happened');
  });

  it('errorSummary is a single readable line', () => {
    expect(errorSummary('GAME_NOT_FOUND', 'gone')).toMatch(/game not found/i);
  });
});

describe('error codes in the UI', () => {
  it('renders a readable message when backup history fails with SAVE_DIR_MISSING', async () => {
    mock.api.backups.list = () =>
      Promise.resolve({
        ok: false,
        error: { code: 'SAVE_DIR_MISSING', message: 'The save folder was moved.' },
      });

    render(
      <SaveManagerProvider>
        <GameDetail game={makeGame()} onBack={() => {}} />
      </SaveManagerProvider>,
    );

    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent(/save folder is missing/i);
    expect(alert).toHaveTextContent(/no longer exists/i);
  });
});
