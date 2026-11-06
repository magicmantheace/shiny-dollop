import { describe, expect, it } from 'vitest';
import { constrainRectToWorkArea, type Rect } from '../src/main/window-bounds.js';

// A 1536x864 screen with a 48px taskbar: DIP coords, like the
// owner's PC reports (3840x2160 at 250%).
const WA: Rect = { x: 0, y: 0, width: 1536, height: 816 };
const SIZE = 220;

describe('constrainRectToWorkArea', () => {
  it('leaves a fully on-screen, right-sized window alone', () => {
    expect(constrainRectToWorkArea({ x: 1316, y: 596, width: SIZE, height: SIZE }, WA, SIZE)).toBeNull();
    expect(constrainRectToWorkArea({ x: 0, y: 0, width: SIZE, height: SIZE }, WA, SIZE)).toBeNull();
  });

  it('pulls a window back from off the right and bottom edges', () => {
    expect(constrainRectToWorkArea({ x: 5000, y: 300, width: SIZE, height: SIZE }, WA, SIZE)).toEqual({
      x: 1316,
      y: 300,
      width: SIZE,
      height: SIZE,
    });
    expect(constrainRectToWorkArea({ x: 100, y: 5000, width: SIZE, height: SIZE }, WA, SIZE)).toEqual({
      x: 100,
      y: 596,
      width: SIZE,
      height: SIZE,
    });
  });

  it('pulls a window back from negative coordinates', () => {
    expect(constrainRectToWorkArea({ x: -400, y: -50, width: SIZE, height: SIZE }, WA, SIZE)).toEqual({
      x: 0,
      y: 0,
      width: SIZE,
      height: SIZE,
    });
  });

  it('repairs the 2026-11-05 corruption: a ~10,000px-wide window', () => {
    // The real incident, in DIP: left edge legal, width absurd —
    // the pet was effectively gone.
    const fixed = constrainRectToWorkArea({ x: 585, y: 596, width: 4043, height: SIZE }, WA, SIZE);
    expect(fixed).toEqual({ x: 585, y: 596, width: SIZE, height: SIZE });
  });

  it('forces an undersized window back to pet size too', () => {
    expect(constrainRectToWorkArea({ x: 10, y: 10, width: 90, height: 90 }, WA, SIZE)).toEqual({
      x: 10,
      y: 10,
      width: SIZE,
      height: SIZE,
    });
  });

  it('respects a work area with an offset origin (taskbar/dock)', () => {
    const wa: Rect = { x: 64, y: 32, width: 1200, height: 800 };
    expect(constrainRectToWorkArea({ x: 0, y: 0, width: SIZE, height: SIZE }, wa, SIZE)).toEqual({
      x: 64,
      y: 32,
      width: SIZE,
      height: SIZE,
    });
    expect(constrainRectToWorkArea({ x: 1104, y: 612, width: SIZE, height: SIZE }, wa, SIZE)).toBeNull();
  });

  it('pins to the work-area origin when the area is smaller than the pet', () => {
    const tiny: Rect = { x: 5, y: 7, width: 100, height: 100 };
    expect(constrainRectToWorkArea({ x: 900, y: 900, width: SIZE, height: SIZE }, tiny, SIZE)).toEqual({
      x: 5,
      y: 7,
      width: SIZE,
      height: SIZE,
    });
  });
});
