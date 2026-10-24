// @vitest-environment jsdom
import './setup';
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import { App } from '../../src/components/App';
import { installFakeAidm } from './fake';

type User = ReturnType<typeof userEvent.setup>;

function region(name: string): HTMLElement {
  return screen.getByRole('region', { name });
}

async function createCampaign(user: User): Promise<void> {
  const campaigns = region('Campaigns');
  await user.type(within(campaigns).getByLabelText('Name'), 'The Mire Campaign');
  await user.type(within(campaigns).getByLabelText('Dice seed (optional)'), 'ui-seed');
  await user.click(within(campaigns).getByRole('button', { name: 'Create campaign' }));
  // Once selected, the campaign panels appear.
  expect(await screen.findByRole('region', { name: 'Characters' })).toBeInTheDocument();
  expect(within(campaigns).getByText(/Dice seed “ui-seed”/)).toBeInTheDocument();
}

async function addCharacter(user: User, name: string, kind: 'pc' | 'npc'): Promise<void> {
  const characters = region('Characters');
  await user.type(within(characters).getByLabelText('Name'), name);
  await user.selectOptions(within(characters).getByLabelText('Kind'), kind);
  await user.click(within(characters).getByRole('button', { name: 'Add character' }));
  expect(await within(characters).findByText(new RegExp(name))).toBeInTheDocument();
}

describe('App', () => {
  it('renders the header and campaign creation form', async () => {
    installFakeAidm();
    render(<App />);
    expect(
      screen.getByRole('heading', { name: 'AI Dungeon Master' }),
    ).toBeInTheDocument();
    expect(screen.getByText(/deterministic house-rules engine/)).toBeInTheDocument();
    expect(
      within(region('Campaigns')).getByRole('button', { name: 'Create campaign' }),
    ).toBeInTheDocument();
    // Campaign-only panels stay hidden until a campaign is selected.
    expect(screen.queryByRole('region', { name: 'Characters' })).not.toBeInTheDocument();
  });

  it('runs the acceptance flow: campaign → characters → roll → encounter → damage', async () => {
    installFakeAidm();
    const user = userEvent.setup();
    render(<App />);
    await createCampaign(user);
    await addCharacter(user, 'Wren', 'pc');
    await addCharacter(user, 'Mire Hound', 'npc');

    // Roll dice and see the auditable result line.
    const dice = region('Dice');
    await user.click(within(dice).getByRole('button', { name: 'Roll dice' }));
    expect(await within(dice).findByText(/2d6: \[.*\] = \d+ \(stream \d+ → \d+\)/)).toBeInTheDocument();

    // The roll is in the session log.
    const log = region('Session log');
    expect(await within(log).findByText(/Rolled 2d6/)).toBeInTheDocument();

    // Start an encounter with both characters.
    const encounter = region('Encounter');
    await user.type(within(encounter).getByLabelText('Encounter name'), 'Ambush');
    await user.click(within(encounter).getByLabelText('Wren'));
    await user.click(within(encounter).getByLabelText('Mire Hound'));
    await user.click(within(encounter).getByRole('button', { name: 'Start encounter' }));
    expect(await within(encounter).findByText(/round 1/)).toBeInTheDocument();
    expect(within(encounter).getAllByText(/initiative \d+/)).toHaveLength(2);

    // Damage the hound: HP 10 (fake default) → 6 after 4 damage.
    const amount = within(encounter).getByLabelText('Amount for Mire Hound');
    await user.clear(amount);
    await user.type(amount, '4');
    const houndRow = within(encounter).getByText(/Mire Hound/).closest('li');
    if (!houndRow) throw new Error('hound row missing');
    await user.click(within(houndRow).getByRole('button', { name: 'Damage' }));
    expect(await within(encounter).findByText(/HP 6\/10/)).toBeInTheDocument();

    // End the encounter; the start form returns.
    await user.click(within(encounter).getByRole('button', { name: 'End encounter' }));
    expect(
      await within(encounter).findByRole('button', { name: 'Start encounter' }),
    ).toBeInTheDocument();
  });

  it('narrates a log entry and manages memory', async () => {
    installFakeAidm();
    const user = userEvent.setup();
    render(<App />);
    await createCampaign(user);

    const log = region('Session log');
    await user.type(within(log).getByLabelText('Note'), 'The ferry bell rang twice.');
    await user.click(within(log).getByRole('button', { name: 'Add note' }));
    expect(await within(log).findByText(/The ferry bell rang twice\./)).toBeInTheDocument();
    const narrateButtons = within(log).getAllByRole('button', { name: 'Narrate' });
    await user.click(narrateButtons[narrateButtons.length - 1]!);
    expect(await within(log).findByText(/Flavor for:/)).toBeInTheDocument();
    expect(within(log).getByText(/\(mock\)/)).toBeInTheDocument();

    const memory = region('Memory');
    await user.type(within(memory).getByLabelText('Title'), 'Sella the Ferryman');
    await user.type(within(memory).getByLabelText('Body'), 'Rows travelers across the Mire.');
    await user.click(within(memory).getByRole('button', { name: 'Add memory' }));
    expect(await within(memory).findByText('Sella the Ferryman')).toBeInTheDocument();

    await user.type(within(memory).getByLabelText('Search memory'), 'ferryman');
    await user.click(within(memory).getByRole('button', { name: 'Search' }));
    expect(await within(memory).findByText('Sella the Ferryman')).toBeInTheDocument();
  });

  it('preserves unsaved session notes across an unrelated refresh, but loads saved notes', async () => {
    installFakeAidm();
    const user = userEvent.setup();
    render(<App />);
    await createCampaign(user);

    const campaigns = region('Campaigns');
    await user.type(within(campaigns).getByLabelText('New session title'), 'Session 1');
    await user.click(within(campaigns).getByRole('button', { name: 'Start session' }));
    const notes = await within(campaigns).findByLabelText('Session notes');
    await user.type(notes, 'Unsaved draft — the bell rang twice.');
    expect(notes).toHaveValue('Unsaved draft — the bell rang twice.');

    // An unrelated action (dice roll) triggers refreshAll, which installs
    // fresh session objects; the unsaved draft must survive it.
    const dice = region('Dice');
    await user.click(within(dice).getByRole('button', { name: 'Roll dice' }));
    expect(await within(dice).findByText(/2d6:/)).toBeInTheDocument();
    expect(within(campaigns).getByLabelText('Session notes')).toHaveValue(
      'Unsaved draft — the bell rang twice.',
    );

    // Saving still works and the saved text remains shown afterwards.
    await user.click(within(campaigns).getByRole('button', { name: 'Save notes' }));
    expect(await screen.findByText('Session notes saved.')).toBeInTheDocument();
    expect(within(campaigns).getByLabelText('Session notes')).toHaveValue(
      'Unsaved draft — the bell rang twice.',
    );
  });

  it('surfaces backend errors in the banner', async () => {
    installFakeAidm();
    const user = userEvent.setup();
    render(<App />);
    await createCampaign(user);
    const dice = region('Dice');
    const notation = within(dice).getByLabelText('Notation');
    await user.clear(notation);
    await user.type(notation, 'banana');
    await user.click(within(dice).getByRole('button', { name: 'Roll dice' }));
    expect(await screen.findByRole('alert')).toHaveTextContent(/DICE_NOTATION_INVALID/);
  });
});
