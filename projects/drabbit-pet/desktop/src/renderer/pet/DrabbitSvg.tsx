import type { FurVariant } from 'drabbit-core';
import type { PetSummary } from '../../shared/api-types.js';
import type { PetAnimState } from './visual-state.js';

/**
 * The v1 drabbit: a hand-drawn inline SVG (furry body, floppy-tipped
 * ears, dragon horns, cloth wings, long curled tail). This is a
 * deliberate placeholder-for-now — the shapes live in this one
 * component so sprite/PNG assets can replace it later without
 * touching the simulation or the shell.
 */

interface Palette {
  fur: string;
  furDark: string;
  belly: string;
  wing: string;
  horn: string;
  innerEar: string;
}

const PALETTES: Record<FurVariant, Palette> = {
  ember: { fur: '#cf4433', furDark: '#a02c1f', belly: '#f7dcba', wing: '#e8b64c', horn: '#e8b64c', innerEar: '#f2a49b' },
  meadow: { fur: '#5cb85c', furDark: '#3e8f3e', belly: '#f5efdc', wing: '#2f7d4f', horn: '#efe3c2', innerEar: '#f2c4ce' },
  royal: { fur: '#8b5cc7', furDark: '#67409c', belly: '#e6d7fa', wing: '#5b3a8e', horn: '#e8b64c', innerEar: '#d9b8f0' },
  sky: { fur: '#84c7f0', furDark: '#5499c9', belly: '#ffffff', wing: '#eef6fb', horn: '#efe3c2', innerEar: '#f7c9d4' },
  sunset: { fur: '#f2a93b', furDark: '#d1811d', belly: '#fdeecb', wing: '#e2703a', horn: '#b3541e', innerEar: '#f7cfa0' },
  rainbow: { fur: '#b388eb', furDark: '#8a63c9', belly: '#ffffff', wing: '#f368e0', horn: '#e8b64c', innerEar: '#ffd3ec' },
};

const RAINBOW_PATCHES: ReadonlyArray<{ cx: number; cy: number; r: number; fill: string }> = [
  { cx: 70, cy: 122, r: 12, fill: '#ff6b6b' },
  { cx: 130, cy: 140, r: 10, fill: '#48dbfb' },
  { cx: 102, cy: 160, r: 9, fill: '#feca57' },
  { cx: 84, cy: 84, r: 8, fill: '#1dd1a1' },
];

function EggSvg({ palette, ready }: { palette: Palette; ready: boolean }) {
  return (
    <g className="egg-shape">
      <path
        d="M100 36 C 129 36 147 84 147 118 C 147 147 126 166 100 166 C 74 166 53 147 53 118 C 53 84 71 36 100 36 Z"
        fill="#fdf3d8"
        stroke={palette.furDark}
        strokeWidth="3"
      />
      <circle cx="82" cy="92" r="9" fill={palette.fur} opacity="0.75" />
      <circle cx="118" cy="76" r="7" fill={palette.fur} opacity="0.6" />
      <circle cx="104" cy="128" r="10" fill={palette.fur} opacity="0.7" />
      <circle cx="76" cy="140" r="6" fill={palette.fur} opacity="0.55" />
      {ready && (
        <polyline
          points="66,108 80,100 92,110 104,100 116,110 128,102 136,110"
          fill="none"
          stroke="#b09a72"
          strokeWidth="3"
          strokeLinejoin="round"
        />
      )}
    </g>
  );
}

export function DrabbitSvg({ summary, anim }: { summary: PetSummary; anim: PetAnimState }) {
  const palette = PALETTES[summary.fur];
  const form = summary.adultForm ?? 'young';
  const eyesClosed = summary.asleep || summary.stage === 'dead';

  if (summary.stage === 'egg') {
    return (
      <svg viewBox="0 0 200 200" className={`drabbit-svg anim-${anim}`} role="img" aria-label="A drabbit egg">
        <EggSvg palette={palette} ready={summary.readyToHatch} />
      </svg>
    );
  }

  return (
    <svg
      viewBox="0 0 200 200"
      className={`drabbit-svg anim-${anim} form-${form} ${summary.stage === 'dead' ? 'is-dead' : ''}`}
      role="img"
      aria-label={`${summary.name} the drabbit`}
    >
      {/* long curled tail, behind everything */}
      <g className="tail">
        <path
          d="M58 150 C 16 156 8 118 34 102 C 52 91 64 108 54 124"
          fill="none"
          stroke={palette.furDark}
          strokeWidth="13"
          strokeLinecap="round"
        />
        <circle cx="36" cy="103" r="10" fill={palette.wing} />
      </g>

      {/* cloth wings */}
      <g className="wing wing-far">
        <path d="M134 110 C 164 100 178 72 167 46 C 162 35 149 38 141 50 C 131 67 127 90 134 110 Z" fill={palette.wing} opacity="0.7" />
      </g>
      <g className="wing wing-near">
        <path d="M66 110 C 34 98 17 67 29 39 C 34 28 49 31 57 44 C 69 63 73 89 66 110 Z" fill={palette.wing} />
      </g>

      <g className="body-all">
        {/* feet */}
        <ellipse cx="70" cy="174" rx="17" ry="8" fill={palette.furDark} />
        <ellipse cx="130" cy="174" rx="17" ry="8" fill={palette.furDark} />

        {/* body + belly */}
        <ellipse cx="100" cy="132" rx="53" ry="44" fill={palette.fur} />
        <ellipse cx="100" cy="142" rx="30" ry="26" fill={palette.belly} />
        {summary.fur === 'rainbow' &&
          RAINBOW_PATCHES.map((p, i) => <circle key={i} cx={p.cx} cy={p.cy} r={p.r} fill={p.fill} opacity="0.8" />)}
        {form === 'scruffy' && (
          <>
            <ellipse cx="76" cy="118" rx="13" ry="8" fill={palette.furDark} opacity="0.45" />
            <ellipse cx="126" cy="152" rx="11" ry="7" fill={palette.furDark} opacity="0.4" />
          </>
        )}

        {/* ears (rotation lives in CSS so sick/scruffy can droop them) */}
        <g className="ear ear-l">
          <ellipse cx="79" cy="38" rx="12" ry="36" fill={palette.fur} />
          <ellipse cx="79" cy="44" rx="6" ry="24" fill={palette.innerEar} />
        </g>
        <g className="ear ear-r">
          <ellipse cx="119" cy="38" rx="12" ry="36" fill={palette.fur} />
          <ellipse cx="119" cy="44" rx="6" ry="24" fill={palette.innerEar} />
        </g>

        {/* head */}
        <circle cx="100" cy="84" r="35" fill={palette.fur} />
        {summary.fur === 'rainbow' && <circle cx="84" cy="70" r="8" fill="#1dd1a1" opacity="0.8" />}

        {/* horns */}
        <g className="horns" stroke={palette.horn} strokeWidth="7" strokeLinecap="round" fill="none">
          <path d="M85 57 C 77 45 77 32 85 22" />
          <path d="M115 57 C 123 45 123 32 115 22" />
        </g>

        {/* face */}
        {eyesClosed ? (
          <g stroke="#2b2135" strokeWidth="3.5" strokeLinecap="round" fill="none">
            <path d="M79 82 Q 87 88 95 82" />
            <path d="M105 82 Q 113 88 121 82" />
          </g>
        ) : (
          <g>
            <circle cx="87" cy="80" r="6.5" fill="#2b2135" />
            <circle cx="113" cy="80" r="6.5" fill="#2b2135" />
            <circle cx="89" cy="78" r="2" fill="#ffffff" />
            <circle cx="115" cy="78" r="2" fill="#ffffff" />
          </g>
        )}
        <ellipse cx="73" cy="95" rx="6" ry="4" fill={palette.innerEar} opacity="0.55" />
        <ellipse cx="127" cy="95" rx="6" ry="4" fill={palette.innerEar} opacity="0.55" />
        <ellipse cx="100" cy="97" rx="15" ry="10" fill={palette.belly} opacity="0.9" />
        <path d="M95 93 Q 100 89 105 93 Q 100 99 95 93 Z" fill="#e2688a" />
        <path d="M94 103 L 98 103 L 96 109 Z" fill="#ffffff" />

        {/* sick tint */}
        {summary.sick && summary.stage !== 'dead' && <circle cx="100" cy="105" r="72" fill="#86c232" opacity="0.16" />}

        {/* radiant sparkles */}
        {form === 'radiant' && (
          <g fill="#ffe066" className="sparkles">
            <path transform="translate(38 58)" d="M0 -7 L2 -2 L7 0 L2 2 L0 7 L-2 2 L-7 0 L-2 -2 Z" />
            <path transform="translate(162 48) scale(0.8)" d="M0 -7 L2 -2 L7 0 L2 2 L0 7 L-2 2 L-7 0 L-2 -2 Z" />
            <path transform="translate(156 124) scale(0.65)" d="M0 -7 L2 -2 L7 0 L2 2 L0 7 L-2 2 L-7 0 L-2 -2 Z" />
          </g>
        )}
      </g>

      {/* gravestone for the departed */}
      {summary.stage === 'dead' && (
        <g className="gravestone">
          <path d="M146 176 L146 152 C146 141 168 141 168 152 L168 176 Z" fill="#9aa3ad" />
          <text x="157" y="166" textAnchor="middle" fontSize="9" fill="#5c646c" fontFamily="sans-serif" fontWeight="bold">
            RIP
          </text>
        </g>
      )}
    </svg>
  );
}
