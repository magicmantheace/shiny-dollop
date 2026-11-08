"""F3 slice 1: director adapters + bounded planner (studio/director.py).

The stub is deterministic and always valid; the planner's gate is the
full scene + IPC validation, so a candidate with an unknown op (or any
other contract violation) is refused and recorded, never wrapped. The
HTTP adapter is exercised end-to-end through a fake transport — no
server exists on this VM and none is needed for these tests.
"""
import copy
import json
import tempfile
import unittest
from pathlib import Path

from studio.cli import main as cli_main
from studio.director import (AdapterError, HttpAdapter, PlannerError,
                             StubAdapter, plan_scene)
from studio.ipc import read_ipc, wrap_scene
from studio.schema import ValidationError, validate_scene

CONTEXT = {
    "scene_id": "planned_conversation",
    "environment_id": "preview_stage",
    "cast": [
        {"id": "traveler", "recipe_id": "traveler_01", "color": "#6499b5"},
        {"id": "innkeeper", "recipe_id": "innkeeper_01", "color": "#d9945c"},
    ],
    "lines": [
        {"actor_id": "traveler", "line": "Excuse me, do you have a room for the night?"},
        {"actor_id": "innkeeper", "line": "We have one upstairs. Come in."},
    ],
}

VALID_SCENE = StubAdapter().propose(CONTEXT)


class ScriptedAdapter:
    """Test double: replays a fixed list of proposals / exceptions."""

    name = "scripted"

    def __init__(self, outputs):
        self.outputs = list(outputs)
        self.contexts = []

    def propose(self, context):
        self.contexts.append(context)
        out = self.outputs.pop(0)
        if isinstance(out, Exception):
            raise out
        return copy.deepcopy(out)


def unknown_op_scene():
    scene = copy.deepcopy(VALID_SCENE)
    scene["events"].append(
        {"at_ms": 99999, "op": "explode", "actor_id": "traveler"})
    return scene


class StubAdapterTests(unittest.TestCase):
    def test_stub_scene_validates(self):
        scene = StubAdapter().propose(copy.deepcopy(CONTEXT))
        self.assertIs(validate_scene(scene), scene)
        wrap_scene(scene)  # IPC envelope validation accepts it too

    def test_stub_scene_is_deterministic(self):
        stub = StubAdapter()
        first = json.dumps(stub.propose(copy.deepcopy(CONTEXT)), indent=2)
        second = json.dumps(stub.propose(copy.deepcopy(CONTEXT)), indent=2)
        self.assertEqual(first, second)

    def test_stub_scene_shape(self):
        scene = StubAdapter().propose(copy.deepcopy(CONTEXT))
        ops = [e["op"] for e in scene["events"]]
        self.assertEqual(ops, ["spawn", "spawn", "speak", "speak", "camera"])
        speaks = [e for e in scene["events"] if e["op"] == "speak"]
        # First line at 800 ms; second after its 2934 ms speak hold + 400 ms gap.
        self.assertEqual([e["at_ms"] for e in speaks], [800, 4134])
        self.assertEqual(scene["events"][-1]["shot"], "two_shot")

    def test_stub_rejects_bad_context(self):
        stub = StubAdapter()
        for bad in ({}, {"cast": []}, {"lines": []},
                    {"cast": CONTEXT["cast"]},
                    {"cast": CONTEXT["cast"],
                     "lines": [{"actor_id": "ghost", "line": "Boo."}]},
                    {"cast": [{"id": "x"}], "lines": CONTEXT["lines"]}):
            with self.subTest(bad=bad):
                with self.assertRaises(AdapterError):
                    stub.propose(bad)


class PlannerTests(unittest.TestCase):
    def test_accepts_valid_first_proposal(self):
        result = plan_scene(StubAdapter(), copy.deepcopy(CONTEXT))
        self.assertEqual(result.adapter, "stub")
        self.assertEqual(result.attempts, 1)
        self.assertEqual(result.rejections, [])
        self.assertFalse(result.fallback)
        validate_scene(result.scene)

    def test_retries_garbage_then_valid(self):
        adapter = ScriptedAdapter([{"not": "a scene"}, VALID_SCENE])
        result = plan_scene(adapter, copy.deepcopy(CONTEXT))
        self.assertEqual(result.attempts, 2)
        self.assertEqual(len(result.rejections), 1)
        self.assertFalse(result.fallback)
        self.assertEqual(result.scene["scene_id"], VALID_SCENE["scene_id"])

    def test_retry_context_carries_rejection_and_input_is_untouched(self):
        context = copy.deepcopy(CONTEXT)
        adapter = ScriptedAdapter([{"not": "a scene"}, VALID_SCENE])
        plan_scene(adapter, context)
        self.assertNotIn("rejection", context)
        self.assertIn("rejection", adapter.contexts[1])
        self.assertIn("rejected", adapter.contexts[1]["rejection"])

    def test_adapter_error_counts_as_rejection(self):
        adapter = ScriptedAdapter([AdapterError("boom"), VALID_SCENE])
        result = plan_scene(adapter, copy.deepcopy(CONTEXT))
        self.assertEqual(result.attempts, 2)
        self.assertEqual(len(result.rejections), 1)
        self.assertIn("adapter error", result.rejections[0])

    def test_falls_back_after_max_attempts_of_garbage(self):
        adapter = ScriptedAdapter([{"junk": 1}, {"junk": 2}, {"junk": 3}])
        result = plan_scene(adapter, copy.deepcopy(CONTEXT), max_attempts=3)
        self.assertTrue(result.fallback)
        self.assertEqual(result.adapter, "stub")
        self.assertEqual(result.attempts, 3)
        self.assertEqual(len(result.rejections), 3)
        validate_scene(result.scene)
        self.assertEqual(result.scene, StubAdapter().propose(CONTEXT))

    def test_unknown_op_candidate_is_rejected(self):
        with self.assertRaises(ValidationError):
            validate_scene(unknown_op_scene())
        adapter = ScriptedAdapter([unknown_op_scene(), VALID_SCENE])
        result = plan_scene(adapter, copy.deepcopy(CONTEXT))
        self.assertEqual(result.attempts, 2)
        self.assertIn("unknown operation", result.rejections[0])
        adapter = ScriptedAdapter([unknown_op_scene()])
        result = plan_scene(adapter, copy.deepcopy(CONTEXT), max_attempts=1)
        self.assertTrue(result.fallback)
        self.assertNotIn("explode", [e["op"] for e in result.scene["events"]])

    def test_planner_error_when_fallback_cannot_validate(self):
        bad_context = copy.deepcopy(CONTEXT)
        bad_context["lines"] = [
            {"actor_id": "traveler", "line": "x" * 501}]  # over the 500-char bound
        with self.assertRaises(PlannerError):
            plan_scene(StubAdapter(), bad_context)

    def test_max_attempts_must_be_positive(self):
        with self.assertRaises(ValueError):
            plan_scene(StubAdapter(), copy.deepcopy(CONTEXT), max_attempts=0)


class HttpAdapterTests(unittest.TestCase):
    def transport_returning(self, reply):
        calls = []

        def transport(url, payload, timeout_s):
            calls.append((url, payload))
            if isinstance(reply, Exception):
                raise reply
            return reply

        transport.calls = calls
        return transport

    def test_parses_fenced_json_reply(self):
        scene_json = json.dumps(VALID_SCENE)
        for text in ("```json\n" + scene_json + "\n```",
                     "Here is the scene:\n```json\n" + scene_json + "\n```",
                     scene_json):
            with self.subTest(text=text[:24]):
                transport = self.transport_returning({"response": text})
                adapter = HttpAdapter(transport=transport)
                scene = adapter.propose(copy.deepcopy(CONTEXT))
                self.assertEqual(scene["scene_id"], VALID_SCENE["scene_id"])
                url, payload = transport.calls[0]
                self.assertTrue(url.endswith("/api/generate"))
                self.assertEqual(payload["model"], HttpAdapter.DEFAULT_MODEL)
                self.assertFalse(payload["stream"])

    def test_end_to_end_through_planner(self):
        transport = self.transport_returning(
            {"response": "```json\n" + json.dumps(VALID_SCENE) + "\n```"})
        result = plan_scene(HttpAdapter(transport=transport),
                            copy.deepcopy(CONTEXT))
        self.assertEqual(result.adapter, "http")
        self.assertEqual(result.attempts, 1)
        self.assertFalse(result.fallback)

    def test_transport_failure_raises_adapter_error(self):
        adapter = HttpAdapter(
            transport=self.transport_returning(ConnectionError("refused")))
        with self.assertRaises(AdapterError):
            adapter.propose(copy.deepcopy(CONTEXT))

    def test_non_json_reply_raises_adapter_error(self):
        adapter = HttpAdapter(transport=self.transport_returning(
            {"response": "Sorry, I cannot stage that."}))
        with self.assertRaises(AdapterError):
            adapter.propose(copy.deepcopy(CONTEXT))

    def test_missing_fields_raise_adapter_error(self):
        for reply in ({"done": True},                       # no 'response'
                      {"response": "{\"hello\": 1}"}):      # not a scene
            with self.subTest(reply=reply):
                adapter = HttpAdapter(
                    transport=self.transport_returning(reply))
                with self.assertRaises(AdapterError):
                    adapter.propose(copy.deepcopy(CONTEXT))

    def test_non_loopback_endpoint_refused(self):
        for endpoint in ("https://api.openai.com/v1",
                         "http://192.168.1.10:11434",
                         "http://example.com"):
            with self.subTest(endpoint=endpoint):
                with self.assertRaises(AdapterError):
                    HttpAdapter(endpoint=endpoint)


class PlanCliTests(unittest.TestCase):
    def test_plan_command_writes_enveloped_scene(self):
        with tempfile.TemporaryDirectory() as tmp:
            context_path = Path(tmp) / "context.json"
            context_path.write_text(json.dumps(CONTEXT), encoding="utf-8")
            out_path = Path(tmp) / "planned.json"
            code = cli_main(["plan", "--context", str(context_path),
                             "--out", str(out_path)])
            self.assertEqual(code, 0)
            scene = read_ipc(out_path)
            self.assertEqual(scene["scene_id"], "planned_conversation")
            validate_scene(scene)


if __name__ == "__main__":
    unittest.main()
