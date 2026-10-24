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
