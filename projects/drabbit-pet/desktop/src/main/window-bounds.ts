/**
 * Window bounds guard: the pet window must always be exactly its
 * pet size and fully inside the primary display's work area. Pure
 * math — the main process feeds it Electron's live rects.
 *
 * Why this exists (2026-11-05): the pet was lost for real — its
 * window ended up ~10,000 px wide and effectively off-screen after
 * being hidden during some display change. Roaming only ever set
 * the position of the window's left edge and never checked the
 * size, so nothing ever pulled it back. This function is the
 * correction the main process now applies on a watchdog cadence.
 */

export interface Rect {
  x: number;
  y: number;
  width: number;
  height: number;
}

/**
 * Force `rect` to exactly `size` × `size`, fully inside
 * `workArea`. Returns the corrected rect, or null when the rect is
 * already exactly right (the caller then does nothing).
 */
export function constrainRectToWorkArea(
  rect: Rect,
  workArea: Rect,
  size: number,
): Rect | null {
  const maxX = workArea.x + Math.max(0, workArea.width - size);
  const maxY = workArea.y + Math.max(0, workArea.height - size);
  const fixed: Rect = {
    x: Math.min(Math.max(rect.x, workArea.x), maxX),
    y: Math.min(Math.max(rect.y, workArea.y), maxY),
    width: size,
    height: size,
  };
  if (
    fixed.x === rect.x &&
    fixed.y === rect.y &&
    fixed.width === rect.width &&
    fixed.height === rect.height
  ) {
    return null;
  }
  return fixed;
}
