import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { ReactElement } from 'react';
import { ENTITY_TYPES } from '../shared/types';
import type { ContinuityWarning, Entity, EntityType, LinkedEntity, Revision } from '../shared/types';
import { api } from './api';

const TYPE_LABELS: Record<EntityType, string> = {
  character: 'Character',
  location: 'Location',
  faction: 'Faction',
  event: 'Timeline event',
  note: 'Note',
};

/**
 * Strict parser for the timeline-order fields (Timeline order, Born order,
 * Died order). Only an empty field means "no order recorded" (null); any
 * other input must be a whole number in its entirety. Previously this used
 * parseInt, which silently coerced `10.9` to `10`, `12abc` to `12` and
 * non-numeric text to null — creation then reported success while
 * persisting a different order than the author typed, or silently
 * disabling the continuity check. Invalid input now throws, and the
 * caller surfaces the error instead of saving.
 */
export function parseOrderOrNull(fieldLabel: string, raw: string): number | null {
  const v = raw.trim();
  if (v === '') return null;
  if (!/^[+-]?\d+$/.test(v)) {
    throw new Error(`${fieldLabel} must be a whole number or left empty.`);
  }
  const n = Number(v);
  if (!Number.isSafeInteger(n)) {
    throw new Error(`${fieldLabel} must be a whole number or left empty.`);
  }
  return n;
}

export function App(): ReactElement {
  const [entities, setEntities] = useState<Entity[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [linked, setLinked] = useState<LinkedEntity[]>([]);
  const [revisions, setRevisions] = useState<Revision[]>([]);
  const [timeline, setTimeline] = useState<Entity[]>([]);
  const [warnings, setWarnings] = useState<ContinuityWarning[]>([]);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');

  // create form
  const [newType, setNewType] = useState<EntityType>('character');
  const [newName, setNewName] = useState('');
  const [newRole, setNewRole] = useState('');
  const [newDescription, setNewDescription] = useState('');
  const [newBody, setNewBody] = useState('');
  const [newTags, setNewTags] = useState('');
  const [newStoryDate, setNewStoryDate] = useState('');
  const [newOrderKey, setNewOrderKey] = useState('');
  const [newBorn, setNewBorn] = useState('');
  const [newDied, setNewDied] = useState('');

  // edit form (selected entity)
  const [editName, setEditName] = useState('');
  const [editDescription, setEditDescription] = useState('');
  const [editBody, setEditBody] = useState('');
  const [editRole, setEditRole] = useState('');
  const [editStoryDate, setEditStoryDate] = useState('');
  const [editOrderKey, setEditOrderKey] = useState('');
  const [editBorn, setEditBorn] = useState('');
  const [editDied, setEditDied] = useState('');

  // link form
  const [linkTarget, setLinkTarget] = useState('');
  const [linkLabel, setLinkLabel] = useState('');

  // search
  const [searchText, setSearchText] = useState('');
  const [searchType, setSearchType] = useState<'' | EntityType>('');
  const [searchResults, setSearchResults] = useState<Entity[] | null>(null);

  // backup
  const [backupText, setBackupText] = useState('');
  const [importText, setImportText] = useState('');

  const selected = useMemo(
    () => entities.find((e) => e.id === selectedId) ?? null,
    [entities, selectedId],
  );

  const refresh = useCallback(async (keepSelection = true) => {
    const [all, tl, ws] = await Promise.all([
      api().entities.list(),
      api().timeline.list(),
      api().continuity.warnings(),
    ]);
    setEntities(all);
    setTimeline(tl);
    setWarnings(ws);
    if (!keepSelection) setSelectedId(null);
  }, []);

  useEffect(() => {
    refresh(false).catch((e: Error) => setError(e.message));
  }, [refresh]);

  // The entity id the edit drafts were last initialized for. refresh()
  // replaces the entities array with fresh objects for the SAME id (e.g.
  // after adding/removing a relationship), and re-initializing on every
  // such object would silently discard unsaved edits — so the drafts are
  // initialized only when the selection actually changes to a new entity.
  // A successful save sends exactly the draft values, so no re-init is
  // needed afterwards either.
  const draftEntityIdRef = useRef<string | null>(null);

  useEffect(() => {
    if (!selected) {
      draftEntityIdRef.current = null;
      setLinked([]);
      setRevisions([]);
      return;
    }
    if (draftEntityIdRef.current !== selected.id) {
      draftEntityIdRef.current = selected.id;
      setEditName(selected.name);
      setEditDescription(selected.description);
      setEditBody(selected.body);
      setEditRole(selected.role);
      setEditStoryDate(selected.storyDate ?? '');
      setEditOrderKey(selected.orderKey === null ? '' : String(selected.orderKey));
      setEditBorn(selected.bornOrder === null ? '' : String(selected.bornOrder));
      setEditDied(selected.diedOrder === null ? '' : String(selected.diedOrder));
    }
    Promise.all([api().links.forEntity(selected.id), api().revisions.list(selected.id)])
      .then(([l, r]) => {
        setLinked(l);
        setRevisions(r);
      })
      .catch((e: Error) => setError(e.message));
  }, [selected]);

  async function run(fn: () => Promise<void>): Promise<void> {
    setError('');
    setMessage('');
    try {
      await fn();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  const createEntity = (): void => {
    void run(async () => {
      const created = await api().entities.create({
        type: newType,
        name: newName,
        role: newType === 'character' ? newRole : '',
        description: newDescription,
        body: newBody,
        storyDate: newType === 'event' ? newStoryDate || null : null,
        orderKey: newType === 'event' ? parseOrderOrNull('Timeline order', newOrderKey) : null,
        bornOrder: newType === 'character' ? parseOrderOrNull('Born order', newBorn) : null,
        diedOrder: newType === 'character' ? parseOrderOrNull('Died order', newDied) : null,
        tags: newTags.split(',').map((t) => t.trim()).filter(Boolean),
      });
      setNewName('');
      setNewDescription('');
      setNewBody('');
      setMessage(`Created ${TYPE_LABELS[created.type]} "${created.name}".`);
      await refresh();
      setSelectedId(created.id);
    });
  };

  const saveEdits = (): void => {
    if (!selected) return;
    void run(async () => {
      // The type-specific fields that determine timeline continuity are
      // editable here too — the engine/IPC patch has always supported
      // them, so correcting an event's date/order or a character's
      // birth/death order no longer requires delete-and-recreate (which
      // lost links and revision history). The order fields go through
      // the strict parser: invalid input throws and nothing is saved.
      const updated = await api().entities.update(selected.id, {
        name: editName,
        description: editDescription,
        body: editBody,
        ...(selected.type === 'character'
          ? {
              role: editRole,
              bornOrder: parseOrderOrNull('Born order', editBorn),
              diedOrder: parseOrderOrNull('Died order', editDied),
            }
          : {}),
        ...(selected.type === 'event'
          ? {
              storyDate: editStoryDate.trim() === '' ? null : editStoryDate,
              orderKey: parseOrderOrNull('Timeline order', editOrderKey),
            }
          : {}),
      });
      setMessage(`Saved "${updated.name}".`);
      await refresh();
    });
  };

  const deleteSelected = (): void => {
    if (!selected) return;
    void run(async () => {
      await api().entities.remove(selected.id);
      setMessage(`Deleted "${selected.name}" and its links.`);
      setSelectedId(null);
      await refresh(false);
    });
  };

  const addLink = (): void => {
    if (!selected || !linkTarget) return;
    void run(async () => {
      await api().links.add(selected.id, linkTarget, linkLabel);
      setMessage('Link added.');
      setLinkLabel('');
      await refresh();
      const l = await api().links.forEntity(selected.id);
      setLinked(l);
    });
  };

  const doSearch = (): void => {
    void run(async () => {
      const results = await api().search.query(searchText, searchType === '' ? undefined : searchType);
      setSearchResults(results);
    });
  };

  const listToShow = searchResults ?? entities;

  return (
    <div className="layout">
      <div>
        <section className="panel" aria-label="Create entity">
          <h2>New entity</h2>
          <label>
            Type
            <select aria-label="New entity type" value={newType} onChange={(e) => setNewType(e.target.value as EntityType)}>
              {ENTITY_TYPES.map((t) => (
                <option key={t} value={t}>{TYPE_LABELS[t]}</option>
              ))}
            </select>
          </label>
          <label>
            Name
            <input aria-label="Name" value={newName} onChange={(e) => setNewName(e.target.value)} />
          </label>
          {newType === 'character' && (
            <>
              <label>
                Role
                <input aria-label="Role" value={newRole} onChange={(e) => setNewRole(e.target.value)} />
              </label>
              <label>
                Born (timeline order)
                <input aria-label="Born order" value={newBorn} onChange={(e) => setNewBorn(e.target.value)} />
              </label>
              <label>
                Died (timeline order)
                <input aria-label="Died order" value={newDied} onChange={(e) => setNewDied(e.target.value)} />
              </label>
            </>
          )}
          {newType === 'event' && (
            <>
              <label>
                Story date
                <input aria-label="Story date" value={newStoryDate} onChange={(e) => setNewStoryDate(e.target.value)} />
              </label>
              <label>
                Timeline order
                <input aria-label="Timeline order" value={newOrderKey} onChange={(e) => setNewOrderKey(e.target.value)} />
              </label>
            </>
          )}
          <label>
            Description
            <input aria-label="Description" value={newDescription} onChange={(e) => setNewDescription(e.target.value)} />
          </label>
          <label>
            Notes (markdown-friendly)
            <textarea aria-label="Body" rows={4} value={newBody} onChange={(e) => setNewBody(e.target.value)} />
          </label>
          <label>
            Tags (comma separated)
            <input aria-label="Tags" value={newTags} onChange={(e) => setNewTags(e.target.value)} />
          </label>
          <button type="button" onClick={createEntity}>Create</button>
        </section>

        <section className="panel" aria-label="Search">
          <h2>Search</h2>
          <input aria-label="Search text" value={searchText} onChange={(e) => setSearchText(e.target.value)} />
          <select aria-label="Search type filter" value={searchType} onChange={(e) => setSearchType(e.target.value as '' | EntityType)}>
            <option value="">All types</option>
            {ENTITY_TYPES.map((t) => (
              <option key={t} value={t}>{TYPE_LABELS[t]}</option>
            ))}
          </select>
          <button type="button" onClick={doSearch}>Search</button>
          {searchResults !== null && (
            <button type="button" onClick={() => setSearchResults(null)}>Clear search</button>
          )}
        </section>

        <section className="panel" aria-label="Entities">
          <h2>{searchResults !== null ? 'Search results' : 'Entities'}</h2>
          {listToShow.length === 0 && <p>Nothing here yet.</p>}
          {listToShow.map((e) => (
            <button
              key={e.id}
              type="button"
              className="entity-item"
              aria-current={e.id === selectedId}
              onClick={() => setSelectedId(e.id)}
            >
              {e.name} <small>({TYPE_LABELS[e.type]})</small>
            </button>
          ))}
        </section>
      </div>

      <div>
        {error && <p className="error" role="alert">{error}</p>}
        {message && <p className="ok" role="status">{message}</p>}

        {warnings.length > 0 && (
          <section className="panel" aria-label="Continuity warnings">
            <h2>Continuity warnings</h2>
            {warnings.map((w) => (
              <p key={`${w.code}-${w.eventId}-${w.characterId}`} className="warning">{w.message}</p>
            ))}
          </section>
        )}

        <section className="panel" aria-label="Timeline">
          <h2>Timeline</h2>
          {timeline.length === 0 && <p>No timeline events yet.</p>}
          <ol>
            {timeline.map((e) => (
              <li key={e.id}>
                {e.orderKey !== null ? `#${e.orderKey} ` : ''}{e.name}
                {e.storyDate ? ` — ${e.storyDate}` : ''}
              </li>
            ))}
          </ol>
        </section>

        {selected && (
          <section className="panel" aria-label="Entity detail">
            <h2>{selected.name}</h2>
            <p>
              {TYPE_LABELS[selected.type]}
              {selected.role ? ` — ${selected.role}` : ''}
              {selected.tags.length > 0 ? ` · tags: ${selected.tags.join(', ')}` : ''}
            </p>
            <label>
              Name
              <input aria-label="Edit name" value={editName} onChange={(e) => setEditName(e.target.value)} />
            </label>
            <label>
              Description
              <input aria-label="Edit description" value={editDescription} onChange={(e) => setEditDescription(e.target.value)} />
            </label>
            {selected.type === 'character' && (
              <>
                <label>
                  Role
                  <input aria-label="Edit role" value={editRole} onChange={(e) => setEditRole(e.target.value)} />
                </label>
                <label>
                  Born (timeline order)
                  <input aria-label="Edit born order" value={editBorn} onChange={(e) => setEditBorn(e.target.value)} />
                </label>
                <label>
                  Died (timeline order)
                  <input aria-label="Edit died order" value={editDied} onChange={(e) => setEditDied(e.target.value)} />
                </label>
              </>
            )}
            {selected.type === 'event' && (
              <>
                <label>
                  Story date
                  <input aria-label="Edit story date" value={editStoryDate} onChange={(e) => setEditStoryDate(e.target.value)} />
                </label>
                <label>
                  Timeline order
                  <input aria-label="Edit timeline order" value={editOrderKey} onChange={(e) => setEditOrderKey(e.target.value)} />
                </label>
              </>
            )}
            <label>
              Notes
              <textarea aria-label="Edit body" rows={5} value={editBody} onChange={(e) => setEditBody(e.target.value)} />
            </label>
            <button type="button" onClick={saveEdits}>Save changes</button>
            <button type="button" onClick={deleteSelected}>Delete entity</button>

            <h3>Links &amp; relationships</h3>
            {linked.length === 0 && <p>No links yet.</p>}
            <ul>
              {linked.map((l) => (
                <li key={l.linkId}>
                  {l.label ? `${l.label}: ` : ''}{l.entity.name} ({TYPE_LABELS[l.entity.type]})
                  <button
                    type="button"
                    aria-label={`Remove link to ${l.entity.name}`}
                    onClick={() => void run(async () => {
                      await api().links.remove(l.linkId);
                      await refresh();
                      setLinked(await api().links.forEntity(selected.id));
                    })}
                  >
                    Remove
                  </button>
                </li>
              ))}
            </ul>
            <label>
              Link to
              <select aria-label="Link target" value={linkTarget} onChange={(e) => setLinkTarget(e.target.value)}>
                <option value="">Choose an entity…</option>
                {entities.filter((e) => e.id !== selected.id).map((e) => (
                  <option key={e.id} value={e.id}>{e.name} ({TYPE_LABELS[e.type]})</option>
                ))}
              </select>
            </label>
            <label>
              Label (ally, rival, family, located-in…)
              <input aria-label="Link label" value={linkLabel} onChange={(e) => setLinkLabel(e.target.value)} />
            </label>
            <button type="button" onClick={addLink}>Add link</button>

            <h3>Revision history</h3>
            {revisions.length === 0 && <p>No revisions recorded.</p>}
            <ul>
              {revisions.map((r) => (
                <li key={r.revNo}>Revision {r.revNo} — {r.snapshot.name} ({r.createdAt})</li>
              ))}
            </ul>
          </section>
        )}

        <section className="panel" aria-label="Backup">
          <h2>Project backup</h2>
          <button
            type="button"
            onClick={() => void run(async () => setBackupText(await api().backup.exportJson()))}
          >
            Export JSON backup
          </button>
          <button
            type="button"
            onClick={() => void run(async () => setBackupText(await api().backup.exportMarkdown()))}
          >
            Export Markdown
          </button>
          <label>
            Backup output
            <textarea aria-label="Backup output" rows={8} readOnly value={backupText} />
          </label>
          <label>
            Import a JSON backup (replaces the current project)
            <textarea aria-label="Import JSON" rows={6} value={importText} onChange={(e) => setImportText(e.target.value)} />
          </label>
          <button
            type="button"
            onClick={() => void run(async () => {
              const result = await api().backup.importJson(importText);
              setMessage(`Imported ${result.entities} entities and ${result.links} links.`);
              setSelectedId(null);
              await refresh(false);
            })}
          >
            Import backup
          </button>
        </section>
      </div>
    </div>
  );
}
