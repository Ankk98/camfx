# CamFX Tests - Quick Start

## Run unit tests

```bash
pytest tests/ -v
```

## Run a specific test file

```bash
pytest tests/test_effect_chaining.py -v
pytest tests/test_camera_devices.py -v
```

## Common options

```bash
pytest tests/ -q
pytest tests/ --maxfail=1
pytest tests/ -vv
```

