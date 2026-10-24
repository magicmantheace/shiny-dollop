/**
 * Discovery honesty: candidates are always shown with their evidence label,
 * and pattern matches are never presented as certain.
 */
import { describe, it, expect, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import AddGameDialog from '../../src/components/AddGameDialog';
import { SaveManagerProvider } from '../../src/store';
import { installMockSaveManager, type MockSaveManager } from './mockSaveManager';

let mock: MockSaveManager;

beforeEach(() => {
  mock = installMockSaveManager();
  mock.api.games.discoverCandidates = () =>
    Promise.resolve({
      ok: true,
      data: [
        {
          gameName: 'Skyrim',
          source: 'steam' as const,
          savePath: 'C:\\Steam\\userdata\\123\\489830\\',
          evidence: 'verified-path' as const,
          detail: 'Found in Steam userdata for app 489830.',
        },
        {
          gameName: 'Stardew Valley',
          source: 'steam' as const,
          savePath: 'C:\\Users\\me\\AppData\\Roaming\\StardewValley\\Saves',
          evidence: 'pattern-match' as const,
          detail: '',
        },
      ],
    });
});

function renderDialog(): void {
  render(
    <SaveManagerProvider>
      <AddGameDialog onClose={() => {}} onAdded={() => {}} />
    </SaveManagerProvider>,
  );
}

describe('AddGameDialog discovery', () => {
  it('displays each candidate with its evidence label', async () => {
    const user = userEvent.setup();
    renderDialog();

    await user.click(screen.getByRole('button', { name: /scan for save folders/i }));

    expect(await screen.findByText('Skyrim')).toBeInTheDocument();
    expect(screen.getByText('Verified path')).toBeInTheDocument();

    expect(screen.getByText('Stardew Valley')).toBeInTheDocument();
    // The pattern-match label must carry its "not confirmed" honesty marker.
    expect(screen.getByText(/pattern match.*not confirmed/i)).toBeInTheDocument();
  });

  it('adds a candidate through games.add with its source', async () => {
    const user = userEvent.setup();
    renderDialog();

    await user.click(screen.getByRole('button', { name: /scan for save folders/i }));
    await screen.findByText('Skyrim');

    const addButtons = screen.getAllByRole('button', { name: /^add$/i });
    await user.click(addButtons[0]);

    await screen.findByText('Skyrim');
    expect(mock.calls.gamesAdd).toHaveLength(1);
    expect(mock.calls.gamesAdd[0]).toMatchObject({
      name: 'Skyrim',
      savePath: 'C:\\Steam\\userdata\\123\\489830\\',
      source: 'steam',
    });
  });

  it('lets the user pick a folder through the native picker before adding', async () => {
    const user = userEvent.setup();
    mock.api.games.chooseFolder = () => Promise.resolve({ ok: true, data: { path: 'D:\\Games\\Saves' } });
    renderDialog();

    await user.click(screen.getByRole('button', { name: /choose folder/i }));
    expect(await screen.findByDisplayValue('D:\\Games\\Saves')).toBeInTheDocument();
  });
});
