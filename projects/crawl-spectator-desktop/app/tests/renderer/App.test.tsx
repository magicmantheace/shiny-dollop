// @vitest-environment jsdom
import './setup';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import { App } from '../../src/components/App';
import { FakeSpectator } from './fake';

function install(fake: FakeSpectator): void {
  (window as unknown as Record<string, unknown>).spectator = fake;
}

describe('App — mode labeling (live truth vs demo)', () => {
  it('shows an unmistakable DEMO banner in demo mode', async () => {
    install(new FakeSpectator('demo'));
    render(<App />);
    expect(await screen.findByText(/DEMO MODE — invented fixture data/)).toBeInTheDocument();
    expect(screen.getByText('READ-ONLY')).toBeInTheDocument();
  });

  it('shows a LIVE banner naming the base URL in live mode', async () => {
    install(new FakeSpectator('live'));
    render(<App />);
    expect(await screen.findByText(/LIVE — connected to the real Feed API at http:\/\/127\.0\.0\.1:8000/)).toBeInTheDocument();
    expect(screen.queryByText(/DEMO MODE/)).not.toBeInTheDocument();
  });
});

describe('App — descenders, profile, feed', () => {
  it('lists descenders and loads an authentic profile + history on selection', async () => {
    install(new FakeSpectator('demo'));
    const user = userEvent.setup();
    render(<App />);
    const main = await screen.findByRole('button', { name: /^mira-vane active/ });
    await user.click(main);
    expect(await screen.findByText('Reach the Stratum 3 exit')).toBeInTheDocument();
    // The damage event appears in both the live feed and the profile history.
    expect((await screen.findAllByText(/Mira Vane was damaged by a falling bell clapper/)).length).toBeGreaterThanOrEqual(2);
    expect(screen.getByText(/trust 0.8, respect 0.7/)).toBeInTheDocument();
  });

  it('renders the live ledger feed with event summaries', async () => {
    install(new FakeSpectator('demo'));
    render(<App />);
    expect(await screen.findByText(/Mira Vane formed the Ember Pact/)).toBeInTheDocument();
    expect(screen.getByText(/Buffered 2 event\(s\), cursor tick 1231/)).toBeInTheDocument();
  });

  it('follow toggles persist through the API and unlock highlights', async () => {
    const fake = new FakeSpectator('demo');
    install(fake);
    const user = userEvent.setup();
    render(<App />);
    const followBtn = await screen.findByRole('button', { name: 'Follow mira-vane' });
    await user.click(followBtn);
    expect(await screen.findByRole('button', { name: 'Unfollow mira-vane' })).toBeInTheDocument();
    expect(fake.prefs.followedDescenderIds).toContain('mira-vane');
  });

  it('clears demo profile, search and replay state when connecting live', async () => {
    install(new FakeSpectator('demo'));
    const user = userEvent.setup();
    render(<App />);
    // Load demo source-specific state: a profile, a search, and a replay.
    const main = await screen.findByRole('button', { name: /^mira-vane active/ });
    await user.click(main);
    expect(await screen.findByText('Reach the Stratum 3 exit')).toBeInTheDocument();
    await user.type(screen.getByLabelText('Search descenders and events'), 'mira');
    await user.click(screen.getByRole('button', { name: 'Search' }));
    expect(await screen.findByText(/descender\(s\), 0 event\(s\)/)).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Load replay' }));
    expect(await screen.findByText(/Replay-only fixture event/)).toBeInTheDocument();

    // Switch sources: none of the demo state may survive under LIVE.
    await user.click(screen.getByRole('button', { name: 'Connect live' }));
    expect(await screen.findByText(/LIVE — connected to the real Feed API/)).toBeInTheDocument();
    expect(screen.getByText('Select a Descender to inspect authentic state and history.')).toBeInTheDocument();
    expect(screen.queryByText('Reach the Stratum 3 exit')).not.toBeInTheDocument();
    expect(screen.queryByText(/descender\(s\), 0 event\(s\)/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Replay-only fixture event/)).not.toBeInTheDocument();
  });

  it('rejects a profile response that resolves after switching connections', async () => {
    const fake = new FakeSpectator('demo');
    let releaseProfile!: () => void;
    fake.profileGate = new Promise<void>((resolve) => { releaseProfile = resolve; });
    install(fake);
    const user = userEvent.setup();
    render(<App />);
    const main = await screen.findByRole('button', { name: /^mira-vane active/ });
    await user.click(main); // profile request now in flight (gated)
    await user.click(screen.getByRole('button', { name: 'Connect live' }));
    expect(await screen.findByText(/LIVE — connected to the real Feed API/)).toBeInTheDocument();
    releaseProfile(); // the stale demo response arrives late
    await new Promise((r) => setTimeout(r, 50));
    expect(screen.queryByText('Reach the Stratum 3 exit')).not.toBeInTheDocument();
    expect(screen.getByText('Select a Descender to inspect authentic state and history.')).toBeInTheDocument();
  });

  it('search narrows the descender list via the API', async () => {
    install(new FakeSpectator('demo'));
    const user = userEvent.setup();
    render(<App />);
    await screen.findByText('ossian-rell');
    await user.type(screen.getByLabelText('Search descenders and events'), 'mira');
    await user.click(screen.getByRole('button', { name: 'Search' }));
    expect(await screen.findByText(/descender\(s\), 0 event\(s\)/)).toBeInTheDocument();
    expect(screen.queryByText('ossian-rell')).not.toBeInTheDocument();
  });
});
