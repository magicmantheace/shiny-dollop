import { useState } from 'react';
import { getGmm } from '../gmm';

interface Props {
  onUndone: () => void;
}

/** Reverts the most recent metadata edit via changes:undo. */
export function UndoButton({ onUndone }: Props) {
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const undo = async () => {
    setBusy(true);
    setMsg(null);
    setError(null);
    try {
      const { reverted, gameId } = await getGmm().changes.undo();
      if (reverted) {
        setMsg(gameId ? `Reverted the last change (game ${gameId}).` : 'Reverted the last change.');
        onUndone();
      } else {
        setMsg('Nothing to undo.');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <span className="undo">
      <button className="btn" onClick={undo} disabled={busy}>
        {busy ? 'Undoing…' : 'Undo last change'}
      </button>
      {msg && (
        <span className="notice small" role="status">
          {msg}
        </span>
      )}
      {error && (
        <span className="error small" role="alert">
          {error}
        </span>
      )}
    </span>
  );
}
