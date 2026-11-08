"""Strict, bounded JSON-lines process adapter for simulation only.

Run: python -m developmental_ai.environment_service
Caller sends one JSON object per line; responses include a matching request_id.
The process has no tool execution, file access, networking or OS actuators.
"""
from __future__ import annotations

import json
import sys
from typing import Any
from developmental_ai.environment_api import EnvironmentSession, canonical

SERVICE_SCHEMA = "developmental-ai.environment-service/v1"
MAX_INPUT = 65536  # includes bounded checkpoint replay records


class EnvironmentService:
    def __init__(self):
        self.session = None

    def handle(self, request: Any) -> dict:
        if type(request) is not dict or set(request) not in (
                {"schema", "request_id", "op", "config"},
                {"schema", "request_id", "op", "action", "expected_tick"},
                {"schema", "request_id", "op"},
                {"schema", "request_id", "op", "checkpoint"}):
            raise ValueError("invalid service request fields")
        if request["schema"] != SERVICE_SCHEMA or type(request["request_id"]) is not str or not (1 <= len(request["request_id"]) <= 64) or not all(c.isalnum() or c in "-_" for c in request["request_id"]):
            raise ValueError("invalid service schema or request identifier")
        op = request["op"]
        if op == "start" and set(request) == {"schema", "request_id", "op", "config"}:
            if self.session is not None:
                raise ValueError("close existing session first")
            if type(request["config"]) is not dict:
                raise ValueError("invalid session configuration")
            self.session = EnvironmentSession(**request["config"])
            result = {"frame": self.session.frame()}
        elif op == "restore" and set(request) == {"schema", "request_id", "op", "checkpoint"}:
            if self.session is not None:
                raise ValueError("close existing session first")
            self.session = EnvironmentSession.restore(request["checkpoint"])
            result = {"frame": self.session.frame()}
        elif op == "close" and len(request) == 3:
            self.session = None
            result = {"closed": True}
        elif self.session is None:
            raise ValueError("no active session")
        elif op == "step" and set(request) == {"schema", "request_id", "op", "action", "expected_tick"}:
            result = self.session.step(request["action"], expected_tick=request["expected_tick"])
        elif op == "observe" and len(request) == 3:
            result = {"frame": self.session.frame()}
        elif op == "checkpoint" and len(request) == 3:
            result = {"checkpoint": self.session.checkpoint()}
        else:
            raise ValueError("unknown operation or fields")
        return {"schema": SERVICE_SCHEMA, "request_id": request["request_id"], "result": result}


def serve(stdin=None, stdout=None) -> None:
    source = sys.stdin.buffer if stdin is None else stdin
    target = sys.stdout if stdout is None else stdout
    service = EnvironmentService()
    for raw in source:
        try:
            if isinstance(raw, bytes):
                if len(raw) > MAX_INPUT:
                    raise ValueError("request too large")
                raw = raw.decode("utf-8")
            if len(raw.encode("utf-8")) > MAX_INPUT:
                raise ValueError("request too large")
            request = json.loads(raw)
            response = service.handle(request)
        except (ValueError, TypeError, KeyError, UnicodeError, json.JSONDecodeError) as exc:
            # Intentionally no traceback or reflection of arbitrary input.
            response = {"schema": SERVICE_SCHEMA, "error": {"code": "invalid_request", "message": str(exc)[:120]}}
        target.write(canonical(response) + "\n")
        target.flush()


if __name__ == "__main__":
    serve()
