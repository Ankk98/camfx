# CamFX Tests

This directory contains unit tests for core CamFX logic (effect chaining, effect controller behavior, camera device helpers).

v4l2-only cleanup removed the graph integration tests.

## Running tests

Run unit tests:

```bash
pytest -v
```

Run a specific file:

```bash
pytest tests/test_effect_chaining.py -v
pytest tests/test_camera_devices.py -v
```

## What’s covered

- `EffectChain`: chaining, updating, removing, and applying effects
- `EffectController`: thread-safe effect chain updates
- `camera_devices`: listing/probing helpers for `/dev/video*`

