"""Resilient Ollama runtime policy for the live Underreach Alpha media sidecar.

Qwen3 thinking remains disabled and generation remains bounded. Alpha accepts
strict JSON first, then recovers an embedded JSON object from harmless wrapper
text such as Markdown code fences. Parsed objects are validated against the
actual Underreach writer/verifier Pydantic contracts before they are accepted.
If both bounded attempts still fail, the worker uses a deterministic
schema-compatible fallback derived only from the already-supplied canonical
prompt data so media production cannot be stalled by non-canonical model
formatting. Deterministic claim verification remains the final authority and
canonical simulation state is never changed.
"""
from __future__ import annotations

import json
from typing import Any

from . import underreach_ollama_providers as ollama


PROTOCOL = "underreach.alpha-ollama-runtime.v4"
WRITER_NUM_PREDICT = 512
VERIFIER_NUM_PREDICT = 768
RETRY_NUM_PREDICT = 1024
DEFAULT_NUM_PREDICT = 768
FALLBACK_REASON_CODE = "alpha_ollama_structured_fallback"


def _initial_num_predict(self, model: str) -> int:
    if model == self.config.writer_model:
        return WRITER_NUM_PREDICT
    if model == self.config.verifier_model:
        return VERIFIER_NUM_PREDICT
    return DEFAULT_NUM_PREDICT


def _request_body(
    self,
    *,
    model: str,
    messages: list[dict[str, str]],
    schema: dict[str, Any],
    temperature: float,
    seed: int,
    num_predict: int,
) -> dict[str, Any]:
    return {
        "model": model,
        "messages": messages,
        "stream": False,
        "think": False,
        "format": schema,
        "keep_alive": self.config.keep_alive,
        "options": {
            "temperature": temperature,
            "seed": seed,
            "num_predict": num_predict,
        },
    }


def _parse_json_object_text(text: str) -> dict[str, Any] | None:
    value = text.strip()
    if not value:
        return None

    try:
        parsed = json.loads(value)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    decoder = json.JSONDecoder()
    for index, character in enumerate(value):
        if character != "{":
            continue
        try:
            parsed, _end = decoder.raw_decode(value[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    return None


def _parse_structured_body(body: dict[str, Any]) -> dict[str, Any] | None:
    message = body.get("message")
    if not isinstance(message, dict) or not isinstance(message.get("content"), str):
        return None
    return _parse_json_object_text(message["content"])


def _validated_payload(self, *, model: str, payload: dict[str, Any]) -> dict[str, Any] | None:
    """Return a normalized payload only when it matches the real provider contract."""
    try:
        if model == self.config.writer_model:
            return ollama.OllamaStorySelection.model_validate(payload).model_dump(mode="json")
        if model == self.config.verifier_model:
            return ollama.OllamaAssessmentBatch.model_validate(payload).model_dump(mode="json")
    except Exception:
        return None
    return payload


def _user_prompt(messages: list[dict[str, str]]) -> str:
    return "\n".join(
        item.get("content", "")
        for item in messages
        if isinstance(item, dict) and item.get("role") == "user" and isinstance(item.get("content"), str)
    )


def _writer_fallback(self, messages: list[dict[str, str]]) -> dict[str, Any] | None:
    prompt = _user_prompt(messages)
    marker = "Allowed facts:\n"
    if marker not in prompt:
        return None
    raw = prompt.split(marker, 1)[1].strip()
    try:
        facts = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(facts, list):
        return None
    fact_ids = [
        item.get("fact_id")
        for item in facts
        if isinstance(item, dict) and isinstance(item.get("fact_id"), str) and item.get("fact_id")
    ]
    if not fact_ids:
        return None
    limit = max(1, int(getattr(self.config, "max_selected_facts", 6)))
    return {
        "fact_ids": fact_ids[:limit],
        "style_line": None,
        "tone": "cinematic",
    }


def _verifier_fallback(messages: list[dict[str, str]]) -> dict[str, Any] | None:
    prompt = _user_prompt(messages)
    start_marker = "Sentences: "
    end_marker = "\nAllowed facts:"
    if start_marker not in prompt or end_marker not in prompt:
        return None
    raw = prompt.split(start_marker, 1)[1].split(end_marker, 1)[0].strip()
    try:
        sentences = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(sentences, list):
        return None
    return {
        "assessments": [
            {
                "sentence_index": index,
                "classification": "ambiguous",
                "reason_code": FALLBACK_REASON_CODE,
            }
            for index, _sentence in enumerate(sentences)
        ]
    }


def _deterministic_fallback(
    self,
    *,
    model: str,
    messages: list[dict[str, str]],
) -> dict[str, Any] | None:
    if model == self.config.writer_model:
        return _writer_fallback(self, messages)
    if model == self.config.verifier_model:
        return _verifier_fallback(messages)
    return None


def _bounded_chat_json(
    self,
    *,
    model: str,
    messages: list[dict[str, str]],
    schema: dict[str, Any],
    temperature: float,
    seed: int,
) -> dict[str, Any]:
    first_limit = _initial_num_predict(self, model)
    attempts = (first_limit,) if first_limit >= RETRY_NUM_PREDICT else (first_limit, RETRY_NUM_PREDICT)

    last_body: dict[str, Any] | None = None
    for num_predict in attempts:
        last_body = self._post(
            "/api/chat",
            _request_body(
                self,
                model=model,
                messages=messages,
                schema=schema,
                temperature=temperature,
                seed=seed,
                num_predict=num_predict,
            ),
        )
        parsed = _parse_structured_body(last_body)
        if parsed is None:
            continue
        validated = _validated_payload(self, model=model, payload=parsed)
        if validated is not None:
            return validated

    fallback = _deterministic_fallback(self, model=model, messages=messages)
    if fallback is not None:
        validated_fallback = _validated_payload(self, model=model, payload=fallback)
        if validated_fallback is not None:
            return validated_fallback

    if last_body is not None:
        message = last_body.get("message")
        if not isinstance(message, dict) or not isinstance(message.get("content"), str):
            raise ollama.OllamaProviderError("Ollama response omitted message.content")
    raise ollama.OllamaProviderError(
        f"Ollama structured output was not recoverable after bounded retry ({attempts[-1]} tokens)"
    )


_bounded_chat_json.__underreach_alpha_bounded__ = True


def install_alpha_ollama_runtime() -> None:
    """Install the resilient bounded policy once in the dedicated Alpha worker process."""

    current = ollama._OllamaClient.chat_json
    if getattr(current, "__underreach_alpha_bounded__", False):
        return
    ollama._OllamaClient.chat_json = _bounded_chat_json


__all__ = [
    "PROTOCOL",
    "WRITER_NUM_PREDICT",
    "VERIFIER_NUM_PREDICT",
    "RETRY_NUM_PREDICT",
    "DEFAULT_NUM_PREDICT",
    "FALLBACK_REASON_CODE",
    "install_alpha_ollama_runtime",
]
