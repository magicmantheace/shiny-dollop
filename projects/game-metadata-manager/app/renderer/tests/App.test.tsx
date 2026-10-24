import { afterEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { App } from '../src/App';
import { installGmmMock, makeConflict, makeGame, uninstallGmmMock } from './mock-gmm';

afterEach(() => {
  uninstallGmmMock();
  vi.unstubAllGlobals();
});

describe('App bundle import result survives the library refresh', () => {
  it('keeps import counts and conflicts visible during and after a reload', async () => {
    const user = userEvent.setup();
    const mock = installGmmMock();

    // First library load resolves immediately; the refresh triggered by a
    // successful import hangs until released, so the test can inspect the
    // UI *while* App is in its loading/refresh state.
    let releaseRefresh: (() => void) | null = null;
    let listCalls = 0;
    mock.lib.list.mockImplementation(async () => {
      listCalls += 1;
      if (listCalls === 1) return [makeGame({ id: 'g-1' })];
      return new Promise<ReturnType<typeof makeGame>[]>((resolve) => {
        releaseRefresh = () => resolve([makeGame({ id: 'g-1' })]);
      }) as never;
    });

    mock.bundle.import.mockResolvedValue({
      added: 2,
      updated: 1,
      conflicts: [
        makeConflict({
          gameId: 'g-7',
          field: 'description',
          localValue: 'Local blurb',
          bundleValue: 'Bundle blurb',
          chosen: 'bundle',
        }),
      ],
    });

    render(<App />);

    // Wait for the initial load to finish, then open Bundles.
    await waitFor(() => expect(screen.queryByText('Loading library…')).not.toBeInTheDocument());
    await user.click(screen.getByRole('button', { name: 'Bundles' }));
    fireEvent.change(await screen.findByLabelText('Bundle JSON to import'), {
      target: { value: '{"version":1}' },
    });
    await user.click(screen.getByRole('button', { name: 'Import bundle' }));

    // The import triggers onChanged -> refreshKey bump -> a second library load.
    await waitFor(() => expect(listCalls).toBeGreaterThanOrEqual(2));
    expect(releaseRefresh).not.toBeNull();

    // While that refresh is still in flight, the import result must remain
    // visible — unmounting BundlePanel here discards importResult.
    expect(await screen.findByText('Conflicts (1)', {}, { timeout: 2000 })).toBeInTheDocument();
    expect(screen.getByText('g-7')).toBeInTheDocument();
    expect(screen.getByText('Bundle blurb')).toBeInTheDocument();

    // And it must still be there once the refresh completes.
    releaseRefresh!();
    await waitFor(() => expect(screen.queryByText('Loading library…')).not.toBeInTheDocument());
    expect(await screen.findByText('Conflicts (1)')).toBeInTheDocument();
  });
});
