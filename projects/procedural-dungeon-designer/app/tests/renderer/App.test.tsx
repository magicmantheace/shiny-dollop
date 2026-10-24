// @vitest-environment jsdom
import './setup';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';

type UserEvent = ReturnType<typeof userEvent.setup>;
import { App } from '../../src/components/App';
import { installFakePdd } from './fake';

async function awaitThemesLoaded(): Promise<void> {
  // Sunken Crypt is the default theme; its tagline only renders once
  // themesList() has resolved and populated the select.
  expect(
    await screen.findByText(/drowned burial complex/),
  ).toBeInTheDocument();
}

async function generateViaUi(user: UserEvent): Promise<void> {
  await user.click(screen.getByRole('button', { name: 'Generate dungeon' }));
  expect(await screen.findByTestId('dungeon-map')).toBeInTheDocument();
  expect(
    await screen.findByText(/Connected: all \d+ rooms reachable/),
  ).toBeInTheDocument();
}

/** Small, high-budget dungeon: 3 rooms at difficulty 5 leaves ample budget. */
async function generateSmallDungeon(user: UserEvent): Promise<void> {
  const roomCount = screen.getByLabelText('Room count');
  await user.clear(roomCount);
  await user.type(roomCount, '3');
  const difficulty = screen.getByLabelText('Difficulty');
  await user.clear(difficulty);
  await user.type(difficulty, '5');
  await generateViaUi(user);
}

function budgetUsedFromMeter(): number {
  const text = screen.getByTestId('budget-meter').textContent ?? '';
  const match = /Budget: (\d+) \/ (\d+)/.exec(text);
  if (!match) throw new Error(`Budget text not found in: ${text}`);
  return Number(match[1]);
}

describe('App', () => {
  it('renders the generator form and loads themes', async () => {
    installFakePdd();
    render(<App />);

    expect(
      screen.getByRole('heading', {
        name: 'Procedural Dungeon Designer',
      }),
    ).toBeInTheDocument();
    await awaitThemesLoaded();

    expect(screen.getByLabelText('Seed')).toHaveValue('first delve');
    expect(screen.getByLabelText('Grid width')).toHaveValue(28);
    expect(screen.getByLabelText('Grid height')).toHaveValue(20);
    expect(screen.getByLabelText('Room count')).toHaveValue(9);
    expect(screen.getByLabelText('Difficulty')).toHaveValue(2);
    expect(screen.getByLabelText('Theme')).toHaveValue('sunken-crypt');
    expect(
      screen.getByRole('option', { name: 'Sunken Crypt' }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole('option', { name: 'Ember Deep' }),
    ).toBeInTheDocument();
    expect(screen.getByText(/No dungeon yet/)).toBeInTheDocument();
  });

  it('generate flow renders the map, inspector and Connected validation', async () => {
    installFakePdd();
    const user = userEvent.setup();
    render(<App />);
    await awaitThemesLoaded();

    await generateViaUi(user);

    const inspector = screen.getByTestId('inspector');
    expect(within(inspector).getByText(/ID: room-/)).toBeInTheDocument();
    expect(screen.getByTestId('budget-meter')).toHaveTextContent(/Budget:/);

    // Clicking a room on the map selects it in the inspector.
    fireEvent.click(screen.getByTestId('room-room-2'));
    expect(
      await within(inspector).findByText(/ID: room-2/),
    ).toBeInTheDocument();
  });

  it('save flow enables placement editing; add and remove update the budget', async () => {
    installFakePdd();
    const user = userEvent.setup();
    render(<App />);
    await awaitThemesLoaded();
    await generateSmallDungeon(user);

    const editor = screen.getByTestId('placement-editor');
    expect(
      within(editor).getByText('Save the dungeon to edit placements'),
    ).toBeInTheDocument();
    expect(
      within(editor).getByRole('button', { name: 'Add placement' }),
    ).toBeDisabled();

    await user.click(screen.getByRole('button', { name: 'Save dungeon' }));
    expect(
      await within(editor).findByText(/Editing saved dungeon/),
    ).toBeInTheDocument();
    expect(
      within(editor).getByRole('button', { name: 'Add placement' }),
    ).toBeEnabled();

    await user.selectOptions(
      within(editor).getByLabelText('Placement kind'),
      'treasure',
    );
    await user.selectOptions(
      within(editor).getByLabelText('Placement entry'),
      'sunken-offering-bowl',
    );

    const usedBefore = budgetUsedFromMeter();
    await user.click(
      within(editor).getByRole('button', { name: 'Add placement' }),
    );

    const inspector = screen.getByTestId('inspector');
    expect(
      await within(inspector).findByText(
        /treasure: Sunken Offering Bowl \(cost 2\)/,
      ),
    ).toBeInTheDocument();
    await waitFor(() => {
      expect(budgetUsedFromMeter()).toBe(usedBefore + 2);
    });

    await user.click(
      within(inspector).getByRole('button', {
        name: 'Remove Sunken Offering Bowl',
      }),
    );
    await waitFor(() => {
      expect(
        within(inspector).queryByText(/Sunken Offering Bowl/),
      ).toBeNull();
    });
    await waitFor(() => {
      expect(budgetUsedFromMeter()).toBe(usedBefore);
    });
  });

  it('budget block: an add that would exceed the budget surfaces BUDGET_EXCEEDED', async () => {
    const fake = installFakePdd();
    const user = userEvent.setup();
    render(<App />);
    await awaitThemesLoaded();
    await generateSmallDungeon(user);

    await user.click(screen.getByRole('button', { name: 'Save dungeon' }));
    const editor = screen.getByTestId('placement-editor');
    expect(
      await within(editor).findByText(/Editing saved dungeon/),
    ).toBeInTheDocument();

    // Shrink the stored budget so any further placement must be blocked.
    const savedId = [...fake.store.keys()][0]!;
    const used = fake.store.get(savedId)!.map.budgetUsed;
    fake.setBudgetLimit(savedId, used);

    await user.selectOptions(
      within(editor).getByLabelText('Placement kind'),
      'treasure',
    );
    await user.selectOptions(
      within(editor).getByLabelText('Placement entry'),
      'sunken-offering-bowl',
    );
    await user.click(
      within(editor).getByRole('button', { name: 'Add placement' }),
    );

    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent('BUDGET_EXCEEDED');
    expect(alert).toHaveTextContent(/would exceed the budget/);
  });

  it('print view can be exited without losing the unsaved map', async () => {
    installFakePdd();
    const user = userEvent.setup();
    render(<App />);
    await awaitThemesLoaded();
    await generateViaUi(user);

    const toggle = screen.getByRole('button', { name: 'Print view' });
    // The toggle must not live inside a panel hidden in print view.
    expect(toggle.closest('.no-print')).toBeNull();
    await user.click(toggle);

    const exit = screen.getByRole('button', { name: 'Exit print view' });
    expect(exit).toHaveAttribute('aria-pressed', 'true');
    expect(exit.closest('.no-print')).toBeNull();
    expect(screen.getByTestId('dungeon-map')).toBeInTheDocument();

    await user.click(exit);
    expect(
      screen.getByRole('button', { name: 'Print view' }),
    ).toHaveAttribute('aria-pressed', 'false');
    // The unsaved generated map survived the round trip out and back.
    expect(screen.getByTestId('dungeon-map')).toBeInTheDocument();
  });

  it('saved list load and delete round trip', async () => {
    installFakePdd();
    const user = userEvent.setup();
    render(<App />);
    await awaitThemesLoaded();
    await generateViaUi(user);

    await user.click(screen.getByRole('button', { name: 'Save dungeon' }));

    const savedPanel = screen.getByTestId('saved-dungeons');
    const nameEl = await within(savedPanel).findByText(
      'first delve dungeon',
    );
    const row = nameEl.closest('li');
    if (!row) throw new Error('Saved dungeon row not found');
    expect(within(savedPanel).getByText(/seed: first delve/)).toBeInTheDocument();
    expect(within(savedPanel).getByText(/theme: sunken-crypt/)).toBeInTheDocument();

    await user.click(within(row).getByRole('button', { name: 'Load' }));
    expect(await screen.findByTestId('dungeon-map')).toBeInTheDocument();
    expect(
      await screen.findByText(/Connected: all \d+ rooms reachable/),
    ).toBeInTheDocument();

    await user.click(within(row).getByRole('button', { name: 'Delete' }));
    expect(
      await within(savedPanel).findByText('No saved dungeons yet.'),
    ).toBeInTheDocument();
    // Deleting the current dungeon clears it back to the empty state.
    expect(await screen.findByText(/No dungeon yet/)).toBeInTheDocument();
  });
});
