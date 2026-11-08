import { afterEach, describe, expect, it } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { useLibraryData } from '../src/hooks';
import { installGmmMock, makeGame, uninstallGmmMock } from './mock-gmm';

afterEach(() => {
  uninstallGmmMock();
});

describe('useLibraryData missing-flag merge', () => {
  it('marks games whose ids come back from rescan as missing', async () => {
    const mock = installGmmMock();
    const present = makeGame({ id: 'g-present', title: 'Present' });
    const gone = makeGame({ id: 'g-gone', title: 'Gone' });
    mock.lib.list.mockResolvedValue([present, gone]);
    mock.lib.rescan.mockResolvedValue({ missingIds: ['g-gone'] });

    const { result } = renderHook(() => useLibraryData(0));
    await waitFor(() => expect(result.current.loading).toBe(false));

    const byId = new Map(result.current.games.map((g) => [g.id, g]));
    expect(byId.get('g-present')!.missing).toBe(false);
    expect(byId.get('g-gone')!.missing).toBe(true);
  });

  it('still loads the library when rescan fails', async () => {
    const mock = installGmmMock();
    const game = makeGame({ id: 'g-1', title: 'Solo' });
    mock.lib.list.mockResolvedValue([game]);
    mock.lib.rescan.mockRejectedValue(new Error('scan blew up'));

    const { result } = renderHook(() => useLibraryData(0));
    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.games).toHaveLength(1);
    expect(result.current.games[0]!.missing).toBe(false);
    expect(result.current.error).toBeNull();
  });
});
