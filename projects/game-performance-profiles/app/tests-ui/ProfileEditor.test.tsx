import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ProfileEditor } from '../src/components/ProfileEditor';
import { callArgs, clearGppMock, installGppMock, mockProfile } from './mocks';

afterEach(() => {
  clearGppMock();
});

function renderEditor(profile?: Parameters<typeof ProfileEditor>[0]['profile']) {
  const props = {
    profile,
    onSaved: vi.fn(),
    onCancel: vi.fn(),
  };
  const view = render(<ProfileEditor {...props} />);
  return { view, props };
}

describe('ProfileEditor', () => {
  it('renders the name field', () => {
    renderEditor();
    expect(screen.getByLabelText('Profile name')).toBeInTheDocument();
  });

  it('blocks save with an empty name and never calls the bridge', async () => {
    const user = userEvent.setup();
    const mock = installGppMock();
    const { props } = renderEditor();
    await user.selectOptions(screen.getByLabelText('Add change'), 'game-mode');
    await user.click(screen.getByRole('button', { name: 'Add' }));
    await user.click(screen.getByRole('button', { name: 'Create profile' }));
    expect(screen.getByText('Profile name is required.')).toBeInTheDocument();
    expect(props.onSaved).not.toHaveBeenCalled();
    expect(mock.calls['createProfile']).toBeUndefined();
  });

  it('requires at least one change', async () => {
    const user = userEvent.setup();
    installGppMock();
    renderEditor();
    await user.type(screen.getByLabelText('Profile name'), 'My profile');
    await user.click(screen.getByRole('button', { name: 'Create profile' }));
    expect(screen.getByText(/at least one change/)).toBeInTheDocument();
  });

  it('adds a game-mode change with an on/off toggle', async () => {
    const user = userEvent.setup();
    installGppMock();
    renderEditor();
    await user.selectOptions(screen.getByLabelText('Add change'), 'game-mode');
    await user.click(screen.getByRole('button', { name: 'Add' }));
    expect(screen.getByLabelText('Game Mode')).toBeInTheDocument();
    expect(
      within(screen.getByLabelText('Game Mode') as HTMLElement).getByRole('option', {
        name: 'On',
      }),
    ).toBeInTheDocument();
  });

  it('shows the power-plan format hint and must-pick-your-plan warning', async () => {
    const user = userEvent.setup();
    installGppMock();
    renderEditor();
    await user.selectOptions(screen.getByLabelText('Add change'), 'power-plan');
    await user.click(screen.getByRole('button', { name: 'Add' }));
    const hints = screen.getAllByText(/You must pick your own plan/);
    expect(hints.length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText(/powercfg \/list/).length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText(/8-4-4-4-12/)).toBeInTheDocument();
  });

  it('rejects a bad GUID and does not save', async () => {
    const user = userEvent.setup();
    const mock = installGppMock();
    renderEditor();
    await user.type(screen.getByLabelText('Profile name'), 'P1');
    await user.selectOptions(screen.getByLabelText('Add change'), 'power-plan');
    await user.click(screen.getByRole('button', { name: 'Add' }));
    await user.type(screen.getByLabelText('Power-plan GUID'), 'junk');
    await user.click(screen.getByRole('button', { name: 'Create profile' }));
    expect(screen.getByText(/not a valid power-plan GUID/)).toBeInTheDocument();
    expect(mock.calls['createProfile']).toBeUndefined();
  });

  it('accepts a valid GUID and creates the profile', async () => {
    const user = userEvent.setup();
    const mock = installGppMock();
    const { props } = renderEditor();
    await user.type(screen.getByLabelText('Profile name'), 'P1');
    await user.selectOptions(screen.getByLabelText('Add change'), 'power-plan');
    await user.click(screen.getByRole('button', { name: 'Add' }));
    await user.type(
      screen.getByLabelText('Power-plan GUID'),
      '381b4222-f694-41f0-9685-ff5bb260df2e',
    );
    await user.click(screen.getByRole('button', { name: 'Create profile' }));
    expect(callArgs(mock, 'createProfile')[0]).toEqual({
      name: 'P1',
      changes: [
        { kind: 'power-plan', params: { guid: '381b4222-f694-41f0-9685-ff5bb260df2e' } },
      ],
    });
    expect(props.onSaved).toHaveBeenCalledTimes(1);
  });

  it('process-priority form offers only above-normal and high', async () => {
    const user = userEvent.setup();
    installGppMock();
    renderEditor();
    await user.selectOptions(screen.getByLabelText('Add change'), 'process-priority');
    await user.click(screen.getByRole('button', { name: 'Add' }));
    const select = screen.getByLabelText('Priority') as HTMLSelectElement;
    const options = Array.from(select.options).map((o) => o.value);
    expect(options).toEqual(['above-normal', 'high']);
    expect(screen.getByText(/Realtime priority is never allowed/)).toBeInTheDocument();
  });

  it('fullscreen-optimizations validates the exe path', async () => {
    const user = userEvent.setup();
    const mock = installGppMock();
    renderEditor();
    await user.type(screen.getByLabelText('Profile name'), 'P1');
    await user.selectOptions(
      screen.getByLabelText('Add change'),
      'fullscreen-optimizations',
    );
    await user.click(screen.getByRole('button', { name: 'Add' }));
    await user.type(screen.getByLabelText('Game .exe path'), 'game.exe');
    await user.click(screen.getByRole('button', { name: 'Create profile' }));
    expect(screen.getByText(/absolute Windows path/)).toBeInTheDocument();
    expect(mock.calls['createProfile']).toBeUndefined();
  });

  it('remove button drops a change', async () => {
    const user = userEvent.setup();
    installGppMock();
    renderEditor();
    await user.selectOptions(screen.getByLabelText('Add change'), 'game-mode');
    await user.click(screen.getByRole('button', { name: 'Add' }));
    expect(screen.getByLabelText('Game Mode')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Remove Game Mode change' }));
    expect(screen.queryByLabelText('Game Mode')).not.toBeInTheDocument();
  });

  it('edit mode pre-fills the existing profile', () => {
    renderEditor(mockProfile({ name: 'Existing' }));
    expect(screen.getByLabelText('Profile name')).toHaveValue('Existing');
    expect(screen.getByRole('button', { name: 'Save changes' })).toBeInTheDocument();
  });

  it('edit mode calls updateProfile with the id', async () => {
    const user = userEvent.setup();
    const mock = installGppMock();
    renderEditor(mockProfile({ id: 'profile-42', name: 'Existing' }));
    await user.click(screen.getByRole('button', { name: 'Save changes' }));
    expect(callArgs(mock, 'updateProfile')[0]).toEqual(
      expect.objectContaining({ id: 'profile-42', name: 'Existing' }),
    );
  });
});
