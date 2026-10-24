import { useCallback, useEffect, useRef, useState } from 'react';
import type {
  Campaign,
  Character,
  Encounter,
  LogEntry,
  MemoryEntry,
  MemoryKind,
  NarrationSettings,
  Session,
} from '../../shared/types';
import { ATTRIBUTES, ATTRIBUTE_LABELS, DIFFICULTIES } from '../../shared/ruleset';
import type { Attribute, DifficultyKey } from '../../shared/ruleset';
import { api, formatError } from '../lib/aidm';

function downloadText(filename: string, text: string): void {
  const blob = new Blob([text], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

export function App() {
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [campaignId, setCampaignId] = useState<string>('');
  const [newCampaignName, setNewCampaignName] = useState('');
  const [newCampaignSetting, setNewCampaignSetting] = useState('');
  const [newCampaignSeed, setNewCampaignSeed] = useState('');

  const [sessions, setSessions] = useState<Session[]>([]);
  const [sessionId, setSessionId] = useState<string>('');
  const [newSessionTitle, setNewSessionTitle] = useState('');
  const [sessionNotes, setSessionNotes] = useState('');

  const [characters, setCharacters] = useState<Character[]>([]);
  const [charName, setCharName] = useState('');
  const [charKind, setCharKind] = useState<'pc' | 'npc'>('pc');
  const [charArchetype, setCharArchetype] = useState('');
  const [charHpMax, setCharHpMax] = useState(10);
  const [charStats, setCharStats] = useState<Record<Attribute, number>>({
    might: 0,
    agility: 0,
    wits: 0,
    spirit: 0,
  });

  const [notation, setNotation] = useState('2d6');
  const [rollLabel, setRollLabel] = useState('');
  const [lastRoll, setLastRoll] = useState<string | null>(null);
  const [checkCharacterId, setCheckCharacterId] = useState('');
  const [checkAttribute, setCheckAttribute] = useState<Attribute>('might');
  const [checkDifficulty, setCheckDifficulty] = useState<DifficultyKey>('standard');

  const [encounter, setEncounter] = useState<Encounter | null>(null);
  const [encounterName, setEncounterName] = useState('');
  const [encounterPicks, setEncounterPicks] = useState<Record<string, boolean>>({});
  const [hpAmounts, setHpAmounts] = useState<Record<string, number>>({});

  const [log, setLog] = useState<LogEntry[]>([]);
  const [noteText, setNoteText] = useState('');

  const [memory, setMemory] = useState<MemoryEntry[]>([]);
  const [memoryQuery, setMemoryQuery] = useState('');
  const [memKind, setMemKind] = useState<MemoryKind>('npc');
  const [memTitle, setMemTitle] = useState('');
  const [memBody, setMemBody] = useState('');
  const [memTags, setMemTags] = useState('');

  const [settings, setSettings] = useState<NarrationSettings>({
    narrator: 'mock',
    endpoint: 'http://127.0.0.1:11434',
    model: '',
  });

  const [exportText, setExportText] = useState('');
  const [importText, setImportText] = useState('');
  const [wbText, setWbText] = useState('');
  const [dungeonText, setDungeonText] = useState('');

  const campaign = campaigns.find((c) => c.id === campaignId) ?? null;
  const activeSession = sessions.find((s) => s.id === sessionId) ?? null;

  const reportError = useCallback((err: unknown) => {
    setError(formatError(err));
  }, []);

  const refreshCampaigns = useCallback(async () => {
    try {
      setCampaigns(await api().campaignsList());
    } catch (err) {
      reportError(err);
    }
  }, [reportError]);

  const refreshAll = useCallback(async () => {
    if (!campaignId) return;
    try {
      const [chars, sess, entries, mem, active, camp] = await Promise.all([
        api().charactersList(campaignId),
        api().sessionsList(campaignId),
        api().logList(campaignId),
        api().memoryList(campaignId),
        api().encountersGetActive(campaignId),
        api().campaignsGet(campaignId),
      ]);
      setCharacters(chars);
      setSessions(sess);
      setLog(entries);
      setMemory(mem);
      setEncounter(active);
      setCampaigns((prev) => prev.map((c) => (c.id === camp.id ? camp : c)));
    } catch (err) {
      reportError(err);
    }
  }, [campaignId, reportError]);

  useEffect(() => {
    void refreshCampaigns();
    void (async () => {
      try {
        setSettings(await api().settingsGet());
      } catch (err) {
        reportError(err);
      }
    })();
  }, [refreshCampaigns, reportError]);

  useEffect(() => {
    void refreshAll();
  }, [refreshAll]);

  // Session-notes draft sync: refreshAll installs newly deserialized
  // session objects on every action (dice rolls, damage, memory edits…),
  // so keying the reset off the session OBJECT would silently discard
  // unsaved notes. Reset the draft only when the selected session
  // changes, or when the persisted notes change while the draft is clean
  // (e.g. a deliberate save just landed). A dirty draft always wins.
  const notesSyncRef = useRef<{ sessionId: string; persisted: string; draft: string } | null>(
    null,
  );
  const updateSessionNotes = useCallback((value: string) => {
    setSessionNotes(value);
    if (notesSyncRef.current) notesSyncRef.current.draft = value;
  }, []);

  useEffect(() => {
    if (!activeSession) {
      notesSyncRef.current = null;
      setSessionNotes('');
      return;
    }
    const sync = notesSyncRef.current;
    if (!sync || sync.sessionId !== activeSession.id) {
      notesSyncRef.current = {
        sessionId: activeSession.id,
        persisted: activeSession.notes,
        draft: activeSession.notes,
      };
      setSessionNotes(activeSession.notes);
      return;
    }
    if (sync.persisted !== activeSession.notes) {
      const wasClean = sync.draft === sync.persisted;
      sync.persisted = activeSession.notes;
      if (wasClean) {
        sync.draft = activeSession.notes;
        setSessionNotes(activeSession.notes);
      }
    }
  }, [activeSession]);

  const run = useCallback(
    async (action: () => Promise<void>) => {
      setError(null);
      try {
        await action();
      } catch (err) {
        reportError(err);
      }
    },
    [reportError],
  );

  return (
    <div className="app">
      <header className="app-header">
        <h1>AI Dungeon Master</h1>
        <p className="subtitle">
          Offline campaign companion. The deterministic house-rules engine decides every
          outcome — every roll is logged with its full breakdown. Narration is flavor only
          and can never change a result.
        </p>
      </header>

      {error && (
        <div className="banner banner-error" role="alert">
          {error}
        </div>
      )}
      {notice && <div className="banner banner-ok">{notice}</div>}

      <main className="app-main">
        <section className="panel" aria-label="Campaigns">
          <h2>Campaigns</h2>
          <div className="row">
            <label>
              Active campaign
              <select
                value={campaignId}
                onChange={(e) => {
                  setCampaignId(e.target.value);
                  setSessionId('');
                }}
              >
                <option value="">— select —</option>
                {campaigns.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </select>
            </label>
            {campaign && (
              <span className="muted">
                Dice seed “{campaign.seed}” · stream state {campaign.diceState}
              </span>
            )}
          </div>
          <div className="row">
            <label>
              Name
              <input value={newCampaignName} onChange={(e) => setNewCampaignName(e.target.value)} />
            </label>
            <label>
              Setting
              <input
                value={newCampaignSetting}
                onChange={(e) => setNewCampaignSetting(e.target.value)}
              />
            </label>
            <label>
              Dice seed (optional)
              <input value={newCampaignSeed} onChange={(e) => setNewCampaignSeed(e.target.value)} />
            </label>
            <button
              onClick={() =>
                void run(async () => {
                  const created = await api().campaignsCreate({
                    name: newCampaignName,
                    setting: newCampaignSetting,
                    ...(newCampaignSeed ? { seed: newCampaignSeed } : {}),
                  });
                  setNewCampaignName('');
                  setNewCampaignSetting('');
                  setNewCampaignSeed('');
                  await refreshCampaigns();
                  setCampaignId(created.id);
                })
              }
            >
              Create campaign
            </button>
          </div>

          {campaign && (
            <div className="row">
              <label>
                Session
                <select value={sessionId} onChange={(e) => setSessionId(e.target.value)}>
                  <option value="">— none —</option>
                  {sessions.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.title}
                      {s.endedAt ? ' (ended)' : ''}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                New session title
                <input value={newSessionTitle} onChange={(e) => setNewSessionTitle(e.target.value)} />
              </label>
              <button
                onClick={() =>
                  void run(async () => {
                    const created = await api().sessionsCreate(campaign.id, {
                      title: newSessionTitle,
                    });
                    setNewSessionTitle('');
                    await refreshAll();
                    setSessionId(created.id);
                  })
                }
              >
                Start session
              </button>
              {activeSession && !activeSession.endedAt && (
                <button
                  onClick={() =>
                    void run(async () => {
                      await api().sessionsEnd(activeSession.id);
                      await refreshAll();
                    })
                  }
                >
                  End session
                </button>
              )}
            </div>
          )}
          {activeSession && (
            <div>
              <label>
                Session notes
                <textarea
                  value={sessionNotes}
                  onChange={(e) => updateSessionNotes(e.target.value)}
                  rows={3}
                />
              </label>
              <button
                onClick={() =>
                  void run(async () => {
                    await api().sessionsUpdateNotes(activeSession.id, sessionNotes);
                    await refreshAll();
                    setNotice('Session notes saved.');
                  })
                }
              >
                Save notes
              </button>
            </div>
          )}
        </section>

        {campaign && (
          <>
            <section className="panel" aria-label="Characters">
              <h2>Characters</h2>
              <ul className="list">
                {characters.map((c) => (
                  <li key={c.id}>
                    <strong>{c.name}</strong> ({c.kind === 'pc' ? 'PC' : 'NPC'}
                    {c.archetype ? `, ${c.archetype}` : ''}) — HP {c.hpCurrent}/{c.hpMax} ·{' '}
                    {ATTRIBUTES.map((a) => `${ATTRIBUTE_LABELS[a]} ${c.stats[a]}`).join(' · ')}
                    {c.inventory.length > 0 && <> · carries: {c.inventory.join(', ')}</>}
                    <button
                      className="small"
                      disabled={encounter?.combatants.some((cb) => cb.characterId === c.id) ?? false}
                      title={
                        encounter?.combatants.some((cb) => cb.characterId === c.id)
                          ? 'In the active encounter — end it before deleting'
                          : undefined
                      }
                      onClick={() =>
                        void run(async () => {
                          await api().charactersDelete(c.id);
                          await refreshAll();
                        })
                      }
                    >
                      Delete
                    </button>
                  </li>
                ))}
                {characters.length === 0 && <li className="muted">No characters yet.</li>}
              </ul>
              <div className="row">
                <label>
                  Name
                  <input value={charName} onChange={(e) => setCharName(e.target.value)} />
                </label>
                <label>
                  Kind
                  <select value={charKind} onChange={(e) => setCharKind(e.target.value as 'pc' | 'npc')}>
                    <option value="pc">PC</option>
                    <option value="npc">NPC</option>
                  </select>
                </label>
                <label>
                  Archetype
                  <input value={charArchetype} onChange={(e) => setCharArchetype(e.target.value)} />
                </label>
                <label>
                  Max HP
                  <input
                    type="number"
                    value={charHpMax}
                    onChange={(e) => setCharHpMax(Number(e.target.value))}
                  />
                </label>
                {ATTRIBUTES.map((a) => (
                  <label key={a}>
                    {ATTRIBUTE_LABELS[a]}
                    <input
                      type="number"
                      value={charStats[a]}
                      onChange={(e) =>
                        setCharStats((prev) => ({ ...prev, [a]: Number(e.target.value) }))
                      }
                    />
                  </label>
                ))}
                <button
                  onClick={() =>
                    void run(async () => {
                      await api().charactersCreate(campaign.id, {
                        kind: charKind,
                        name: charName,
                        archetype: charArchetype,
                        hpMax: charHpMax,
                        stats: charStats,
                      });
                      setCharName('');
                      setCharArchetype('');
                      await refreshAll();
                    })
                  }
                >
                  Add character
                </button>
              </div>
            </section>

            <section className="panel" aria-label="Dice">
              <h2>Dice &amp; checks</h2>
              <div className="row">
                <label>
                  Notation
                  <input value={notation} onChange={(e) => setNotation(e.target.value)} />
                </label>
                <label>
                  Label
                  <input value={rollLabel} onChange={(e) => setRollLabel(e.target.value)} />
                </label>
                <button
                  onClick={() =>
                    void run(async () => {
                      const res = await api().diceRoll(campaign.id, {
                        notation,
                        ...(rollLabel ? { label: rollLabel } : {}),
                        sessionId: sessionId || null,
                      });
                      setLastRoll(
                        `${res.outcome.notation}: [${res.outcome.dice.join(', ')}] = ${res.outcome.total} (stream ${res.outcome.stateBefore} → ${res.outcome.stateAfter})`,
                      );
                      await refreshAll();
                    })
                  }
                >
                  Roll dice
                </button>
              </div>
              <div className="row">
                <label>
                  Character
                  <select
                    value={checkCharacterId}
                    onChange={(e) => setCheckCharacterId(e.target.value)}
                  >
                    <option value="">— select —</option>
                    {characters.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.name}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  Attribute
                  <select
                    value={checkAttribute}
                    onChange={(e) => setCheckAttribute(e.target.value as Attribute)}
                  >
                    {ATTRIBUTES.map((a) => (
                      <option key={a} value={a}>
                        {ATTRIBUTE_LABELS[a]}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  Difficulty
                  <select
                    value={checkDifficulty}
                    onChange={(e) => setCheckDifficulty(e.target.value as DifficultyKey)}
                  >
                    {DIFFICULTIES.map((d) => (
                      <option key={d.key} value={d.key}>
                        {d.label} ({d.target})
                      </option>
                    ))}
                  </select>
                </label>
                <button
                  onClick={() =>
                    void run(async () => {
                      const res = await api().checkRoll(campaign.id, {
                        characterId: checkCharacterId,
                        attribute: checkAttribute,
                        difficulty: checkDifficulty,
                        sessionId: sessionId || null,
                      });
                      setLastRoll(
                        `Check: [${res.outcome.dice.join(', ')}] + ${res.outcome.modifier} = ${res.outcome.total} vs ${res.target} — ${res.succeeded ? 'SUCCESS' : 'FAILURE'}`,
                      );
                      await refreshAll();
                    })
                  }
                >
                  Roll check
                </button>
              </div>
              {lastRoll && <p className="result">{lastRoll}</p>}
            </section>

            <section className="panel" aria-label="Encounter">
              <h2>Encounter</h2>
              {encounter ? (
                <>
                  <p>
                    <strong>{encounter.name}</strong> — round {encounter.round}
                  </p>
                  <ol className="list">
                    {encounter.combatants.map((cb, i) => {
                      const character = characters.find((c) => c.id === cb.characterId);
                      return (
                        <li key={cb.characterId} className={i === encounter.turnIndex ? 'turn' : ''}>
                          {i === encounter.turnIndex ? '▶ ' : ''}
                          {cb.name} — initiative {cb.initiativeTotal} · HP{' '}
                          {character ? `${character.hpCurrent}/${character.hpMax}` : '?'}
                          <span className="row inline">
                            <input
                              type="number"
                              aria-label={`Amount for ${cb.name}`}
                              value={hpAmounts[cb.characterId] ?? 1}
                              onChange={(e) =>
                                setHpAmounts((prev) => ({
                                  ...prev,
                                  [cb.characterId]: Number(e.target.value),
                                }))
                              }
                            />
                            <button
                              className="small"
                              onClick={() =>
                                void run(async () => {
                                  await api().encountersApplyDamage(encounter.id, {
                                    characterId: cb.characterId,
                                    amount: hpAmounts[cb.characterId] ?? 1,
                                  });
                                  await refreshAll();
                                })
                              }
                            >
                              Damage
                            </button>
                            <button
                              className="small"
                              onClick={() =>
                                void run(async () => {
                                  await api().encountersApplyHeal(encounter.id, {
                                    characterId: cb.characterId,
                                    amount: hpAmounts[cb.characterId] ?? 1,
                                  });
                                  await refreshAll();
                                })
                              }
                            >
                              Heal
                            </button>
                          </span>
                        </li>
                      );
                    })}
                  </ol>
                  <div className="row">
                    <button
                      onClick={() =>
                        void run(async () => {
                          setEncounter(await api().encountersAdvanceTurn(encounter.id));
                        })
                      }
                    >
                      Advance turn
                    </button>
                    <button
                      onClick={() =>
                        void run(async () => {
                          await api().encountersEnd(encounter.id);
                          await refreshAll();
                        })
                      }
                    >
                      End encounter
                    </button>
                  </div>
                </>
              ) : (
                <div className="row">
                  <label>
                    Encounter name
                    <input value={encounterName} onChange={(e) => setEncounterName(e.target.value)} />
                  </label>
                  {characters.map((c) => (
                    <label key={c.id} className="check">
                      <input
                        type="checkbox"
                        checked={encounterPicks[c.id] ?? false}
                        onChange={(e) =>
                          setEncounterPicks((prev) => ({ ...prev, [c.id]: e.target.checked }))
                        }
                      />
                      {c.name}
                    </label>
                  ))}
                  <button
                    onClick={() =>
                      void run(async () => {
                        const created = await api().encountersStart(campaign.id, {
                          name: encounterName,
                          characterIds: characters
                            .filter((c) => encounterPicks[c.id])
                            .map((c) => c.id),
                          sessionId: sessionId || null,
                        });
                        setEncounter(created);
                        setEncounterName('');
                        await refreshAll();
                      })
                    }
                  >
                    Start encounter
                  </button>
                </div>
              )}
            </section>

            <section className="panel" aria-label="Session log">
              <h2>Session log</h2>
              <ul className="list log">
                {log.map((entry) => (
                  <li key={entry.id}>
                    <span className="muted">#{entry.seq} · {entry.kind}</span> {entry.text}
                    {entry.narration ? (
                      <div className="narration">
                        “{entry.narration}” <span className="muted">({entry.narrationSource})</span>
                      </div>
                    ) : (
                      <button
                        className="small"
                        onClick={() =>
                          void run(async () => {
                            await api().narrate(entry.id);
                            await refreshAll();
                          })
                        }
                      >
                        Narrate
                      </button>
                    )}
                  </li>
                ))}
                {log.length === 0 && <li className="muted">Nothing logged yet.</li>}
              </ul>
              <div className="row">
                <label>
                  Note
                  <input value={noteText} onChange={(e) => setNoteText(e.target.value)} />
                </label>
                <button
                  onClick={() =>
                    void run(async () => {
                      await api().logAddNote(campaign.id, noteText, sessionId || null);
                      setNoteText('');
                      await refreshAll();
                    })
                  }
                >
                  Add note
                </button>
              </div>
            </section>

            <section className="panel" aria-label="Memory">
              <h2>Memory — NPCs, locations, facts</h2>
              <div className="row">
                <label>
                  Search memory
                  <input value={memoryQuery} onChange={(e) => setMemoryQuery(e.target.value)} />
                </label>
                <button
                  onClick={() =>
                    void run(async () => {
                      setMemory(await api().memorySearch(campaign.id, memoryQuery));
                    })
                  }
                >
                  Search
                </button>
                <button
                  onClick={() =>
                    void run(async () => {
                      setMemory(await api().memoryList(campaign.id));
                    })
                  }
                >
                  Show all
                </button>
              </div>
              <ul className="list">
                {memory.map((m) => (
                  <li key={m.id}>
                    <strong>{m.title}</strong> <span className="muted">({m.kind}, {m.source})</span>
                    {m.body && <div>{m.body}</div>}
                    {m.tags.length > 0 && <div className="muted">tags: {m.tags.join(', ')}</div>}
                    <button
                      className="small"
                      onClick={() =>
                        void run(async () => {
                          await api().memoryDelete(m.id);
                          await refreshAll();
                        })
                      }
                    >
                      Delete
                    </button>
                  </li>
                ))}
                {memory.length === 0 && <li className="muted">No memory entries.</li>}
              </ul>
              <div className="row">
                <label>
                  Kind
                  <select value={memKind} onChange={(e) => setMemKind(e.target.value as MemoryKind)}>
                    <option value="npc">NPC</option>
                    <option value="location">Location</option>
                    <option value="fact">Fact</option>
                  </select>
                </label>
                <label>
                  Title
                  <input value={memTitle} onChange={(e) => setMemTitle(e.target.value)} />
                </label>
                <label>
                  Body
                  <input value={memBody} onChange={(e) => setMemBody(e.target.value)} />
                </label>
                <label>
                  Tags (comma separated)
                  <input value={memTags} onChange={(e) => setMemTags(e.target.value)} />
                </label>
                <button
                  onClick={() =>
                    void run(async () => {
                      await api().memoryCreate(campaign.id, {
                        kind: memKind,
                        title: memTitle,
                        body: memBody,
                        tags: memTags
                          .split(',')
                          .map((t) => t.trim())
                          .filter((t) => t.length > 0),
                      });
                      setMemTitle('');
                      setMemBody('');
                      setMemTags('');
                      await refreshAll();
                    })
                  }
                >
                  Add memory
                </button>
              </div>
            </section>

            <section className="panel" aria-label="Narration settings">
              <h2>Narration</h2>
              <p className="muted">
                Flavor only. The mock narrator works fully offline; the local option posts to a
                loopback endpoint you configure (e.g. Ollama). Narration can never change a roll,
                HP, or any other rules state.
              </p>
              <div className="row">
                <label>
                  Narrator
                  <select
                    value={settings.narrator}
                    onChange={(e) =>
                      setSettings((prev) => ({
                        ...prev,
                        narrator: e.target.value as 'mock' | 'local',
                      }))
                    }
                  >
                    <option value="mock">Mock (offline)</option>
                    <option value="local">Local endpoint</option>
                  </select>
                </label>
                <label>
                  Endpoint (loopback only)
                  <input
                    value={settings.endpoint}
                    onChange={(e) => setSettings((prev) => ({ ...prev, endpoint: e.target.value }))}
                  />
                </label>
                <label>
                  Model
                  <input
                    value={settings.model}
                    onChange={(e) => setSettings((prev) => ({ ...prev, model: e.target.value }))}
                  />
                </label>
                <button
                  onClick={() =>
                    void run(async () => {
                      setSettings(await api().settingsUpdate(settings));
                      setNotice('Narration settings saved.');
                    })
                  }
                >
                  Save narration settings
                </button>
              </div>
            </section>

            <section className="panel" aria-label="Campaign data">
              <h2>Campaign data</h2>
              <div className="row">
                <button
                  onClick={() =>
                    void run(async () => {
                      const text = await api().exportCampaign(campaign.id);
                      setExportText(text);
                      downloadText(`${campaign.name.replace(/\W+/g, '-').toLowerCase()}-campaign.json`, text);
                    })
                  }
                >
                  Export campaign
                </button>
              </div>
              {exportText && (
                <textarea readOnly value={exportText} rows={6} aria-label="Exported campaign JSON" />
              )}
              <label>
                Import campaign bundle (ai-dungeon-master/campaign v1)
                <textarea value={importText} onChange={(e) => setImportText(e.target.value)} rows={4} />
              </label>
              <button
                onClick={() =>
                  void run(async () => {
                    const imported = await api().importCampaign(importText);
                    setImportText('');
                    await refreshCampaigns();
                    setCampaignId(imported.id);
                    setNotice(`Imported campaign “${imported.name}”.`);
                  })
                }
              >
                Import campaign
              </button>
              <label>
                Import Worldbuilding Manager backup (creates memory entries)
                <textarea value={wbText} onChange={(e) => setWbText(e.target.value)} rows={4} />
              </label>
              <button
                onClick={() =>
                  void run(async () => {
                    const summary = await api().importWorldbuilding(campaign.id, wbText);
                    setWbText('');
                    await refreshAll();
                    setNotice(summary.detail);
                  })
                }
              >
                Import worldbuilding backup
              </button>
              <label>
                Import dungeon map manifest (creates a location memory entry)
                <textarea value={dungeonText} onChange={(e) => setDungeonText(e.target.value)} rows={4} />
              </label>
              <button
                onClick={() =>
                  void run(async () => {
                    const summary = await api().importDungeonManifest(campaign.id, dungeonText);
                    setDungeonText('');
                    await refreshAll();
                    setNotice(summary.detail);
                  })
                }
              >
                Import dungeon manifest
              </button>
            </section>
          </>
        )}
      </main>
    </div>
  );
}
