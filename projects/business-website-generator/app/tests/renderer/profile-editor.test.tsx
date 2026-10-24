import { useState } from 'react';
import { act, fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ProfileEditor } from '../../src/components/ProfileEditor';
import type { Site } from '../../shared/types';
import { installMockBwg, type MockBwg } from './mock-bwg';

let mock: MockBwg;
let site: Site;

function renderEditor() {
  return render(
    <ProfileEditor
      site={site}
      onSaved={() => {}}
      focusSectionId={null}
      onFocusSectionDone={() => {}}
    />,
  );
}

beforeEach(() => {
  vi.useFakeTimers();
  mock = installMockBwg();
  const found = [...mock.__sites.values()].find((s) => s.businessType === 'trades');
  if (!found) throw new Error('no trades site');
  site = structuredClone(found);
});

afterEach(() => {
  vi.useRealTimers();
});

/** Let the debounced autosave fire, then flush the save promise. */
async function settleAutosave() {
  act(() => {
    vi.advanceTimersByTime(1000);
  });
  await act(async () => {});
}

describe('ProfileEditor', () => {
  it('blocks an invalid email: shows an inline message and never saves it', async () => {
    renderEditor();

    const email = screen.getByLabelText('Email');
    fireEvent.change(email, { target: { value: 'not-an-email' } });
    fireEvent.blur(email);
    await settleAutosave();

    expect(screen.getByRole('alert')).toHaveTextContent(/valid email address/i);
    expect(mock.calls.updateProfile).toHaveLength(0);
    expect(screen.getByRole('status')).toHaveTextContent(/fix the highlighted fields/i);
  });

  it('blocks an invalid website URL and keeps other edits unsaved', async () => {
    renderEditor();

    const website = screen.getByLabelText('Website');
    fireEvent.change(website, { target: { value: 'example.com/no-scheme' } });
    fireEvent.blur(website);
    await settleAutosave();

    expect(screen.getByText('URL must start with http:// or https://.')).toBeInTheDocument();
    expect(mock.calls.updateProfile).toHaveLength(0);
  });

  it('autosaves valid changes with a dirty indicator', async () => {
    renderEditor();

    const tagline = screen.getByLabelText('Tagline');
    fireEvent.change(tagline, { target: { value: 'We fix leaks fast' } });
    expect(screen.getByRole('status')).toHaveTextContent(/unsaved changes/i);

    await settleAutosave();

    expect(mock.calls.updateProfile).toHaveLength(1);
    expect(mock.calls.updateProfile[0]!.patch.tagline).toBe('We fix leaks fast');
    expect(screen.getByRole('status')).toHaveTextContent(/all changes saved/i);
  });

  it('preserves edits typed while an autosave is in flight and saves them next', async () => {
    // Mirror the real parent (SiteWorkspace passes onSaved={setSite}): the
    // saved site flows back in as the `site` prop.
    function Harness() {
      const [current, setCurrent] = useState(site);
      return (
        <ProfileEditor
          site={current}
          onSaved={setCurrent}
          focusSectionId={null}
          onFocusSectionDone={() => {}}
        />
      );
    }
    render(<Harness />);

    // Hold the first save in flight until the test releases it; the mock
    // still applies the submitted snapshot immediately, like the backend.
    let release!: () => void;
    const gate = new Promise<void>((resolve) => {
      release = resolve;
    });
    const originalUpdate = mock.sites.updateProfile;
    mock.sites.updateProfile = async (id, patch) => {
      const updated = await originalUpdate(id, patch);
      await gate;
      return updated;
    };

    const tagline = screen.getByLabelText('Tagline');
    fireEvent.change(tagline, { target: { value: 'First edit' } });
    await settleAutosave();
    expect(mock.calls.updateProfile).toHaveLength(1);
    expect(mock.calls.updateProfile[0]!.patch.tagline).toBe('First edit');

    // Type a newer edit while the first save is still awaiting its response.
    fireEvent.change(tagline, { target: { value: 'Second edit while saving' } });

    await act(async () => {
      release();
    });

    // The in-flight (older) snapshot must not overwrite the newer draft,
    // and the UI must not claim everything is saved.
    expect(screen.getByLabelText('Tagline')).toHaveValue('Second edit while saving');
    expect(screen.getByRole('status')).toHaveTextContent(/unsaved changes/i);
    expect(screen.getByRole('status')).not.toHaveTextContent(/all changes saved/i);

    // The newer draft is saved by the next autosave cycle.
    await settleAutosave();
    expect(mock.calls.updateProfile).toHaveLength(2);
    expect(mock.calls.updateProfile[1]!.patch.tagline).toBe('Second edit while saving');
    expect(screen.getByLabelText('Tagline')).toHaveValue('Second edit while saving');
    expect(screen.getByRole('status')).toHaveTextContent(/all changes saved/i);
  });

  it('adds and removes services', () => {
    renderEditor();
    const servicesSection = screen.getByRole('heading', { name: 'Services' }).closest('section')!;
    const inSection = within(servicesSection);

    expect(inSection.getByLabelText('Service 1 title')).toHaveValue('Consultation');

    fireEvent.click(inSection.getByRole('button', { name: 'Add service' }));
    expect(inSection.getByLabelText('Service 2 title')).toBeInTheDocument();

    fireEvent.click(inSection.getByRole('button', { name: 'Remove service 2' }));
    expect(inSection.queryByLabelText('Service 2 title')).not.toBeInTheDocument();
    expect(inSection.getByLabelText('Service 1 title')).toBeInTheDocument();
  });

  it('adds and removes hours lines', () => {
    renderEditor();
    const hoursSection = screen.getByRole('heading', { name: 'Hours' }).closest('section')!;
    const inSection = within(hoursSection);

    expect(inSection.getByLabelText('Hours line 1')).toHaveValue('Mon–Fri: 9am–5pm');

    fireEvent.click(inSection.getByRole('button', { name: 'Add hours line' }));
    expect(inSection.getByLabelText('Hours line 3')).toBeInTheDocument();

    fireEvent.click(inSection.getByRole('button', { name: 'Remove hours line 3' }));
    expect(inSection.queryByLabelText('Hours line 3')).not.toBeInTheDocument();
  });

  it('adds and removes social links, validating the URL', async () => {
    renderEditor();
    const socialSection = screen.getByRole('heading', { name: 'Social links' }).closest('section')!;
    const inSection = within(socialSection);

    fireEvent.click(inSection.getByRole('button', { name: 'Add social link' }));
    const urlInput = inSection.getByLabelText('Link 2 URL');
    fireEvent.change(urlInput, { target: { value: 'not-a-url' } });
    fireEvent.blur(urlInput);
    await settleAutosave();

    expect(inSection.getByText('URL must start with http:// or https://.')).toBeInTheDocument();
    expect(mock.calls.updateProfile).toHaveLength(0);

    fireEvent.click(inSection.getByRole('button', { name: 'Remove social link 2' }));
    expect(inSection.queryByLabelText('Link 2 URL')).not.toBeInTheDocument();
  });

  it('shows SEO length counters', () => {
    renderEditor();
    expect(screen.getByText(/\/ 60 characters/)).toBeInTheDocument();
    expect(screen.getByText(/\/ 160 characters/)).toBeInTheDocument();
  });

  it('requires the business name', async () => {
    renderEditor();

    const name = screen.getByLabelText('Business name');
    fireEvent.change(name, { target: { value: '' } });
    fireEvent.blur(name);
    await settleAutosave();

    expect(screen.getByText(/site name is required/i)).toBeInTheDocument();
    expect(mock.calls.updateProfile).toHaveLength(0);
  });
});
