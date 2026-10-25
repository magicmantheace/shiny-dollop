import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { SnapshotsView } from '../src/components/SnapshotsView';
import { callArgs, clearGppMock, installGppMock, mockSnapshot } from './mocks';

afterEach(() => {
  clearGppMock();
});

const NOTE = 'approximate — point-in-time estimate, not a benchmark';

function renderView(snapshots = [mockSnapshot()], onChanged = vi.fn()) {
  const view = render(<SnapshotsView snapshots={snapshots} onChanged={onChanged} />);
  return { view, onChanged };
}

describe('SnapshotsView', () => {
  it('shows an empty state', () => {
    renderView([]);
    expect(screen.getByText('No snapshots yet.')).toBeInTheDocument();
  });

  it('carries the approximate note on every snapshot', () => {
    renderView([mockSnapshot(), mockSnapshot({ id: 's2', label: 'after' })]);
    // One note per snapshot card, plus one under the compare section.
    expect(screen.getAllByText(NOTE).length).toBeGreaterThanOrEqual(2);
  });

  it('requires a label before taking a snapshot', async () => {
    const user = userEvent.setup();
    const mock = installGppMock();
    renderView([]);
    await user.click(screen.getByRole('button', { name: 'Take snapshot' }));
    expect(screen.getByText(/Give the snapshot a label/)).toBeInTheDocument();
    expect(mock.calls['takeSnapshot']).toBeUndefined();
  });

  it('takes a snapshot with the label and refreshes', async () => {
    const user = userEvent.setup();
    const mock = installGppMock();
    const { onChanged } = renderView([]);
    await user.type(screen.getByLabelText('New snapshot label'), 'before elden ring');
    await user.click(screen.getByRole('button', { name: 'Take snapshot' }));
    expect(callArgs(mock, 'takeSnapshot')[0]).toEqual({ label: 'before elden ring' });
    expect(onChanged).toHaveBeenCalledTimes(1);
  });

  it('renders snapshot stats', () => {
    renderView([mockSnapshot({ cpuPercent: 12.5, memoryMb: 4096 })]);
    expect(screen.getByText('12.5%')).toBeInTheDocument();
    expect(screen.getByText('4096 MB')).toBeInTheDocument();
  });

  it('compares two snapshots with deltas', async () => {
    const user = userEvent.setup();
    installGppMock();
    renderView([
      mockSnapshot({ id: 'a', label: 'before', cpuPercent: 10, memoryMb: 4000 }),
      mockSnapshot({ id: 'b', label: 'after', cpuPercent: 25, memoryMb: 4500 }),
    ]);
    const selects = screen.getAllByRole('combobox');
    await user.selectOptions(selects[0], 'a');
    await user.selectOptions(selects[1], 'b');
    expect(screen.getByText('15.0 pp')).toBeInTheDocument();
    expect(screen.getByText('500 MB')).toBeInTheDocument();
    expect(screen.getAllByText(NOTE).length).toBeGreaterThanOrEqual(1);
  });

  it('shows a backend error when taking fails', async () => {
    const user = userEvent.setup();
    installGppMock({
      async takeSnapshot() {
        return { error: 'wmi unavailable' };
      },
    });
    renderView([]);
    await user.type(screen.getByLabelText('New snapshot label'), 'x');
    await user.click(screen.getByRole('button', { name: 'Take snapshot' }));
    expect(await screen.findByText(/wmi unavailable/)).toBeInTheDocument();
  });
});
