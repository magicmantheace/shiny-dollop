"""Offline voice clips (F3 slice 2): engine interface, stub engine,
external CLI engine slot, phoneme timing table and a content-keyed clip
cache.

An *engine* turns one line of dialogue into a WAV clip:

    synthesize(line, voice, timing, duration_ms=None) -> ClipResult

Engines never touch the network and never write files; persistence is
the cache's job, mirroring the director layer's separation (F3.1).

- `StubVoiceEngine` — deterministic and offline: renders a silent WAV
  whose duration is EXACTLY the ADR-009 speak hold for the line under
  the given `TimingConfig` (an explicit `duration_ms` is honored the
  same way `studio.timing.speak_hold_ms` honors it). Silence at the
  right length is the honest stand-in until a real engine runs on
  owner hardware: scheduling, caching and lip-sync timing all consume
  durations, not waveforms. The stub renders 16000 Hz 16-bit mono —
  16 frames per millisecond — so every hold is sample-exact.
- `ExternalVoiceEngine` — slot for a future espeak/piper-style CLI
  engine. The process call goes through an injectable
  `runner(argv, input_text) -> bytes` callable (the line is the input
  text, the WAV comes back as bytes); `subprocess_runner` is the real
  runner for the CLI. Output that does not parse as WAV, a failed
  runner, or a non-zero exit raises `VoiceError`.

`phoneme_table` produces an ESTIMATED word-level alignment: segments
partition the hold proportionally to word length and each word gets a
coarse viseme label from a deterministic onset rule (see
`_viseme_for`). There is no acoustic analysis anywhere in this module;
the table is the data path a blendshape-capable rig would consume for
lip sync. The adopted Quaternius rig has no morph targets, so no
visual lip sync is claimed or possible yet.

Clip cache (`VoiceCache`): clips are stored as `<key>.wav` files in a
cache directory OUTSIDE git — constructor argument, else the
`AI_ANIMATION_VOICE_CACHE` environment variable, else
`<system temp>/ai-animation-studio/voice-cache`. The key is the
SHA-256 of the canonical JSON of every input that can change the
audio (engine name, voice, line, the timing rate + clamps, and an
explicit duration when given). No index file is kept: the key is a
pure function of the inputs and the record is reconstructed from the
stored WAV (duration parsed from the file itself), so the directory
is self-describing and a corrupt entry simply re-synthesizes.
"""
from __future__ import annotations

import hashlib
import io
import json
import math
import os
import subprocess
import tempfile
import wave
from dataclasses import dataclass, field
from pathlib import Path

try:
    from .timing import DEFAULT_TIMING, TimingConfig, speak_hold_ms
except ImportError:  # standalone module use (studio/ on sys.path)
    from timing import DEFAULT_TIMING, TimingConfig, speak_hold_ms  # type: ignore[no-redef]


class VoiceError(ValueError):
    """A voice engine or the clip cache could not produce a valid clip
    (bad input, engine failure, or output that is not WAV audio)."""


# ---------------------------------------------------------------------------
# WAV helpers
# ---------------------------------------------------------------------------

# 16000 Hz, 16-bit mono: exactly 16 frames per millisecond, so a stub
# clip's length equals its speak hold with no rounding.
SAMPLE_RATE_HZ = 16000
_FRAMES_PER_MS = SAMPLE_RATE_HZ // 1000


def wav_duration_ms(audio: bytes) -> int:
    """Duration of a WAV byte string in milliseconds (rounded).

    Raises VoiceError when the bytes do not parse as WAV audio.
    """
    if not isinstance(audio, (bytes, bytearray)) or len(audio) < 44:
        raise VoiceError("not WAV audio (too short or not bytes)")
    try:
        with wave.open(io.BytesIO(bytes(audio)), "rb") as wav:
            frames = wav.getnframes()
            rate = wav.getframerate()
    except (wave.Error, EOFError) as exc:
        raise VoiceError(f"not WAV audio: {exc}") from exc
    if rate <= 0:
        raise VoiceError("not WAV audio (no sample rate)")
    return round(frames * 1000 / rate)


def _silent_wav(duration_ms: int) -> bytes:
    frames = duration_ms * _FRAMES_PER_MS
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(SAMPLE_RATE_HZ)
        wav.writeframes(b"\x00\x00" * frames)
    return buffer.getvalue()


def _require_speakable(line: object, voice: object) -> None:
    if not isinstance(line, str) or not line.strip():
        raise VoiceError("line must be a non-empty string")
    if not isinstance(voice, str) or not voice.strip():
        raise VoiceError("voice must be a non-empty string")


# ---------------------------------------------------------------------------
# Engines
# ---------------------------------------------------------------------------

@dataclass
class ClipResult:
    """One synthesized clip: the WAV bytes, their duration, and the
    name of the engine that produced them."""

    audio: bytes
    duration_ms: int
    engine: str


class StubVoiceEngine:
    """Deterministic offline engine: silence at exactly the speak hold.

    The voice name does not change the silence (it still keys the
    cache, exactly as a real voice would); the timing config and an
    explicit duration change the length via `speak_hold_ms`.
    """

    name = "stub"

    def synthesize(self, line: str, voice: str,
                   timing: TimingConfig = DEFAULT_TIMING,
                   duration_ms: int | None = None) -> ClipResult:
        _require_speakable(line, voice)
        hold = speak_hold_ms(line, duration_ms, timing)
        return ClipResult(audio=_silent_wav(hold), duration_ms=hold,
                          engine=self.name)


def subprocess_runner(argv: list[str], input_text: str) -> bytes:
    """Real runner for `ExternalVoiceEngine`: feed the line on stdin,
    return stdout as the WAV bytes. Raises VoiceError on spawn failure
    or a non-zero exit."""
    try:
        proc = subprocess.run(
            argv, input=input_text.encode("utf-8"),
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
    except OSError as exc:
        raise VoiceError(
            f"external voice command failed to start: {exc}") from exc
    if proc.returncode != 0:
        detail = proc.stderr.decode("utf-8", "replace").strip()[:200]
        raise VoiceError(
            f"external voice command exited {proc.returncode}: {detail}")
    return proc.stdout


class ExternalVoiceEngine:
    """Slot for an espeak/piper-style CLI engine, via an injectable
    runner.

    `argv_template` items may contain `{voice}`, substituted per call;
    the line itself is passed to the runner as the input text. The
    default template is the espeak-ng shape (`espeak-ng --stdout
    --voice <voice>`, line on stdin, WAV on stdout) — no such engine
    exists on this VM, so with the real `subprocess_runner` this raises
    VoiceError until one is installed on owner hardware. `name` keys
    the cache; it defaults to `external:<program>` so distinct
    commands do not collide, and tests pass an explicit name.
    """

    DEFAULT_ARGV_TEMPLATE = ("espeak-ng", "--stdout", "--voice", "{voice}")

    def __init__(self, runner, argv_template=None, name: str | None = None):
        if not callable(runner):
            raise VoiceError("runner must be callable")
        template = tuple(argv_template) if argv_template is not None \
            else self.DEFAULT_ARGV_TEMPLATE
        if not template or not all(isinstance(p, str) and p for p in template):
            raise VoiceError("argv_template must be a non-empty sequence "
                             "of non-empty strings")
        self.runner = runner
        self.argv_template = template
        self.name = name if name is not None else f"external:{template[0]}"

    def synthesize(self, line: str, voice: str,
                   timing: TimingConfig = DEFAULT_TIMING,
                   duration_ms: int | None = None) -> ClipResult:
        _require_speakable(line, voice)
        argv = [part.replace("{voice}", voice) for part in self.argv_template]
        try:
            audio = self.runner(argv, line)
        except VoiceError:
            raise
        except Exception as exc:  # injected runners may raise anything
            raise VoiceError(f"external voice runner failed: {exc}") from exc
        if not isinstance(audio, (bytes, bytearray)):
            raise VoiceError("external voice runner did not return bytes")
        audio = bytes(audio)
        # Raises VoiceError on non-WAV output; the clip's duration is
        # whatever the real audio actually runs, not the speak hold.
        duration = wav_duration_ms(audio)
        return ClipResult(audio=audio, duration_ms=duration, engine=self.name)


# ---------------------------------------------------------------------------
# Phoneme / viseme timing (ESTIMATED — no acoustic analysis)
# ---------------------------------------------------------------------------

#: The coarse viseme label set (Oculus-style classes).
VISEMES = frozenset({
    "sil", "PP", "FF", "TH", "DD", "kk", "CH", "SS", "nn", "RR",
    "aa", "E", "I", "O", "U",
})


def _viseme_for(word: str) -> str:
    """Coarse viseme for one word from its opening letters.

    Deterministic onset rule, first match wins: digraphs `th` -> TH,
    `ch`/`sh` -> CH; then by first letter — p/b/m -> PP (lips closed),
    f/v -> FF, d/t -> DD, k/g/c/q/h -> kk, j -> CH, s/z/x -> SS,
    n/l -> nn, r -> RR, a -> aa, e -> E, i/y -> I, o -> O, u/w -> U.
    A word with no letters (digits, punctuation) is `sil`.
    """
    letters = "".join(ch for ch in word.lower() if ch.isalpha())
    if not letters:
        return "sil"
    if letters.startswith("th"):
        return "TH"
    if letters.startswith(("ch", "sh")):
        return "CH"
    head = letters[0]
    if head in "pbm":
        return "PP"
    if head in "fv":
        return "FF"
    if head in "dt":
        return "DD"
    if head in "kgcqh":
        return "kk"
    if head == "j":
        return "CH"
    if head in "szx":
        return "SS"
    if head in "nl":
        return "nn"
    if head == "r":
        return "RR"
    if head == "a":
        return "aa"
    if head == "e":
        return "E"
    if head in "iy":
        return "I"
    if head == "o":
        return "O"
    if head in "uw":
        return "U"
    return "nn"


def phoneme_table(line: str, hold_ms: int) -> list[dict]:
    """ESTIMATED word-level alignment partitioning `hold_ms`.

    One segment per whitespace-separated word:
    `{word, start_ms, end_ms, viseme}`. Segment lengths are
    proportional to word length, distributed by largest remainder so
    they sum to the hold exactly: segments are contiguous, the first
    starts at 0 and the last ends at exactly `hold_ms`. When the hold
    can afford it (>= 1 ms per word) no segment is empty. A line with
    no words yields a single `sil` segment spanning the hold.
    """
    if not isinstance(line, str):
        raise VoiceError("line must be a string")
    if type(hold_ms) is not int or hold_ms < 1:
        raise VoiceError("hold_ms must be a positive integer")
    words = line.split()
    if not words:
        return [{"word": "", "start_ms": 0, "end_ms": hold_ms,
                 "viseme": "sil"}]
    weights = [len(word) for word in words]
    total = sum(weights)
    raw = [hold_ms * w / total for w in weights]
    spans = [math.floor(r) for r in raw]
    remainder = hold_ms - sum(spans)
    by_fraction = sorted(range(len(words)),
                         key=lambda i: (-(raw[i] - spans[i]), i))
    for i in by_fraction[:remainder]:
        spans[i] += 1
    if hold_ms >= len(words):
        for i, span in enumerate(spans):
            if span == 0:
                donor = max(range(len(words)), key=lambda j: spans[j])
                spans[donor] -= 1
                spans[i] = 1
    segments = []
    cursor = 0
    for word, span in zip(words, spans):
        segments.append({
            "word": word,
            "start_ms": cursor,
            "end_ms": cursor + span,
            "viseme": _viseme_for(word),
        })
        cursor += span
    return segments


# ---------------------------------------------------------------------------
# Clip cache
# ---------------------------------------------------------------------------

def cache_key(engine_name: str, voice: str, line: str,
              timing: TimingConfig = DEFAULT_TIMING,
              duration_ms: int | None = None) -> str:
    """SHA-256 of the canonical JSON of every input that can change
    the audio: engine, voice, line, timing rate + clamps, and an
    explicit duration when one is given."""
    payload = {
        "engine": engine_name,
        "voice": voice,
        "line": line,
        "speak_chars_per_second": timing.speak_chars_per_second,
        "speak_min_hold_ms": timing.speak_min_hold_ms,
        "speak_max_hold_ms": timing.speak_max_hold_ms,
        "duration_ms": duration_ms,
    }
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


@dataclass
class ClipRecord:
    """A cached (or freshly synthesized) clip and its timing data.

    `phonemes` is the ESTIMATED table from `phoneme_table` over the
    clip's actual duration. `from_cache` is True when the WAV came
    from the cache directory without re-synthesizing.
    """

    key: str
    engine: str
    voice: str
    line_sha256: str
    duration_ms: int
    wav_len: int
    wav_sha256: str
    phonemes: list = field(default_factory=list)
    wav_path: Path | None = None
    from_cache: bool = False


def default_cache_dir() -> Path:
    """Cache directory: `AI_ANIMATION_VOICE_CACHE` when set, else a
    per-user temp location. Always outside git."""
    env = os.environ.get("AI_ANIMATION_VOICE_CACHE")
    if env:
        return Path(env)
    return Path(tempfile.gettempdir()) / "ai-animation-studio" / "voice-cache"


class VoiceCache:
    """Content-keyed store of synthesized clips (`<key>.wav` files).

    A second call with the same key returns the stored clip without
    calling the engine again; the stored WAV is re-parsed on a hit, so
    a corrupt or non-WAV entry falls through to re-synthesis.
    """

    def __init__(self, cache_dir: Path | None = None):
        self.cache_dir = Path(cache_dir) if cache_dir is not None \
            else default_cache_dir()

    def get_or_synthesize(self, line: str, voice: str, *, engine,
                          timing: TimingConfig = DEFAULT_TIMING,
                          duration_ms: int | None = None) -> ClipRecord:
        _require_speakable(line, voice)
        engine_name = getattr(engine, "name", None)
        if not isinstance(engine_name, str) or not engine_name:
            raise VoiceError("engine must expose a non-empty 'name'")
        key = cache_key(engine_name, voice, line, timing, duration_ms)
        path = self.cache_dir / f"{key}.wav"
        if path.is_file():
            audio = path.read_bytes()
            try:
                duration = wav_duration_ms(audio)
            except VoiceError:
                pass  # corrupt entry: fall through and re-synthesize
            else:
                return self._record(key, engine_name, voice, line, audio,
                                    duration, path, from_cache=True)
        result = engine.synthesize(line, voice, timing,
                                   duration_ms=duration_ms)
        audio = bytes(result.audio)
        duration = wav_duration_ms(audio)  # also validates the output
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        tmp = self.cache_dir / f"{key}.tmp"
        tmp.write_bytes(audio)
        tmp.replace(path)
        return self._record(key, engine_name, voice, line, audio, duration,
                            path, from_cache=False)

    @staticmethod
    def _record(key, engine_name, voice, line, audio, duration, path,
                from_cache) -> ClipRecord:
        return ClipRecord(
            key=key,
            engine=engine_name,
            voice=voice,
            line_sha256=hashlib.sha256(line.encode("utf-8")).hexdigest(),
            duration_ms=duration,
            wav_len=len(audio),
            wav_sha256=hashlib.sha256(audio).hexdigest(),
            phonemes=phoneme_table(line, duration),
            wav_path=path,
            from_cache=from_cache,
        )


__all__ = [
    "VoiceError",
    "ClipResult",
    "ClipRecord",
    "StubVoiceEngine",
    "ExternalVoiceEngine",
    "subprocess_runner",
    "VoiceCache",
    "cache_key",
    "default_cache_dir",
    "phoneme_table",
    "wav_duration_ms",
    "VISEMES",
    "SAMPLE_RATE_HZ",
]
