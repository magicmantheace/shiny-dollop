// @vitest-environment jsdom
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it } from 'vitest';
import { App } from '../../src/App';
import { setWbmApi } from '../../src/api';
import type { Entity, EntityInput, EntityPatch, Link, WbmApi } from '../../shared/types';

/** In-memory fake of the real API surface — hermetic renderer tests only;
 *  the engine itself is covered against real SQLite in tests/backend. */
function makeFakeApi(): WbmApi {
  let seq = 0;
  const entities = new Map<string, Entity>();
  const links = new Map<string, Link>();
  const now = '2026-10-23T00:00:00.000Z';
  const mk = (input: EntityInput): Entity => ({
    id: `e${++seq}`,
    type: input.type,
    name: input.name,
    role: input.role ?? '',
    description: input.description ?? '',
    body: input.body ?? '',
    storyDate: input.storyDate ?? null,
    orderKey: input.orderKey ?? null,
    bornOrder: input.bornOrder ?? null,
    diedOrder: input.diedOrder ?? null,
    tags: input.tags ?? [],
    createdAt: now,
    updatedAt: now,
  });
  const hero = mk({ type: 'character', name: 'Sera Vane', bornOrder: 10, diedOrder: 90 });
  entities.set(hero.id, hero);
  const late = mk({ type: 'event', name: 'Sera at the Siege', orderKey: 120 });
  const early = mk({ type: 'event', name: 'Harbour Founded', orderKey: 1 });
  entities.set(late.id, late);
  entities.set(early.id, early);
  const l = { id: 'l1', sourceId: late.id, targetId: hero.id, label: 'features', createdAt: now };
  links.set(l.id, l);

  return {
    entities: {
      create: async (input) => {
        const e = mk(input);
        entities.set(e.id, e);
        return e;
      },
      get: async (id) => entities.get(id) ?? null,
      // The real IPC boundary structured-clones payloads, so every list()
      // returns fresh objects for the same ids — mirror that here.
      list: async (type) => [...entities.values()]
        .filter((e) => !type || e.type === type)
        .map((e) => ({ ...e, tags: [...e.tags] })),
      update: async (id, patch: EntityPatch) => {
        const cur = entities.get(id);
        if (!cur) throw new Error('not found');
        const next = { ...cur, ...patch, updatedAt: now };
        entities.set(id, next);
        return next;
      },
      remove: async (id) => {
        for (const [lid, link] of links) {
          if (link.sourceId === id || link.targetId === id) links.delete(lid);
        }
        return entities.delete(id);
      },
    },
    links: {
      add: async (sourceId, targetId, label = '') => {
        const link = { id: `l${++seq}`, sourceId, targetId, label, createdAt: now };
        links.set(link.id, link);
        return link;
      },
      remove: async (id) => links.delete(id),
      forEntity: async (entityId) =>
        [...links.values()]
          .filter((x) => x.sourceId === entityId || x.targetId === entityId)
          .map((x) => ({
            linkId: x.id,
            label: x.label,
            direction: (x.sourceId === entityId ? 'outgoing' : 'incoming') as 'outgoing' | 'incoming',
            entity: entities.get(x.sourceId === entityId ? x.targetId : x.sourceId) as Entity,
          })),
    },
    revisions: {
      list: async (entityId) => {
        const e = entities.get(entityId);
        return e ? [{ entityId, revNo: 1, snapshot: e, createdAt: now }] : [];
      },
    },
    timeline: {
      list: async () =>
        [...entities.values()]
          .filter((e) => e.type === 'event')
          .sort((a, b) => (a.orderKey ?? 0) - (b.orderKey ?? 0)),
    },
    continuity: {
      warnings: async () => [{
        code: 'EVENT_AFTER_DEATH' as const,
        eventId: late.id,
        eventName: late.name,
        characterId: hero.id,
        characterName: hero.name,
        message: '"Sera at the Siege" (order 120) is linked to Sera Vane, whose death is recorded at order 90.',
      }],
    },
    search: {
      query: async (text, type) =>
        [...entities.values()].filter(
          (e) => (!type || e.type === type)
            && `${e.name} ${e.description} ${e.body}`.toLowerCase().includes(text.toLowerCase()),
        ),
    },
    backup: {
      exportJson: async () => '{"format":"worldbuilding-manager.project","formatVersion":"1.0.0"}',
      importJson: async () => ({ entities: 0, links: 0, revisions: 0 }),
      exportMarkdown: async () => '# Worldbuilding project export',
    },
  };
}

beforeEach(() => {
  setWbmApi(makeFakeApi());
});

describe('App', () => {
  it('lists entities, shows the timeline in order and the continuity warning', async () => {
    render(<App />);
    expect((await screen.findAllByText(/Sera Vane/)).length).toBeGreaterThan(0);
    const timeline = screen.getByLabelText('Timeline');
    const items = within(timeline).getAllByRole('listitem').map((li) => li.textContent ?? '');
    expect(items[0]).toContain('Harbour Founded');
    expect(items[1]).toContain('Sera at the Siege');
    expect(await screen.findByText(/whose death is recorded at order 90/)).toBeInTheDocument();
  });

  it('creates a character through the form and shows it in the list', async () => {
    const user = userEvent.setup();
    render(<App />);
    await screen.findAllByText(/Sera Vane/);
    await user.type(screen.getByLabelText('Name'), 'Captain Morvain');
    await user.type(screen.getByLabelText('Role'), 'antagonist');
    await user.click(screen.getByRole('button', { name: 'Create' }));
    expect(await screen.findByText(/Created Character "Captain Morvain"\./)).toBeInTheDocument();
    expect(screen.getAllByText(/Captain Morvain/).length).toBeGreaterThan(0);
  });

  it('search narrows the entity list', async () => {
    const user = userEvent.setup();
    render(<App />);
    await within(screen.getByLabelText('Entities')).findByText(/Harbour Founded/);
    await user.type(screen.getByLabelText('Search text'), 'Siege');
    await user.click(screen.getByRole('button', { name: 'Search' }));
    const list = screen.getByLabelText('Entities');
    expect(await within(list).findByText(/Sera at the Siege/)).toBeInTheDocument();
    expect(within(list).queryByText(/Harbour Founded/)).not.toBeInTheDocument();
  });

  it('preserves unsaved entity edits when a relationship is added', async () => {
    const user = userEvent.setup();
    render(<App />);
    await screen.findAllByText(/Sera Vane/);
    const entitiesPanel = screen.getByLabelText('Entities');
    await user.click(within(entitiesPanel).getByRole('button', { name: /Sera Vane/ }));

    const nameInput = screen.getByLabelText('Edit name') as HTMLInputElement;
    const bodyInput = screen.getByLabelText('Edit body') as HTMLTextAreaElement;
    await user.clear(nameInput);
    await user.type(nameInput, 'Unsaved Draft Name');
    await user.type(bodyInput, 'Unsaved draft notes.');

    // Adding a relationship triggers refresh(), which replaces the entity
    // objects — the unsaved drafts must survive it.
    const targetSelect = screen.getByLabelText('Link target') as HTMLSelectElement;
    const target = [...targetSelect.options].find((o) => o.textContent?.includes('Harbour Founded'));
    expect(target).toBeDefined();
    await user.selectOptions(targetSelect, target?.value ?? '');
    await user.click(screen.getByRole('button', { name: 'Add link' }));
    expect(await screen.findByText('Link added.')).toBeInTheDocument();

    expect(nameInput.value).toBe('Unsaved Draft Name');
    expect(bodyInput.value).toContain('Unsaved draft notes.');
  });

  it('exports a JSON backup into the output box', async () => {
    const user = userEvent.setup();
    render(<App />);
    await screen.findAllByText(/Sera Vane/);
    await user.click(screen.getByRole('button', { name: 'Export JSON backup' }));
    const out = screen.getByLabelText('Backup output') as HTMLTextAreaElement;
    expect(out.value).toContain('worldbuilding-manager.project');
  });
});
