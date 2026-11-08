import { afterEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { TokenEditor } from './TokenEditor';
import { fixtureTokens } from '../test-utils';

afterEach(() => {
  vi.restoreAllMocks();
});

describe('TokenEditor', () => {
  it('shows an inline error and blocks the API call for an invalid hex value', async () => {
    const onApply = vi.fn();
    const user = userEvent.setup();
    render(<TokenEditor tokens={fixtureTokens} onApply={onApply} />);

    const bgHex = screen.getByLabelText('Background');
    await user.clear(bgHex);
    await user.type(bgHex, '#zzzzzz');

    // Inline error is shown…
    const error = await screen.findByRole('alert');
    expect(error).toHaveTextContent('6-digit hex');
    expect(bgHex).toHaveAttribute('aria-invalid', 'true');
    // …and nothing is sent to the backend.
    expect(onApply).not.toHaveBeenCalled();
  });

  it('forwards a valid hex value once it becomes valid', async () => {
    const onApply = vi.fn();
    const user = userEvent.setup();
    render(<TokenEditor tokens={fixtureTokens} onApply={onApply} />);

    const bgHex = screen.getByLabelText('Background');
    await user.clear(bgHex);
    await user.type(bgHex, '#123abc');

    expect(onApply).toHaveBeenCalledWith({ bg: '#123abc' });
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });

  it('applies the native colour picker value immediately', async () => {
    const onApply = vi.fn();
    render(<TokenEditor tokens={fixtureTokens} onApply={onApply} />);

    const picker = screen.getByLabelText('Background colour picker');
    fireEvent.change(picker, { target: { value: '#aabbcc' } });

    expect(onApply).toHaveBeenCalledWith({ bg: '#aabbcc' });
  });

  it('rejects out-of-range spacing without calling the backend', async () => {
    const onApply = vi.fn();
    const user = userEvent.setup();
    render(<TokenEditor tokens={fixtureTokens} onApply={onApply} />);

    const spacing = screen.getByLabelText('Spacing (px)');
    await user.clear(spacing);
    // '-5' is invalid on every keystroke, so no intermediate valid value
    // may leak to the backend.
    await user.type(spacing, '-5');

    expect(await screen.findByRole('alert')).toHaveTextContent('between 0 and 64');
    expect(onApply).not.toHaveBeenCalled();
  });

  it('accepts valid spacing and forwards it as a number', async () => {
    const onApply = vi.fn();
    const user = userEvent.setup();
    render(<TokenEditor tokens={fixtureTokens} onApply={onApply} />);

    const spacing = screen.getByLabelText('Spacing (px)');
    await user.clear(spacing);
    await user.type(spacing, '24');

    expect(onApply).toHaveBeenCalledWith({ spacing: 24 });
  });

  it('offers only system font stacks in the font selects', () => {
    const onApply = vi.fn();
    render(<TokenEditor tokens={fixtureTokens} onApply={onApply} />);

    const headingFont = screen.getByLabelText('Heading font');
    const options = Array.from(
      (headingFont as HTMLSelectElement).options,
    ).map((o) => o.value);
    expect(options.length).toBeGreaterThan(0);
    for (const v of options) {
      expect(v).not.toMatch(/https?:/);
    }
  });
});
