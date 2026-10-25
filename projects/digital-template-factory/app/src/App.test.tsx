import { afterEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { App } from './App';
import { mockDtf, unmockDtf } from './test-utils';

afterEach(() => {
  unmockDtf();
  vi.restoreAllMocks();
  localStorage.clear();
});

describe('App', () => {
  it('starts on the template gallery and switches views via nav', async () => {
    mockDtf();
    const user = userEvent.setup();
    render(<App />);

    // Gallery is the default view.
    expect(await screen.findByRole('heading', { name: 'Templates' })).toBeInTheDocument();
    expect(await screen.findByText('Simple Invoice')).toBeInTheDocument();

    // Nav to documents.
    await user.click(screen.getByRole('button', { name: 'My documents' }));
    expect(await screen.findByRole('heading', { name: 'My documents' })).toBeInTheDocument();
    expect(screen.getByText(/No documents yet/)).toBeInTheDocument();

    // Back to templates.
    await user.click(screen.getByRole('button', { name: 'Templates' }));
    expect(await screen.findByRole('heading', { name: 'Templates' })).toBeInTheDocument();
  });

  it('opens the editor when a new document is created from the gallery', async () => {
    const dtf = mockDtf();
    const { makeDoc } = await import('./test-utils');
    dtf.documents.create.mockResolvedValue(makeDoc({ id: 'doc-7' }));
    dtf.documents.get.mockResolvedValue(makeDoc({ id: 'doc-7' }));
    const user = userEvent.setup();
    render(<App />);

    await user.click(
      await screen.findByRole('button', { name: 'New document from Simple Invoice' }),
    );

    expect(await screen.findByRole('heading', { name: /Simple Invoice/ })).toBeInTheDocument();
    expect(screen.getByLabelText(/Client name/)).toBeInTheDocument();
  });
});
