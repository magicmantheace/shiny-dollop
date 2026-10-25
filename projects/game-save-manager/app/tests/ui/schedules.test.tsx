/**
 * Schedules view: per-game enable toggle, interval validation, save via
 * schedules.set, and last-run display.
 */
import { describe, it, expect, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import SchedulesView from '../../src/components/SchedulesView';
import { SaveManagerProvider } from '../../src/store';
import { installMockSaveManager, makeGame, type MockSaveManager } from './mockSaveManager';

let mock: MockSaveManager;

beforeEach(() => {
  mock = installMockSaveManager();
  mock.api.games.list = () => Promise.resolve({ ok: true, data: [makeGame()] });
  mock.api.schedules.list = () =>
    Promise.resolve({
      ok: true,
      data: [
        {
          id: 1,
          gameId: 1,
          intervalMinutes: 720,
          enabled: true,
          lastRunAt: '2026-10-23T09:00:00.000Z',
        },
      ],
    });
});

function renderView(): void {
  render(
    <SaveManagerProvider>
      <SchedulesView />
    </SaveManagerProvider>,
  );
}

describe('SchedulesView', () => {
  it('shows the game with its schedule, enabled state, and last run', async () => {
    renderView();
    expect(await screen.findByText('Test Game')).toBeInTheDocument();
    expect(screen.getByLabelText(/enable automatic backups for test game/i)).toBeChecked();
    expect(screen.getByLabelText(/backup interval in minutes for test game/i)).toHaveValue(720);
    expect(screen.getByText(/last run:/i)).toBeInTheDocument();
  });

  it('saves the schedule through schedules.set', async () => {
    const user = userEvent.setup();
    renderView();
    await screen.findByText('Test Game');

    const interval = screen.getByLabelText(/backup interval in minutes for test game/i);
    await user.clear(interval);
    await user.type(interval, '60');
    await user.click(screen.getByRole('button', { name: /^save$/i }));

    expect(mock.calls.schedulesSet).toHaveLength(1);
    expect(mock.calls.schedulesSet[0]).toMatchObject({
      gameId: 1,
      intervalMinutes: 60,
      enabled: true,
    });
  });

  it('rejects intervals outside 5–43200 minutes', async () => {
    const user = userEvent.setup();
    renderView();
    await screen.findByText('Test Game');

    const interval = screen.getByLabelText(/backup interval in minutes for test game/i);
    await user.clear(interval);
    await user.type(interval, '3');

    // Invalid input disables Save entirely — the invalid value can never be submitted.
    expect(screen.getByRole('button', { name: /^save$/i })).toBeDisabled();
    expect(mock.calls.schedulesSet).toHaveLength(0);
  });
});
