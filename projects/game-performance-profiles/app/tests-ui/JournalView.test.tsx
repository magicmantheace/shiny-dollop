import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { JournalView } from '../src/components/JournalView';
import { mockJournalEntry } from './mocks';

describe('JournalView', () => {
  it('shows an empty state', () => {
    render(<JournalView entries={[]} />);
    expect(screen.getByText('No changes recorded yet.')).toBeInTheDocument();
  });

  it('renders entries with before → after', () => {
    render(
      <JournalView
        entries={[
          mockJournalEntry({ before: 'off', after: 'on' }),
          mockJournalEntry({
            id: 'j2',
            changeKind: 'power-plan',
            before: 'balanced',
            after: 'high performance',
          }),
        ]}
      />,
    );
    expect(screen.getByText('off')).toBeInTheDocument();
    expect(screen.getByText('on')).toBeInTheDocument();
    expect(screen.getByText('balanced')).toBeInTheDocument();
    expect(screen.getByText('high performance')).toBeInTheDocument();
    expect(screen.getByText('Game Mode')).toBeInTheDocument();
    expect(screen.getByText('Power plan')).toBeInTheDocument();
  });

  it('shows live badge for un-rolled-back entries', () => {
    render(<JournalView entries={[mockJournalEntry()]} />);
    expect(screen.getByText('live')).toBeInTheDocument();
  });

  it('shows the rolled-back timestamp once rolled back', () => {
    render(
      <JournalView entries={[mockJournalEntry({ rolledBackAt: '2026-10-23T12:00:00Z' })]} />,
    );
    expect(screen.queryByText('live')).not.toBeInTheDocument();
    // Both the applied-at and rolled-back-at timestamps render.
    expect(screen.getAllByText(/2026/)).toHaveLength(2);
  });
});
