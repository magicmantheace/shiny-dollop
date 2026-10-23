from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render one Underreach WAV with the locally installed Kokoro-82M v1.0 model.")
    parser.add_argument("--model-home", type=Path, required=True)
    parser.add_argument("--voice", default="af_bella")
    parser.add_argument("--speed", type=float, default=1.0)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    text = sys.stdin.read().strip()
    if not text:
        raise SystemExit("Kokoro input text is empty")
    if not 0.25 <= args.speed <= 4.0:
        raise SystemExit("Kokoro speed must be between 0.25 and 4.0")

    home = args.model_home.resolve()
    config_path = home / "config.json"
    model_path = home / "kokoro-v1_0.pth"
    voice_path = home / "voices" / f"{args.voice}.pt"
    for required in (config_path, model_path, voice_path):
        if not required.is_file():
            raise SystemExit(f"Required installer Kokoro asset is missing: {required}")

    # The installer has already downloaded the complete model repository. Keep
    # synthesis offline so a runtime request can never silently swap models.
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"

    import numpy as np
    import soundfile as sf
    import torch
    from kokoro import KModel, KPipeline

    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = KModel(
        repo_id="hexgrad/Kokoro-82M",
        config=str(config_path),
        model=str(model_path),
    ).to(device).eval()

    language = args.voice[0].lower() if args.voice and args.voice[0].lower() in "abefhipjz" else "a"
    pipeline = KPipeline(
        lang_code=language,
        repo_id="hexgrad/Kokoro-82M",
        model=model,
    )

    chunks: list[np.ndarray] = []
    for result in pipeline(text, voice=str(voice_path), speed=args.speed, split_pattern=r"\n+"):
        audio = result.audio
        if audio is None:
            continue
        chunks.append(audio.detach().cpu().numpy())
    if not chunks:
        raise SystemExit("Kokoro generated no audio")

    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(output), np.concatenate(chunks), 24000, subtype="PCM_16", format="WAV")
    if not output.is_file() or output.stat().st_size <= 44:
        raise SystemExit("Kokoro output WAV was not created")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
