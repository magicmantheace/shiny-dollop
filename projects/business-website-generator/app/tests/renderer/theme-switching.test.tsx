import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { SiteWorkspace } from '../../src/components/SiteWorkspace';
import { ThemePicker } from '../../src/components/ThemePicker';
import type { Site } from '../../shared/types';
import { installMockBwg, tradesSiteId, type MockBwg } from './mock-bwg';

let mock: MockBwg;

beforeEach(() => {
  mock = installMockBwg();
});

function siteFor(id: string): Site {
  const found = mock.__sites.get(id);
  if (!found) throw new Error('site missing');
  return structuredClone(found);
}

describe('ThemePicker', () => {
  it('switching theme calls sites.setTheme and reports the updated site', async () => {
    const user = userEvent.setup();
    const onThemeChanged = vi.fn();
    render(
      <ThemePicker
        site={siteFor(tradesSiteId(mock))}
        themes={await mock.themes.list()}
        onThemeChanged={onThemeChanged}
      />,
    );

    // Only compatible themes are offered: Workshop (current) and Solid.
    // Bistro is restaurant-only and must not appear.
    expect(screen.queryByText('Bistro')).not.toBeInTheDocument();
    expect(screen.getByText('Workshop')).toBeInTheDocument();
    expect(screen.getByText('Solid')).toBeInTheDocument();

    const id = tradesSiteId(mock);
    await user.click(screen.getByRole('button', { name: 'Use theme Solid' }));

    expect(mock.calls.setTheme).toHaveLength(1);
    expect(mock.calls.setTheme[0]).toEqual({ id, themeId: 'theme-solid' });
    expect(onThemeChanged).toHaveBeenCalledTimes(1);
    expect(onThemeChanged.mock.calls[0]![0].themeId).toBe('theme-solid');
  });
});

describe('theme switching re-renders the preview', () => {
  it('preview fetches fresh pages after a theme change', async () => {
    const user = userEvent.setup();
    const id = tradesSiteId(mock);
    render(<SiteWorkspace siteId={id} onBack={() => {}} />);

    // Wait for the workspace to load.
    await screen.findByRole('heading', { name: 'Acme Plumbing' });

    // Open the preview tab: first render.
    await user.click(screen.getByRole('tab', { name: 'Preview' }));
    const iframe = await screen.findByTestId('preview-iframe');
    expect(mock.calls.previewRender).toHaveLength(1);
    expect(iframe.getAttribute('srcdoc')).toContain('data-theme="theme-workshop"');

    // Switch theme on the theme tab.
    await user.click(screen.getByRole('tab', { name: 'Theme' }));
    await user.click(await screen.findByRole('button', { name: 'Use theme Solid' }));
    expect(mock.calls.setTheme).toHaveLength(1);

    // Back to preview: pages are re-rendered with the new theme.
    await user.click(screen.getByRole('tab', { name: 'Preview' }));
    const iframe2 = await screen.findByTestId('preview-iframe');
    expect(mock.calls.previewRender).toHaveLength(2);
    expect(iframe2.getAttribute('srcdoc')).toContain('data-theme="theme-solid"');
  });
});
