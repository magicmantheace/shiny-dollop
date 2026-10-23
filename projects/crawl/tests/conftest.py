from __future__ import annotations

import pytest

from livingworld.generation import generate_world


@pytest.fixture
def world():
    return generate_world(
        seed="test-seed",
        name="Test World",
        target_population=10_000,
        persistent_npcs=100,
        towns=5,
        villages=20,
    )
