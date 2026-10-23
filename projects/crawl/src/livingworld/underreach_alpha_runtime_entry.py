"""Resilient entry point for the Underreach Alpha runtime.

The accepted Alpha runtime owns canonical simulation state. This entry point only
replaces its presentation/status JSON file writer with the Windows-lock-tolerant
atomic writer before delegating to the existing runtime main function.
"""
from __future__ import annotations

from . import underreach_alpha_runtime as runtime
from .underreach_atomic_json_io import atomic_json


runtime._atomic_json = atomic_json


if __name__ == "__main__":
    runtime.main()
