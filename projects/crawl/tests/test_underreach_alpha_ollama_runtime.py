from __future__ import annotations

import json

import httpx

from livingworld import underreach_ollama_providers as ollama
from livingworld.underreach_alpha_ollama_runtime import (
    FALLBACK_REASON_CODE,
    RETRY_NUM_PREDICT,
    VERIFIER_NUM_PREDICT,
    WRITER_NUM_PREDICT,
    install_alpha_ollama_runtime,
)


def _writer_payload() -> dict:
    return {"fact_ids": ["fact_001"], "style_line": None, "tone": "cinematic"}


def _verifier_payload() -> dict:
    return {
        "assessments": [
            {"sentence_index": 0, "classification": "factual", "reason_code": "supported"}
        ]
    }


def test_alpha_ollama_runtime_disables_qwen_thinking_and_bounds_generation() -> None:
    original = ollama._OllamaClient.chat_json
    captured: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        captured.append(body)
        payload = _writer_payload() if body["model"] == "qwen3:8b" else _verifier_payload()
        return httpx.Response(200, json={"message": {"content": json.dumps(payload)}})

    transport = httpx.Client(transport=httpx.MockTransport(handler), base_url="http://test")
    try:
        install_alpha_ollama_runtime()
        installed = ollama._OllamaClient.chat_json
        install_alpha_ollama_runtime()
        assert ollama._OllamaClient.chat_json is installed

        config = ollama.OllamaProviderConfig()
        client = ollama._OllamaClient(config, client=transport)
        client.chat_json(
            model=config.writer_model,
            messages=[{"role": "user", "content": "writer"}],
            schema=ollama.OllamaStorySelection.model_json_schema(),
            temperature=0.0,
            seed=1,
        )
        client.chat_json(
            model=config.verifier_model,
            messages=[{"role": "user", "content": "verifier"}],
            schema=ollama.OllamaAssessmentBatch.model_json_schema(),
            temperature=0.0,
            seed=2,
        )
    finally:
        ollama._OllamaClient.chat_json = original
        transport.close()

    assert len(captured) == 2
    assert captured[0]["think"] is False
    assert captured[1]["think"] is False
    assert captured[0]["options"]["num_predict"] == WRITER_NUM_PREDICT
    assert captured[1]["options"]["num_predict"] == VERIFIER_NUM_PREDICT


def test_alpha_ollama_runtime_retries_wrong_shape_json_before_accepting_valid_writer_payload() -> None:
    original = ollama._OllamaClient.chat_json
    captured: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(json.loads(request.content))
        payload = {"ok": True} if len(captured) == 1 else _writer_payload()
        return httpx.Response(200, json={"message": {"content": json.dumps(payload)}})

    transport = httpx.Client(transport=httpx.MockTransport(handler), base_url="http://test")
    try:
        install_alpha_ollama_runtime()
        config = ollama.OllamaProviderConfig()
        client = ollama._OllamaClient(config, client=transport)
        parsed = client.chat_json(
            model=config.writer_model,
            messages=[{"role": "user", "content": "writer"}],
            schema=ollama.OllamaStorySelection.model_json_schema(),
            temperature=0.0,
            seed=7,
        )
    finally:
        ollama._OllamaClient.chat_json = original
        transport.close()

    assert parsed == _writer_payload()
    assert len(captured) == 2
    assert captured[0]["options"]["num_predict"] == WRITER_NUM_PREDICT
    assert captured[1]["options"]["num_predict"] == RETRY_NUM_PREDICT


def test_alpha_ollama_runtime_recovers_valid_writer_json_from_markdown_wrapper() -> None:
    original = ollama._OllamaClient.chat_json

    def handler(_request: httpx.Request) -> httpx.Response:
        content = "Here is the result:\n```json\n" + json.dumps(_writer_payload()) + "\n```"
        return httpx.Response(200, json={"message": {"content": content}})

    transport = httpx.Client(transport=httpx.MockTransport(handler), base_url="http://test")
    try:
        install_alpha_ollama_runtime()
        config = ollama.OllamaProviderConfig()
        client = ollama._OllamaClient(config, client=transport)
        parsed = client.chat_json(
            model=config.writer_model,
            messages=[{"role": "user", "content": "writer"}],
            schema=ollama.OllamaStorySelection.model_json_schema(),
            temperature=0.0,
            seed=3,
        )
    finally:
        ollama._OllamaClient.chat_json = original
        transport.close()

    assert parsed == _writer_payload()


def test_alpha_writer_uses_deterministic_allowed_fact_fallback_after_two_bad_responses() -> None:
    original = ollama._OllamaClient.chat_json

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"message": {"content": json.dumps({"wrong": "shape"})}})

    facts = [
        {"fact_id": "fact_002", "scope": "event", "subject": "b", "predicate": "event_type", "value": "B"},
        {"fact_id": "fact_001", "scope": "event", "subject": "a", "predicate": "event_type", "value": "A"},
    ]
    prompt = "Chapter: HIGHLIGHT_TEST\nAllowed facts:\n" + json.dumps(facts, separators=(",", ":"), sort_keys=True)
    transport = httpx.Client(transport=httpx.MockTransport(handler), base_url="http://test")
    try:
        install_alpha_ollama_runtime()
        config = ollama.OllamaProviderConfig(max_selected_facts=1)
        client = ollama._OllamaClient(config, client=transport)
        parsed = client.chat_json(
            model=config.writer_model,
            messages=[{"role": "user", "content": prompt}],
            schema=ollama.OllamaStorySelection.model_json_schema(),
            temperature=0.0,
            seed=4,
        )
    finally:
        ollama._OllamaClient.chat_json = original
        transport.close()

    assert parsed == {"fact_ids": ["fact_002"], "style_line": None, "tone": "cinematic"}


def test_alpha_verifier_rejects_wrong_shape_json_and_uses_schema_valid_conservative_fallback() -> None:
    original = ollama._OllamaClient.chat_json
    captured: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={"message": {"content": json.dumps({"assessments": [{"classification": "factual"}]})}},
        )

    sentences = ["One.", "Two."]
    prompt = "Sentences: " + json.dumps(sentences) + "\nAllowed facts: []"
    transport = httpx.Client(transport=httpx.MockTransport(handler), base_url="http://test")
    try:
        install_alpha_ollama_runtime()
        config = ollama.OllamaProviderConfig()
        client = ollama._OllamaClient(config, client=transport)
        parsed = client.chat_json(
            model=config.verifier_model,
            messages=[{"role": "user", "content": prompt}],
            schema=ollama.OllamaAssessmentBatch.model_json_schema(),
            temperature=0.0,
            seed=5,
        )
        validated = ollama.OllamaAssessmentBatch.model_validate(parsed)
    finally:
        ollama._OllamaClient.chat_json = original
        transport.close()

    assert len(captured) == 2
    assert [item.sentence_index for item in validated.assessments] == [0, 1]
    assert all(item.classification == "ambiguous" for item in validated.assessments)
    assert all(item.reason_code == FALLBACK_REASON_CODE for item in validated.assessments)
