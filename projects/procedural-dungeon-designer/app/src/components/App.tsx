import { useCallback, useEffect, useState } from 'react';
import type { ChangeEvent } from 'react';
import type {
  DungeonMap,
  DungeonSummary,
  GenParams,
  PlacementKind,
  Room,
  SavedDungeon,
  ThemeId,
  ThemeInfo,
  ValidationResult,
} from '../../shared/types';
import { api, formatError } from '../lib/pdd';

const PLACEMENT_KINDS: PlacementKind[] = [
  'encounter',
  'trap',
  'hazard',
  'treasure',
];

function slugify(name: string): string {
  const slug = name
    .toLowerCase()
    .replace(/[^\w-]+/g, '-')
    .replace(/^-+|-+$/g, '');
  return slug.length > 0 ? slug : 'dungeon';
}

function downloadText(filename: string, text: string, mime: string): void {
  const blob = new Blob([text], { type: mime });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

function capitalise(text: string): string {
  return text.length > 0 ? text[0]!.toUpperCase() + text.slice(1) : text;
}

export function App() {
  const [error, setError] = useState<string | null>(null);

  // Themes + generator form
  const [themes, setThemes] = useState<ThemeInfo[]>([]);
  const [seed, setSeed] = useState('first delve');
  const [gridWidth, setGridWidth] = useState(28);
  const [gridHeight, setGridHeight] = useState(20);
  const [roomCount, setRoomCount] = useState(9);
  const [difficulty, setDifficulty] = useState(2);
  const [themeId, setThemeId] = useState<ThemeId>('sunken-crypt');

  // Current dungeon (saved or unsaved)
  const [currentMap, setCurrentMap] = useState<DungeonMap | null>(null);
  const [savedId, setSavedId] = useState<string | null>(null);
  const [savedName, setSavedName] = useState<string | null>(null);
  const [saveName, setSaveName] = useState('first delve dungeon');
  const [selectedRoomId, setSelectedRoomId] = useState<string | null>(null);
  const [validation, setValidation] = useState<ValidationResult | null>(null);
  const [printView, setPrintView] = useState(false);

  // Saved list
  const [savedList, setSavedList] = useState<DungeonSummary[]>([]);

  // Placement editor
  const [placementKind, setPlacementKind] =
    useState<PlacementKind>('encounter');
  const [placementKey, setPlacementKey] = useState('');
  const [moveTargets, setMoveTargets] = useState<Record<string, string>>({});

  const reportError = useCallback((err: unknown) => {
    setError(formatError(err));
  }, []);

  const refreshSavedList = useCallback(async () => {
    try {
      setSavedList(await api().dungeonsList());
    } catch (err) {
      reportError(err);
    }
  }, [reportError]);

  // Initial load: themes + saved dungeons.
  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const list = await api().themesList();
        if (!cancelled) {
          setThemes(list);
          if (list.length > 0) {
            setThemeId((prev) =>
              list.some((t) => t.id === prev) ? prev : list[0]!.id,
            );
          }
        }
      } catch (err) {
        if (!cancelled) reportError(err);
      }
      if (!cancelled) await refreshSavedList();
    })();
    return () => {
      cancelled = true;
    };
  }, [refreshSavedList, reportError]);

  // Validation readout follows the current map (generate / load / edits).
  useEffect(() => {
    if (!currentMap) {
      setValidation(null);
      return;
    }
    let cancelled = false;
    void (async () => {
      try {
        const result = await api().validateMap(currentMap);
        if (!cancelled) setValidation(result);
      } catch (err) {
        if (!cancelled) reportError(err);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [currentMap, reportError]);

  const genTheme = themes.find((t) => t.id === themeId) ?? null;
  const mapTheme =
    themes.find((t) => t.id === currentMap?.params.theme) ?? genTheme;
  const isSaved = savedId !== null;

  const selectedRoom: Room | null =
    currentMap?.rooms.find((r) => r.id === selectedRoomId) ??
    currentMap?.rooms[0] ??
    null;

  // Keep the placement entry selection valid for the current kind/theme.
  useEffect(() => {
    if (!mapTheme) return;
    const entries = mapTheme.tables[placementKind];
    if (!entries.some((e) => e.key === placementKey)) {
      setPlacementKey(entries[0]?.key ?? '');
    }
  }, [mapTheme, placementKind, placementKey]);

  const applySaved = useCallback((saved: SavedDungeon) => {
    setCurrentMap(saved.map);
    setSavedId(saved.id);
    setSavedName(saved.name);
    setSaveName(saved.name);
    setSelectedRoomId((prev) => {
      if (prev && saved.map.rooms.some((r) => r.id === prev)) return prev;
      const entrance =
        saved.map.rooms.find((r) => r.isEntrance) ?? saved.map.rooms[0];
      return entrance?.id ?? null;
    });
  }, []);

  const onGenerate = async () => {
    const params: GenParams = {
      seed,
      gridWidth,
      gridHeight,
      roomCount,
      theme: themeId,
      difficulty,
    };
    try {
      const map = await api().generate(params);
      setCurrentMap(map);
      setSavedId(null);
      setSavedName(null);
      setSaveName(`${params.seed} dungeon`);
      const entrance = map.rooms.find((r) => r.isEntrance) ?? map.rooms[0];
      setSelectedRoomId(entrance?.id ?? null);
      setError(null);
    } catch (err) {
      reportError(err);
    }
  };

  const onSave = async () => {
    if (!currentMap) return;
    const name = saveName.trim();
    if (!name) {
      setError('Please enter a name for the dungeon before saving.');
      return;
    }
    try {
      const saved = await api().dungeonsSave({ name, map: currentMap });
      applySaved(saved);
      setError(null);
      await refreshSavedList();
    } catch (err) {
      reportError(err);
    }
  };

  const onLoad = async (id: string) => {
    try {
      const saved = await api().dungeonsGet(id);
      applySaved(saved);
      setError(null);
    } catch (err) {
      reportError(err);
    }
  };

  const onDelete = async (id: string) => {
    try {
      await api().dungeonsDelete(id);
      if (savedId === id) {
        setCurrentMap(null);
        setSavedId(null);
        setSavedName(null);
        setSelectedRoomId(null);
      }
      setError(null);
      await refreshSavedList();
    } catch (err) {
      reportError(err);
    }
  };

  const onAddPlacement = async () => {
    if (!savedId || !selectedRoom || !placementKey) return;
    try {
      const saved = await api().placementsAdd(savedId, {
        roomId: selectedRoom.id,
        kind: placementKind,
        key: placementKey,
      });
      applySaved(saved);
      setError(null);
    } catch (err) {
      reportError(err);
    }
  };

  const onRemovePlacement = async (placementId: string) => {
    if (!savedId) return;
    try {
      const saved = await api().placementsRemove(savedId, placementId);
      applySaved(saved);
      setError(null);
    } catch (err) {
      reportError(err);
    }
  };

  const onMovePlacement = async (placementId: string) => {
    if (!savedId || !currentMap) return;
    const fallback = currentMap.rooms.find(
      (r) => r.id !== selectedRoom?.id,
    )?.id;
    const toRoomId = moveTargets[placementId] ?? fallback;
    if (!toRoomId) return;
    try {
      const saved = await api().placementsMove(savedId, placementId, toRoomId);
      applySaved(saved);
      setError(null);
    } catch (err) {
      reportError(err);
    }
  };

  const onExportJson = async () => {
    if (!savedId) return;
    try {
      const text = await api().exportJson(savedId);
      downloadText(
        `${slugify(savedName ?? saveName)}.json`,
        text,
        'application/json',
      );
      setError(null);
    } catch (err) {
      reportError(err);
    }
  };

  const onExportMarkdown = async () => {
    if (!savedId) return;
    try {
      const text = await api().exportMarkdown(savedId);
      downloadText(
        `${slugify(savedName ?? saveName)}.md`,
        text,
        'text/markdown',
      );
      setError(null);
    } catch (err) {
      reportError(err);
    }
  };

  const onImportFile = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = '';
    if (!file) return;
    try {
      const text = await file.text();
      const saved = await api().importJson(text);
      applySaved(saved);
      setError(null);
      await refreshSavedList();
    } catch (err) {
      reportError(err);
    }
  };

  const palette = mapTheme?.palette ?? null;
  const entranceRoom = currentMap?.rooms.find((r) => r.isEntrance) ?? null;
  const budgetUsed = currentMap?.budgetUsed ?? 0;
  const budgetLimit = currentMap?.budgetLimit ?? 0;
  const overBudget = currentMap !== null && budgetUsed > budgetLimit;
  const budgetPercent =
    budgetLimit > 0
      ? Math.min(100, Math.round((budgetUsed / budgetLimit) * 100))
      : 0;
  const otherRooms = currentMap
    ? currentMap.rooms.filter((r) => r.id !== selectedRoom?.id)
    : [];

  return (
    <div className={printView ? 'app print-view' : 'app'}>
      <header className="app-header">
        <h1>Procedural Dungeon Designer</h1>
        <p className="subtitle">
          Generate seeded, connected dungeon maps, tune encounter budgets,
          and export deterministic layouts.
        </p>
      </header>

      {error && (
        <div role="alert" className="error-banner">
          {error}
        </div>
      )}

      <main className="app-main">
        <section
          aria-labelledby="generator-heading"
          className="panel no-print"
        >
          <h2 id="generator-heading">Generator</h2>
          <div className="form-grid">
            <div>
              <label htmlFor="seed-input">Seed</label>
              <input
                id="seed-input"
                type="text"
                value={seed}
                onChange={(e) => setSeed(e.target.value)}
              />
            </div>
            <div>
              <label htmlFor="grid-width-input">Grid width</label>
              <input
                id="grid-width-input"
                type="number"
                min={12}
                max={60}
                value={gridWidth}
                onChange={(e) => setGridWidth(Number(e.target.value))}
              />
            </div>
            <div>
              <label htmlFor="grid-height-input">Grid height</label>
              <input
                id="grid-height-input"
                type="number"
                min={12}
                max={48}
                value={gridHeight}
                onChange={(e) => setGridHeight(Number(e.target.value))}
              />
            </div>
            <div>
              <label htmlFor="room-count-input">Room count</label>
              <input
                id="room-count-input"
                type="number"
                min={3}
                max={40}
                value={roomCount}
                onChange={(e) => setRoomCount(Number(e.target.value))}
              />
            </div>
            <div>
              <label htmlFor="difficulty-input">Difficulty</label>
              <input
                id="difficulty-input"
                type="number"
                min={1}
                max={5}
                step={1}
                value={difficulty}
                onChange={(e) => setDifficulty(Number(e.target.value))}
              />
            </div>
            <div>
              <label htmlFor="theme-select">Theme</label>
              <select
                id="theme-select"
                value={themeId}
                onChange={(e) => setThemeId(e.target.value as ThemeId)}
              >
                {themes.map((theme) => (
                  <option key={theme.id} value={theme.id}>
                    {theme.name}
                  </option>
                ))}
              </select>
            </div>
          </div>
          {genTheme && <p className="theme-tagline">{genTheme.tagline}</p>}
          <div className="button-row">
            <button
              type="button"
              className="primary"
              onClick={() => void onGenerate()}
            >
              Generate dungeon
            </button>
            <button
              type="button"
              aria-pressed={printView}
              onClick={() => setPrintView((prev) => !prev)}
            >
              Print view
            </button>
          </div>
          <p className="note">
            Print view shows a black-on-white map and hides the editor
            panels; browser print works from either view.
          </p>
        </section>

        <div className="workspace">
          <section aria-labelledby="map-heading" className="panel map-panel">
            <h2 id="map-heading">Dungeon map</h2>
            {!currentMap || !palette ? (
              <p className="empty-state">
                No dungeon yet. Configure the generator above and choose
                Generate dungeon to create your first delve.
              </p>
            ) : (
              <>
                <div className="budget-block" data-testid="budget-meter">
                  <p className="budget-text">
                    Budget: {budgetUsed} / {budgetLimit}
                    {overBudget && (
                      <span className="over-budget"> Over budget</span>
                    )}
                  </p>
                  <div
                    className="budget-bar"
                    role="progressbar"
                    aria-label="Budget"
                    aria-valuemin={0}
                    aria-valuemax={budgetLimit}
                    aria-valuenow={budgetUsed}
                  >
                    <div
                      className={
                        overBudget
                          ? 'budget-bar-fill over'
                          : 'budget-bar-fill'
                      }
                      style={{ width: `${budgetPercent}%` }}
                    />
                  </div>
                  {validation && (
                    <p className="validation-text" data-testid="validation">
                      {validation.connected
                        ? `Connected: all ${validation.roomCount} rooms reachable`
                        : `Not connected: unreachable rooms: ${
                            validation.unreachableRoomIds.join(', ') ||
                            'none'
                          }`}
                    </p>
                  )}
                </div>

                <svg
                  className="dungeon-map"
                  data-testid="dungeon-map"
                  role="img"
                  aria-label={`Dungeon map with ${currentMap.rooms.length} rooms, seed ${currentMap.params.seed}, theme ${currentMap.params.theme}`}
                  viewBox={`0 0 ${currentMap.gridWidth} ${currentMap.gridHeight}`}
                >
                  {currentMap.tiles.map((row, y) =>
                    row.split('').map((tile, x) => {
                      const inEntrance =
                        entranceRoom !== null &&
                        x >= entranceRoom.x &&
                        x < entranceRoom.x + entranceRoom.w &&
                        y >= entranceRoom.y &&
                        y < entranceRoom.y + entranceRoom.h;
                      let fill = palette.wall;
                      let tileClass = 'tile tile-wall';
                      if (tile === '.') {
                        fill = inEntrance ? palette.entrance : palette.floor;
                        tileClass = inEntrance
                          ? 'tile tile-entrance'
                          : 'tile tile-floor';
                      } else if (tile === '+') {
                        fill = palette.corridor;
                        tileClass = 'tile tile-corridor';
                      }
                      return (
                        <rect
                          key={`${x}-${y}`}
                          className={tileClass}
                          x={x}
                          y={y}
                          width={1}
                          height={1}
                          fill={fill}
                        />
                      );
                    }),
                  )}
                  {selectedRoom && (
                    <rect
                      className="room-selected"
                      x={selectedRoom.x}
                      y={selectedRoom.y}
                      width={selectedRoom.w}
                      height={selectedRoom.h}
                      fill="none"
                      stroke={palette.accent}
                    />
                  )}
                  {currentMap.rooms.map((room) => (
                    <rect
                      key={room.id}
                      className="room-hit"
                      data-testid={`room-${room.id}`}
                      aria-label={room.name}
                      x={room.x}
                      y={room.y}
                      width={room.w}
                      height={room.h}
                      onClick={() => setSelectedRoomId(room.id)}
                    />
                  ))}
                </svg>
                <p className="muted">
                  Click a room on the map to inspect it. Walls, floors and
                  corridors use the {mapTheme?.name ?? ''} palette; the
                  entrance room is tinted.
                </p>
              </>
            )}
          </section>

          <div className="side-column">
            <section
              aria-labelledby="inspector-heading"
              className="panel no-print"
              data-testid="inspector"
            >
              <h2 id="inspector-heading">Inspector</h2>
              {!selectedRoom ? (
                <p>Select a room on the map to inspect it.</p>
              ) : (
                <div>
                  <h3>{selectedRoom.name}</h3>
                  <p>
                    ID: {selectedRoom.id}
                    {selectedRoom.isEntrance && (
                      <span className="badge entrance-badge"> Entrance</span>
                    )}
                  </p>
                  <p>
                    Size: {selectedRoom.w} × {selectedRoom.h} · Center: (
                    {selectedRoom.cx}, {selectedRoom.cy}) · Position: (
                    {selectedRoom.x}, {selectedRoom.y})
                  </p>
                  <h4>Placements</h4>
                  {selectedRoom.placements.length === 0 ? (
                    <p>No placements in this room.</p>
                  ) : (
                    <ul className="placement-list">
                      {selectedRoom.placements.map((placement) => (
                        <li key={placement.id} className="placement-row">
                          <span>
                            {placement.kind}: {placement.name} (cost{' '}
                            {placement.cost})
                          </span>
                          <span className="placement-controls">
                            <label
                              className="visually-hidden"
                              htmlFor={`move-select-${placement.id}`}
                            >
                              Move {placement.name} to room
                            </label>
                            <select
                              id={`move-select-${placement.id}`}
                              aria-label={`Move ${placement.name} to room`}
                              value={
                                moveTargets[placement.id] ??
                                otherRooms[0]?.id ??
                                ''
                              }
                              disabled={!isSaved || otherRooms.length === 0}
                              onChange={(e) =>
                                setMoveTargets((prev) => ({
                                  ...prev,
                                  [placement.id]: e.target.value,
                                }))
                              }
                            >
                              {otherRooms.map((room) => (
                                <option key={room.id} value={room.id}>
                                  {room.name}
                                </option>
                              ))}
                            </select>
                            <button
                              type="button"
                              aria-label={`Move ${placement.name}`}
                              disabled={!isSaved || otherRooms.length === 0}
                              onClick={() =>
                                void onMovePlacement(placement.id)
                              }
                            >
                              Move
                            </button>
                            <button
                              type="button"
                              aria-label={`Remove ${placement.name}`}
                              disabled={!isSaved}
                              onClick={() =>
                                void onRemovePlacement(placement.id)
                              }
                            >
                              Remove
                            </button>
                          </span>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              )}
            </section>

            <section
              aria-labelledby="placement-editor-heading"
              className="panel no-print"
              data-testid="placement-editor"
            >
              <h2 id="placement-editor-heading">Placement editor</h2>
              {!currentMap ? (
                <p>Generate a dungeon before editing placements.</p>
              ) : (
                <>
                  {!isSaved && (
                    <p className="notice">
                      Save the dungeon to edit placements
                    </p>
                  )}
                  {isSaved && savedName && (
                    <p className="note">
                      Editing saved dungeon “{savedName}”.
                    </p>
                  )}
                  <label htmlFor="placement-kind-select">
                    Placement kind
                  </label>
                  <select
                    id="placement-kind-select"
                    value={placementKind}
                    disabled={!isSaved}
                    onChange={(e) =>
                      setPlacementKind(e.target.value as PlacementKind)
                    }
                  >
                    {PLACEMENT_KINDS.map((kind) => (
                      <option key={kind} value={kind}>
                        {capitalise(kind)}
                      </option>
                    ))}
                  </select>
                  <label htmlFor="placement-entry-select">
                    Placement entry
                  </label>
                  <select
                    id="placement-entry-select"
                    value={placementKey}
                    disabled={!isSaved || !mapTheme}
                    onChange={(e) => setPlacementKey(e.target.value)}
                  >
                    {(mapTheme?.tables[placementKind] ?? []).map((entry) => (
                      <option key={entry.key} value={entry.key}>
                        {entry.name} (cost {entry.cost})
                      </option>
                    ))}
                  </select>
                  <div className="button-row">
                    <button
                      type="button"
                      className="primary"
                      disabled={!isSaved || !selectedRoom || !placementKey}
                      onClick={() => void onAddPlacement()}
                    >
                      Add placement
                    </button>
                  </div>
                  {selectedRoom && (
                    <p className="muted">
                      Adding to: {selectedRoom.name} ({selectedRoom.id})
                    </p>
                  )}
                </>
              )}
            </section>
          </div>
        </div>

        <section aria-labelledby="save-heading" className="panel no-print">
          <h2 id="save-heading">Save dungeon</h2>
          <label htmlFor="dungeon-name-input">Dungeon name</label>
          <input
            id="dungeon-name-input"
            type="text"
            value={saveName}
            onChange={(e) => setSaveName(e.target.value)}
          />
          <div className="button-row">
            <button
              type="button"
              className="primary"
              disabled={!currentMap}
              onClick={() => void onSave()}
            >
              Save dungeon
            </button>
          </div>
          {isSaved && savedName && (
            <p className="note">
              Saved as “{savedName}” — placement editing is enabled.
            </p>
          )}
        </section>

        <section
          aria-labelledby="saved-heading"
          className="panel no-print"
          data-testid="saved-dungeons"
        >
          <h2 id="saved-heading">Saved dungeons</h2>
          {savedList.length === 0 ? (
            <p>No saved dungeons yet.</p>
          ) : (
            <ul className="saved-list">
              {savedList.map((summary) => (
                <li key={summary.id} className="saved-row">
                  <span className="saved-summary">
                    <strong>{summary.name}</strong> — seed: {summary.seed} ·
                    theme: {summary.theme} · rooms: {summary.roomCount} ·
                    budget: {summary.budgetUsed} / {summary.budgetLimit}
                  </span>
                  <span className="button-row inline">
                    <button
                      type="button"
                      onClick={() => void onLoad(summary.id)}
                    >
                      Load
                    </button>
                    <button
                      type="button"
                      className="danger"
                      onClick={() => void onDelete(summary.id)}
                    >
                      Delete
                    </button>
                  </span>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section aria-labelledby="export-heading" className="panel no-print">
          <h2 id="export-heading">Export and import</h2>
          <p className="muted">
            Export works on the current saved dungeon. Importing a JSON
            export makes it the current dungeon.
          </p>
          <div className="button-row">
            <button
              type="button"
              disabled={!isSaved}
              onClick={() => void onExportJson()}
            >
              Export JSON
            </button>
            <button
              type="button"
              disabled={!isSaved}
              onClick={() => void onExportMarkdown()}
            >
              Export Markdown
            </button>
          </div>
          <label htmlFor="import-file-input">Import JSON</label>
          <input
            id="import-file-input"
            type="file"
            accept=".json,application/json"
            onChange={(e) => void onImportFile(e)}
          />
        </section>
      </main>
    </div>
  );
}
