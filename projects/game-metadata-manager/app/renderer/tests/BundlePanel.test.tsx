import { afterEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { BundlePanel } from '../src/components/BundlePanel';
import { installGmmMock, makeConflict, uninstallGmmMock } from './mock-gmm';

afterEach(() => {
  uninstallGmmMock();
  vi.unstubAllGlobals();
});

function renderPanel() {
  const mock = installGmmMock();
  const onChanged = vi.fn();
  render(<BundlePanel onChanged={onChanged} />);
  return { mock, onChanged };
}

describe('BundlePanel export', () => {
  it('shows the exported JSON in a textarea', async () => {
    const user = userEvent.setup();
    const { mock } = renderPanel();
    mock.bundle.export.mockResolvedValue({ json: '{"version":1,"games":[]}' });
    await user.click(screen.getByRole('button', { name: 'Export bundle' }));
    const area = await screen.findByLabelText('Exported bundle JSON');
    expect(area).toHaveValue('{"version":1,"games":[]}');
    expect(mock.bundle.export).toHaveBeenCalledTimes(1);
  });

  it('notes when the native save dialog is unavailable', async () => {
    const user = userEvent.setup();
    const { mock } = renderPanel();
    mock.bundle.export.mockResolvedValue({ json: '{}' });
    await user.click(screen.getByRole('button', { name: 'Export bundle' }));
    await screen.findByLabelText('Exported bundle JSON');
    expect(
      screen.getByText(/native file saving is not available/i),
    ).toBeInTheDocument();
  });
});

describe('BundlePanel import', () => {
  it('rejects an empty import textarea', async () => {
    const user = userEvent.setup();
    const { mock } = renderPanel();
    await user.click(screen.getByRole('button', { name: 'Import bundle' }));
    expect(await screen.findByText('Paste bundle JSON first.')).toBeInTheDocument();
    expect(mock.bundle.import).not.toHaveBeenCalled();
  });

  it('shows added/updated counts and the conflicts list', async () => {
    const user = userEvent.setup();
    const { mock, onChanged } = renderPanel();
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
    // user.type would parse the braces as keyboard descriptors; fireEvent sets the value directly.
    fireEvent.change(screen.getByLabelText('Bundle JSON to import'), {
      target: { value: '{"version":1}' },
    });
    await user.click(screen.getByRole('button', { name: 'Import bundle' }));
    const status = await screen.findByRole('status');
    expect(status).toHaveTextContent(/2/);
    expect(status).toHaveTextContent(/1/);
    expect(await screen.findByText('Conflicts (1)')).toBeInTheDocument();
    expect(screen.getByText('g-7')).toBeInTheDocument();
    expect(screen.getByText('description')).toBeInTheDocument();
    expect(screen.getByText('Local blurb')).toBeInTheDocument();
    expect(screen.getByText('Bundle blurb')).toBeInTheDocument();
    expect(screen.getByText('bundle')).toBeInTheDocument();
    expect(onChanged).toHaveBeenCalled();
  });

  it('shows "No conflicts." when the import is clean', async () => {
    const user = userEvent.setup();
    const { mock } = renderPanel();
    mock.bundle.import.mockResolvedValue({ added: 1, updated: 0, conflicts: [] });
    fireEvent.change(screen.getByLabelText('Bundle JSON to import'), {
      target: { value: '{}' },
    });
    await user.click(screen.getByRole('button', { name: 'Import bundle' }));
    expect(await screen.findByText('No conflicts.')).toBeInTheDocument();
    expect(mock.bundle.import).toHaveBeenCalledWith('{}');
  });
});

describe('BundlePanel undo', () => {
  it('reverts the last change and reports it', async () => {
    const user = userEvent.setup();
    const { mock, onChanged } = renderPanel();
    mock.changes.undo.mockResolvedValue({ reverted: true, gameId: 'g9' });
    await user.click(screen.getByRole('button', { name: 'Undo last change' }));
    expect(mock.changes.undo).toHaveBeenCalledTimes(1);
    expect(await screen.findByText('Reverted the last change (game g9).')).toBeInTheDocument();
    expect(onChanged).toHaveBeenCalled();
  });

  it('reports when there is nothing to undo', async () => {
    const user = userEvent.setup();
    const { mock } = renderPanel();
    mock.changes.undo.mockResolvedValue({ reverted: false });
    await user.click(screen.getByRole('button', { name: 'Undo last change' }));
    expect(await screen.findByText('Nothing to undo.')).toBeInTheDocument();
    expect(mock.changes.undo).toHaveBeenCalledTimes(1);
  });
});
