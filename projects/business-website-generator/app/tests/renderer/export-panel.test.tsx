import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ExportPanel } from '../../src/components/ExportPanel';
import { installMockBwg, tradesSiteId, type MockBwg } from './mock-bwg';

let mock: MockBwg;

beforeEach(() => {
  mock = installMockBwg();
});

function panel(id: string, onJumpToSection = vi.fn()) {
  return render(<ExportPanel siteId={id} onJumpToSection={onJumpToSection} />);
}

describe('ExportPanel', () => {
  it('lists validation issues with named codes and section links', async () => {
    const user = userEvent.setup();
    const id = tradesSiteId(mock);
    // Corrupt the seeded profile so validation finds real issues.
    const site = mock.__sites.get(id)!;
    site.profile.contact.email = 'not-an-email';
    site.profile.services = [{ title: '', description: 'x' }];

    const onJumpToSection = vi.fn();
    panel(id, onJumpToSection);

    await user.click(screen.getByRole('button', { name: 'Validate' }));

    expect(await screen.findByText('CONTACT_EMAIL_INVALID')).toBeInTheDocument();
    expect(screen.getByText('SERVICE_TITLE_MISSING')).toBeInTheDocument();

    const goButtons = screen.getAllByRole('button', { name: 'Go to section' });
    expect(goButtons).toHaveLength(2);
    await user.click(goButtons[0]!);
    expect(onJumpToSection).toHaveBeenCalledWith('section-contact');
    await user.click(goButtons[1]!);
    expect(onJumpToSection).toHaveBeenCalledWith('section-services');
  });

  it('keeps export disabled while validation has issues', async () => {
    const user = userEvent.setup();
    const id = tradesSiteId(mock);
    mock.__sites.get(id)!.profile.contact.email = 'bad';

    panel(id);
    const exportButton = screen.getByRole('button', { name: 'Export…' });
    // Before validation runs, export is disabled too.
    expect(exportButton).toBeDisabled();

    await user.click(screen.getByRole('button', { name: 'Validate' }));
    await screen.findByText('CONTACT_EMAIL_INVALID');

    expect(exportButton).toBeDisabled();
    expect(mock.calls.exportRun).toHaveLength(0);
    expect(mock.calls.pickDirectory).toBe(0);
  });

  it('exports after a clean validation and lists the written files', async () => {
    const user = userEvent.setup();
    const id = tradesSiteId(mock);
    panel(id);

    await user.click(screen.getByRole('button', { name: 'Validate' }));
    await screen.findByText(/validation passed/i);

    const exportButton = screen.getByRole('button', { name: 'Export…' });
    expect(exportButton).toBeEnabled();

    await user.click(exportButton);

    expect(mock.calls.pickDirectory).toBe(1);
    expect(mock.calls.exportRun).toHaveLength(1);
    expect(mock.calls.exportRun[0]).toEqual({ id, destDir: '/mock/export/dir' });

    expect(await screen.findByText('Export complete')).toBeInTheDocument();
    expect(screen.getByText('/mock/export/dir')).toBeInTheDocument();
    expect(screen.getByText('index.html')).toBeInTheDocument();
    expect(screen.getByText('services.html')).toBeInTheDocument();
  });

  it('does nothing when the directory picker is cancelled', async () => {
    const user = userEvent.setup();
    mock.__setPickDirectoryResult(null);
    panel(tradesSiteId(mock));

    await user.click(screen.getByRole('button', { name: 'Validate' }));
    await screen.findByText(/validation passed/i);
    await user.click(screen.getByRole('button', { name: 'Export…' }));

    expect(mock.calls.pickDirectory).toBe(1);
    expect(mock.calls.exportRun).toHaveLength(0);
    expect(screen.queryByText('Export complete')).not.toBeInTheDocument();
  });
});
