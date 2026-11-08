# Hardware and latency budget

**Target owner hardware:** RTX 3060 12 GB, i5-10400F, 32 GB RAM, Windows 11. **No measurements have been taken.**

| Subsystem | Initial goal | Notes |
| --- | --- | --- |
| Godot stylized preview | >= 30 FPS at 1080p | p95 frame <= 33.3 ms; measure on owner PC |
| Character count | 2 active, expand 4–8 later | CPU skinning, draw calls, GPU pressure vary |
| Render VRAM | Aim 2–4 GB | Heuristic ceiling to leave space for inference |
| LLM / TTS combined | Remaining available memory only | Prefer small quantized models, CPU fallback |
| Main-thread blocking | 0 synchronous AI calls | Actor loop must run independently |
| Animation event dispatch | < 5 ms p95 goal | Validate ahead of dispatch |
| Asset creation | Outside live frame budget | Paused/queued while live show runs |

## Profiling protocol

Record GPU utilization, peak VRAM, CPU load, scene FPS average/p95/1% low, event-to-visible latency, TTS latency and frame jitter. Test a 60-second two-character scene plus simultaneous background inference on owner hardware. Repeat 3 runs cold/warm. Document Godot version, model/quantization, resolution and OS.

## Fallback ladder

1. Pause asset generation.
2. Queue LLM proposals; continue cached beats.
3. Lower shadows, resolution and post-processing.
4. Reduce character/prop density and IK updates.
5. Fall back to precomputed voices/gestures.

Never interpret 30 or 60 FPS as proven capability until those tests are executed.
