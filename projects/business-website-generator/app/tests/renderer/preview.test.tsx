import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it } from 'vitest';
import { Preview } from '../../src/components/Preview';
import { installMockBwg, tradesSiteId, type MockBwg } from './mock-bwg';

let mock: MockBwg;

beforeEach(() => {
  mock = installMockBwg();
});

describe('Preview', () => {
  it('renders page tabs and shows the selected page HTML in the sandboxed iframe', async () => {
    const user = userEvent.setup();
    render(<Preview siteId={tradesSiteId(mock)} renderKey={0} />);

    // Tab bar lists the rendered pages.
    await screen.findByRole('tab', { name: 'index.html' });
    expect(screen.getByRole('tab', { name: 'services.html' })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: 'contact.html' })).toBeInTheDocument();

    const iframe = screen.getByTestId('preview-iframe');
    expect(iframe.tagName).toBe('IFRAME');
    expect(iframe.getAttribute('sandbox')).toBe('allow-same-origin');
    expect(iframe.getAttribute('srcdoc')).toContain('<h1>Acme Plumbing</h1>');
    expect(iframe.getAttribute('srcdoc')).toContain('index.html');

    // Selecting another tab swaps the iframe content.
    await user.click(screen.getByRole('tab', { name: 'services.html' }));
    const iframe2 = screen.getByTestId('preview-iframe');
    expect(iframe2.getAttribute('srcdoc')).toContain('services.html');
  });

  it('toggles the viewport between desktop width and 375px mobile', async () => {
    const user = userEvent.setup();
    render(<Preview siteId={tradesSiteId(mock)} renderKey={0} />);
    const iframe = await screen.findByTestId('preview-iframe');

    expect(iframe).toHaveStyle({ width: '100%' });

    await user.click(screen.getByRole('button', { name: 'Mobile' }));
    expect(screen.getByTestId('preview-iframe')).toHaveStyle({ width: '375px' });
    expect(screen.getByRole('button', { name: 'Mobile' })).toHaveAttribute('aria-pressed', 'true');

    await user.click(screen.getByRole('button', { name: 'Desktop' }));
    expect(screen.getByTestId('preview-iframe')).toHaveStyle({ width: '100%' });
  });

  it('labels the preview as approximate', async () => {
    render(<Preview siteId={tradesSiteId(mock)} renderKey={0} />);
    await screen.findByTestId('preview-iframe');
    expect(
      screen.getByText(/preview is approximate — the exported files are authoritative/i),
    ).toBeInTheDocument();
  });
});
