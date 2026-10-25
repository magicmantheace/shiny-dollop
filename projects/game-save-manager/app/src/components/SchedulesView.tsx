import { useState } from 'react';
import type { Game, Schedule } from '../../shared/types';
import { useStore } from '../store';
import { IpcError } from '../api';
import { errorSummary } from '../errorMessages';
import { formatDateTime, timeAgo } from '../format';
import SourceBadge from './SourceBadge';

const MIN_MINUTES = 5;
const MAX_MINUTES = 43200;
const PRESETS = [60, 360, 720, 1440];

interface ScheduleRowProps {
  game: Game;
  schedule: Schedule | null;
}

/**
 * Per-game schedule row: enable/disable toggle, interval in minutes, last-run
 * display. Saving calls schedules.set (upsert); removing calls schedules.delete.
 */
function ScheduleRow({ game, schedule }: ScheduleRowProps): React.ReactNode {
  const { setSchedule, deleteSchedule, pushToast } = useStore();
  const [enabled, setEnabled] = useState(schedule?.enabled ?? false);
  const [minutes, setMinutes] = useState(String(schedule?.intervalMinutes ?? 1440));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const parsed = Number(minutes);
  const valid = Number.isInteger(parsed) && parsed >= MIN_MINUTES && parsed <= MAX_MINUTES;

  const save = async (): Promise<void> => {
    if (!valid) {
      setError(`Interval must be a whole number of minutes between ${MIN_MINUTES} and ${MAX_MINUTES}.`);
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await setSchedule(game.id, parsed, enabled);
      pushToast(
        'success',
        'Schedule saved',
        enabled
          ? `"${game.name}" will back up every ${parsed} minute${parsed === 1 ? '' : 's'}.`
          : `Automatic backups for "${game.name}" are turned off.`,
      );
    } catch (err) {
      setError(
        err instanceof IpcError ? errorSummary(err.code, err.message) : 'Could not save the schedule.',
      );
    } finally {
      setSaving(false);
    }
  };

  const remove = async (): Promise<void> => {
    if (!schedule) {
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await deleteSchedule(game.id);
      pushToast('success', 'Schedule removed', `Automatic backups for "${game.name}" are turned off.`);
    } catch (err) {
      setError(
        err instanceof IpcError ? errorSummary(err.code, err.message) : 'Could not remove the schedule.',
      );
    } finally {
      setSaving(false);
    }
  };

  return (
    <li className="gsm-schedule-row">
      <div className="gsm-schedule-main">
        <div className="gsm-schedule-title">
          <strong>{game.name}</strong>
          <SourceBadge source={game.source} />
        </div>
        <div className="gsm-schedule-controls">
          <label className="gsm-check">
            <input
              type="checkbox"
              checked={enabled}
              onChange={(e) => setEnabled(e.target.checked)}
              aria-label={`Enable automatic backups for ${game.name}`}
            />
            <span>Automatic backups</span>
          </label>
          <label className="gsm-interval">
            <span>Every</span>
            <input
              type="number"
              min={MIN_MINUTES}
              max={MAX_MINUTES}
              value={minutes}
              onChange={(e) => setMinutes(e.target.value)}
              aria-label={`Backup interval in minutes for ${game.name}`}
            />
            <span>minutes</span>
          </label>
          <div className="gsm-presets" role="group" aria-label="Interval presets">
            {PRESETS.map((p) => (
              <button
                key={p}
                type="button"
                className="gsm-btn gsm-btn-small"
                onClick={() => setMinutes(String(p))}
                aria-label={`Set interval to ${p} minutes for ${game.name}`}
              >
                {p >= 1440 ? `${p / 1440}d` : p >= 60 ? `${p / 60}h` : `${p}m`}
              </button>
            ))}
          </div>
        </div>
        <p className="gsm-muted">
          Last run: {schedule?.lastRunAt ? `${timeAgo(schedule.lastRunAt)} (${formatDateTime(schedule.lastRunAt)})` : 'never'}
        </p>
        {error && (
          <div className="gsm-error" role="alert">
            {error}
          </div>
        )}
      </div>
      <div className="gsm-schedule-actions">
        <button
          type="button"
          className="gsm-btn gsm-btn-primary"
          onClick={() => void save()}
          disabled={saving || !valid}
        >
          {saving ? 'Saving…' : 'Save'}
        </button>
        {schedule && (
          <button type="button" className="gsm-btn" onClick={() => void remove()} disabled={saving}>
            Delete
          </button>
        )}
      </div>
    </li>
  );
}

/** Schedules view: one schedule row per tracked game. */
export default function SchedulesView(): React.ReactNode {
  const { games, gamesLoading, gamesError, schedules, schedulesLoading, schedulesError, refreshSchedules } =
    useStore();

  const loading = gamesLoading || schedulesLoading;
  const error = gamesError ?? schedulesError;

  if (loading) {
    return (
      <section className="gsm-view" aria-busy="true" aria-label="Backup schedules">
        <p className="gsm-muted">Loading schedules…</p>
      </section>
    );
  }

  if (error) {
    return (
      <section className="gsm-view" aria-label="Backup schedules">
        <div className="gsm-error" role="alert">
          <strong>Couldn&apos;t load schedules.</strong>
          <p>{error}</p>
          <button type="button" className="gsm-btn" onClick={() => void refreshSchedules()}>
            Retry
          </button>
        </div>
      </section>
    );
  }

  if (games.length === 0) {
    return (
      <section className="gsm-view gsm-empty" aria-label="Backup schedules">
        <h2>No schedules yet</h2>
        <p className="gsm-muted">Add a game to the library first, then set up automatic backups here.</p>
      </section>
    );
  }

  const byGame = new Map<number, Schedule>(schedules.map((s) => [s.gameId, s]));

  return (
    <section className="gsm-view" aria-label="Backup schedules">
      <div className="gsm-view-header">
        <h2>Backup schedules</h2>
      </div>
      <p className="gsm-muted">
        Schedules run while the app is open. Timers don&apos;t survive an app restart, but your
        settings do.
      </p>
      <ul className="gsm-schedule-list">
        {games.map((game) => (
          <ScheduleRow key={game.id} game={game} schedule={byGame.get(game.id) ?? null} />
        ))}
      </ul>
    </section>
  );
}
