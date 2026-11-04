"""F3 slice 2 — offline voice clips: stub/external engines, phoneme
timing table, content-keyed clip cache, and the `speak` CLI.

No real speech engine exists on this VM, so the external engine is
exercised only through fake runners. All cache directories are temp
dirs; no WAV ever lands in git.
"""
import io
import json
import unittest
import wave
from contextlib import redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory

from studio.cli import main as cli_main
from studio.timing import (DEFAULT_TIMING, TimingConfig, speak_hold_ms)
from studio.voice import (SAMPLE_RATE_HZ, VISEMES, ClipResult, VoiceCache,
                          VoiceError, ExternalVoiceEngine, StubVoiceEngine,
                          cache_key, phoneme_table, wav_duration_ms)

LINE = "Excuse me, do you have a room for the night?"


def parse_wav(audio: bytes) -> dict:
    with wave.open(io.BytesIO(audio), "rb") as wav:
        return {
            "channels": wav.getnchannels(),
            "sampwidth": wav.getsampwidth(),
            "framerate": wav.getframerate(),
            "frames": wav.getnframes(),
        }


class CountingEngine:
    """Wraps the stub engine and counts synthesize calls."""

    def __init__(self):
        self.calls = 0
        self._inner = StubVoiceEngine()

    @property
    def name(self):
        return self._inner.name

    def synthesize(self, line, voice, timing=DEFAULT_TIMING, duration_ms=None):
        self.calls += 1
        return self._inner.synthesize(line, voice, timing,
                                      duration_ms=duration_ms)


class StubEngineTests(unittest.TestCase):
    def test_derived_duration_matches_speak_hold_exactly(self):
        engine = StubVoiceEngine()
        for line in (LINE, "We have one upstairs. Come in.", "Hello."):
            with self.subTest(line=line):
                result = engine.synthesize(line, "narrator")
                hold = speak_hold_ms(line)
                self.assertEqual(result.engine, "stub")
                self.assertEqual(result.duration_ms, hold)
                self.assertEqual(wav_duration_ms(result.audio), hold)
                info = parse_wav(result.audio)
                self.assertEqual(info["channels"], 1)
                self.assertEqual(info["sampwidth"], 2)
                self.assertEqual(info["framerate"], SAMPLE_RATE_HZ)
                # 16 frames per ms at 16000 Hz: sample-exact.
                self.assertEqual(info["frames"], hold * 16)

    def test_explicit_duration_honored(self):
        result = StubVoiceEngine().synthesize(LINE, "narrator",
                                              duration_ms=5000)
        self.assertEqual(result.duration_ms, 5000)
        self.assertEqual(parse_wav(result.audio)["frames"], 5000 * 16)

    def test_clamped_durations(self):
        engine = StubVoiceEngine()
        short = engine.synthesize("Hi", "narrator")
        self.assertEqual(short.duration_ms,
                         DEFAULT_TIMING.speak_min_hold_ms)
        self.assertEqual(short.duration_ms, speak_hold_ms("Hi"))
        long_line = "x" * 500
        long_result = engine.synthesize(long_line, "narrator")
        self.assertEqual(long_result.duration_ms,
                         DEFAULT_TIMING.speak_max_hold_ms)
        self.assertEqual(long_result.duration_ms, speak_hold_ms(long_line))

    def test_custom_rate_changes_duration(self):
        timing = TimingConfig(speak_chars_per_second=30.0)
        result = StubVoiceEngine().synthesize(LINE, "narrator", timing)
        self.assertEqual(result.duration_ms, speak_hold_ms(LINE, timing=timing))

    def test_determinism(self):
        engine = StubVoiceEngine()
        first = engine.synthesize(LINE, "narrator")
        second = engine.synthesize(LINE, "narrator")
        self.assertEqual(first.audio, second.audio)

    def test_bad_input_rejected(self):
        engine = StubVoiceEngine()
        for line, voice in (("", "narrator"), ("  ", "narrator"),
                            ("Hello.", ""), (None, "narrator")):
            with self.subTest(line=line, voice=voice):
                with self.assertRaises(VoiceError):
                    engine.synthesize(line, voice)


class ExternalEngineTests(unittest.TestCase):
    def _wav_runner(self, seen):
        def runner(argv, input_text):
            seen.append((argv, input_text))
            return StubVoiceEngine().synthesize(
                input_text, "any").audio
        return runner

    def test_success_via_fake_runner(self):
        seen = []
        engine = ExternalVoiceEngine(self._wav_runner(seen),
                                     argv_template=("fake-tts", "-v", "{voice}"),
                                     name="fake")
        result = engine.synthesize(LINE, "alice")
        self.assertEqual(seen, [(["fake-tts", "-v", "alice"], LINE)])
        self.assertEqual(result.engine, "fake")
        self.assertEqual(result.duration_ms, wav_duration_ms(result.audio))
        self.assertEqual(result.duration_ms, speak_hold_ms(LINE))

    def test_runner_failure_raises_voice_error(self):
        def boom(argv, input_text):
            raise RuntimeError("no such binary")
        engine = ExternalVoiceEngine(boom, name="fake")
        with self.assertRaises(VoiceError):
            engine.synthesize(LINE, "alice")

    def test_garbage_output_raises_voice_error(self):
        engine = ExternalVoiceEngine(lambda argv, text: b"this is not a wav",
                                     name="fake")
        with self.assertRaises(VoiceError):
            engine.synthesize(LINE, "alice")

    def test_non_bytes_output_raises_voice_error(self):
        engine = ExternalVoiceEngine(lambda argv, text: "wav-ish", name="fake")
        with self.assertRaises(VoiceError):
            engine.synthesize(LINE, "alice")

    def test_default_name_derived_from_program(self):
        engine = ExternalVoiceEngine(lambda argv, text: b"")
        self.assertTrue(engine.name.startswith("external:"))
        self.assertIn("espeak-ng", engine.name)


class PhonemeTableTests(unittest.TestCase):
    def assert_partitions(self, line, hold):
        segments = phoneme_table(line, hold)
        self.assertEqual(segments[0]["start_ms"], 0)
        self.assertEqual(segments[-1]["end_ms"], hold)
        total = 0
        for prev, cur in zip(segments, segments[1:]):
            self.assertEqual(cur["start_ms"], prev["end_ms"])
        for seg in segments:
            self.assertGreaterEqual(seg["end_ms"], seg["start_ms"])
            self.assertIn(seg["viseme"], VISEMES)
            total += seg["end_ms"] - seg["start_ms"]
        self.assertEqual(total, hold)
        return segments

    def test_partitions_hold_for_several_lines(self):
        for line, hold in (
            (LINE, speak_hold_ms(LINE)),
            ("Hello.", 800),
            ("One", 15000),
            ("a bb ccc dddd eeeee ffffff ggggggg", 4321),
            ("Short", 100),
        ):
            with self.subTest(line=line, hold=hold):
                segments = self.assert_partitions(line, hold)
                self.assertEqual(len(segments), len(line.split()))

    def test_one_word_line_spans_whole_hold(self):
        segments = phoneme_table("Hello", 2000)
        self.assertEqual(len(segments), 1)
        self.assertEqual(segments[0]["start_ms"], 0)
        self.assertEqual(segments[0]["end_ms"], 2000)

    def test_proportional_to_word_length(self):
        # Equal-rate split: a 2-char and a 6-char word over 800 ms
        # divide 200 / 600.
        segments = phoneme_table("aa bbbbbb", 800)
        self.assertEqual(
            [(s["start_ms"], s["end_ms"]) for s in segments],
            [(0, 200), (200, 800)])

    def test_no_empty_segments_when_hold_affords(self):
        segments = phoneme_table("a bb c", 800)
        for seg in segments:
            self.assertGreater(seg["end_ms"], seg["start_ms"])

    def test_wordless_line_is_one_silence_segment(self):
        segments = phoneme_table("   ", 1200)
        self.assertEqual(segments, [{"word": "", "start_ms": 0,
                                     "end_ms": 1200, "viseme": "sil"}])

    def test_viseme_onset_rule(self):
        cases = {
            "Peter": "PP", "bravo": "PP", "Mother": "PP",
            "fish": "FF", "Victor": "FF",
            "the": "TH", "this": "TH",
            "dog": "DD", "Time": "DD",
            "king": "kk", "go": "kk", "cat": "kk", "hello": "kk",
            "chin": "CH", "ship": "CH", "jump": "CH",
            "sun": "SS", "zoo": "SS",
            "night": "nn", "lamp": "nn",
            "run": "RR",
            "apple": "aa", "egg": "E", "in": "I", "open": "O",
            "under": "U", "we": "U",
            "42": "sil",
        }
        for word, expected in cases.items():
            with self.subTest(word=word):
                segments = phoneme_table(word, 1000)
                self.assertEqual(segments[0]["viseme"], expected)

    def test_bad_hold_rejected(self):
        for bad in (0, -5, "800", 800.5, True, None):
            with self.subTest(bad=bad):
                with self.assertRaises(VoiceError):
                    phoneme_table("Hello.", bad)


class CacheTests(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.cache = VoiceCache(Path(self._tmp.name) / "voice-cache")

    def test_record_fields_and_file_written(self):
        record = self.cache.get_or_synthesize(LINE, "narrator",
                                              engine=StubVoiceEngine())
        self.assertFalse(record.from_cache)
        self.assertEqual(record.engine, "stub")
        self.assertEqual(record.voice, "narrator")
        self.assertEqual(record.duration_ms, speak_hold_ms(LINE))
        self.assertEqual(record.key,
                         cache_key("stub", "narrator", LINE, DEFAULT_TIMING))
        self.assertTrue(record.wav_path.is_file())
        audio = record.wav_path.read_bytes()
        self.assertEqual(record.wav_len, len(audio))
        self.assertEqual(record.wav_len, len(audio))
        import hashlib
        self.assertEqual(record.wav_sha256,
                         hashlib.sha256(audio).hexdigest())
        self.assertEqual(record.line_sha256,
                         hashlib.sha256(LINE.encode("utf-8")).hexdigest())
        self.assertEqual(len(record.phonemes), len(LINE.split()))
        self.assertEqual(record.phonemes[-1]["end_ms"], record.duration_ms)

    def test_cache_hit_avoids_resynthesis(self):
        engine = CountingEngine()
        first = self.cache.get_or_synthesize(LINE, "narrator", engine=engine)
        second = self.cache.get_or_synthesize(LINE, "narrator", engine=engine)
        self.assertEqual(engine.calls, 1)
        self.assertFalse(first.from_cache)
        self.assertTrue(second.from_cache)
        self.assertEqual(first.key, second.key)
        self.assertEqual(first.wav_sha256, second.wav_sha256)
        self.assertEqual(first.duration_ms, second.duration_ms)
        self.assertEqual(first.phonemes, second.phonemes)

    def test_cache_survives_new_instance(self):
        engine = CountingEngine()
        self.cache.get_or_synthesize(LINE, "narrator", engine=engine)
        fresh = VoiceCache(self.cache.cache_dir)
        record = fresh.get_or_synthesize(LINE, "narrator", engine=engine)
        self.assertEqual(engine.calls, 1)
        self.assertTrue(record.from_cache)

    def test_different_voice_or_rate_different_key(self):
        engine = CountingEngine()
        base = self.cache.get_or_synthesize(LINE, "narrator", engine=engine)
        other_voice = self.cache.get_or_synthesize(LINE, "innkeeper",
                                                   engine=engine)
        faster = self.cache.get_or_synthesize(
            LINE, "narrator", engine=engine,
            timing=TimingConfig(speak_chars_per_second=30.0))
        keys = {base.key, other_voice.key, faster.key}
        self.assertEqual(len(keys), 3)
        self.assertEqual(engine.calls, 3)
        self.assertNotEqual(base.duration_ms, faster.duration_ms)

    def test_explicit_duration_keys_separately(self):
        engine = CountingEngine()
        derived = self.cache.get_or_synthesize(LINE, "narrator", engine=engine)
        explicit = self.cache.get_or_synthesize(LINE, "narrator", engine=engine,
                                                duration_ms=5000)
        self.assertNotEqual(derived.key, explicit.key)
        self.assertEqual(explicit.duration_ms, 5000)

    def test_corrupt_entry_resynthesizes(self):
        engine = CountingEngine()
        record = self.cache.get_or_synthesize(LINE, "narrator", engine=engine)
        record.wav_path.write_bytes(b"corrupted")
        again = self.cache.get_or_synthesize(LINE, "narrator", engine=engine)
        self.assertEqual(engine.calls, 2)
        self.assertFalse(again.from_cache)
        self.assertEqual(again.wav_sha256, record.wav_sha256)

    def test_wavs_stay_in_cache_dir(self):
        self.cache.get_or_synthesize(LINE, "narrator", engine=StubVoiceEngine())
        wavs = list(self.cache.cache_dir.glob("*.wav"))
        self.assertEqual(len(wavs), 1)


class CliTests(unittest.TestCase):
    def test_speak_command_uses_cache(self):
        with TemporaryDirectory() as tmp:
            cache_dir = Path(tmp) / "vc"
            argv = ["speak", "--line", LINE, "--voice", "narrator",
                    "--engine", "stub", "--voice-cache", str(cache_dir)]
            out = io.StringIO()
            with redirect_stdout(out):
                self.assertEqual(cli_main(argv), 0)
            first = out.getvalue()
            self.assertIn("synthesized", first)
            self.assertIn("segments", first)
            self.assertIn("key", first)
            out = io.StringIO()
            with redirect_stdout(out):
                self.assertEqual(cli_main(argv), 0)
            self.assertIn("cache", out.getvalue())
            self.assertEqual(len(list(cache_dir.glob("*.wav"))), 1)

    def test_speak_requires_line(self):
        with self.assertRaises(SystemExit):
            cli_main(["speak", "--engine", "stub"])


if __name__ == "__main__":
    unittest.main()
