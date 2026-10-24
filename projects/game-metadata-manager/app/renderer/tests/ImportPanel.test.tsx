import { afterEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ImportPanel } from '../src/components/ImportPanel';
import { installGmmMock, makeGame, uninstallGmmMock } from './mock-gmm';

afterEach(() => {
  uninstallGmmMock();
});

describe('ImportPanel', () => {
  it('rejects empty input', async () => {
    const user = userEvent.setup();
    const mock = installGmmMock();
    render(<ImportPanel onChanged={() => undefined} />);
    await user.click(screen.getByRole('button', { name: 'Import' }));
    expect(await screen.findByText('Enter at least one root path, one per line.')).toBeInTheDocument();
    expect(mock.lib.importRoots).not.toHaveBeenCalled();
  });

  it('rejects whitespace-only input', async () => {
    const user = userEvent.setup();
    const mock = installGmmMock();
    render(<ImportPanel onChanged={() => undefined} />);
    await user.type(screen.getByLabelText('Root paths, one per line'), '   \n  ');
    await user.click(screen.getByRole('button', { name: 'Import' }));
    expect(await screen.findByText('Enter at least one root path, one per line.')).toBeInTheDocument();
    expect(mock.lib.importRoots).not.toHaveBeenCalled();
  });

  it('imports trimmed, non-empty roots and shows the counts', async () => {
    const user = userEvent.setup();
    const mock = installGmmMock();
    const onChanged = vi.fn();
    mock.lib.importRoots.mockResolvedValue({
      imported: 2,
      skipped: 1,
      games: [makeGame({ id: 'g1', title: 'Doom Eternal' }), makeGame({ id: 'g2', title: 'Hades' })],
    });
    render(<ImportPanel onChanged={onChanged} />);
    await user.type(
      screen.getByLabelText('Root paths, one per line'),
      'C:\\Games\n\n  D:\\More Games  \n',
    );
    await user.click(screen.getByRole('button', { name: 'Import' }));
    expect(mock.lib.importRoots).toHaveBeenCalledWith(['C:\\Games', 'D:\\More Games']);
    const status = await screen.findByRole('status');
    expect(status).toHaveTextContent(/Imported/);
    expect(status).toHaveTextContent(/2/);
    expect(status).toHaveTextContent(/skipped/);
    expect(screen.getByText('Doom Eternal')).toBeInTheDocument();
    expect(screen.getByText('Hades')).toBeInTheDocument();
    expect(onChanged).toHaveBeenCalled();
  });
});
