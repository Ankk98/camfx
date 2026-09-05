"""Persisted camfx state — effect chain across reboots (Q22, Q19).

TOML = human settings (colors, config). JSON = machine state (manifests, persisted chains).
So the effect chain is JSON at ~/.local/state/camfx/state.json.

Schema:
{
  "version": 1,
  "effects": [
    {"type": "blur", "config": {"strength": 25}},
    ...
  ],
  "camera": {"source_id": "/dev/video0", "width": 640, "height": 480, "fps": 30}
}
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger("camfx.state")

STATE_DIR = Path.home() / ".local" / "state" / "camfx"
STATE_FILE = STATE_DIR / "state.json"
STATE_VERSION = 1


def _state_path() -> Path:
	# Allow override for tests
	import os
	ov = os.environ.get("CAMFX_STATE_FILE")
	if ov:
		return Path(ov)
	return STATE_FILE


def save_state(effects: list[dict[str, Any]], camera: dict[str, Any] | None = None) -> None:
	"""Persist effect chain + optional camera config."""
	path = _state_path()
	try:
		path.parent.mkdir(parents=True, exist_ok=True)
		payload = {
			"version": STATE_VERSION,
			"effects": effects,
		}
		if camera is not None:
			payload["camera"] = camera
		tmp = path.with_suffix(".tmp")
		tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
		tmp.replace(path)
		logger.debug("Saved camfx state to %s (%d effects)", path, len(effects))
	except Exception as e:
		logger.warning("Failed to save camfx state to %s: %s", path, e)


def load_state() -> dict[str, Any] | None:
	"""Load persisted state, or None if missing/invalid."""
	path = _state_path()
	if not path.exists():
		return None
	try:
		data = json.loads(path.read_text(encoding="utf-8"))
		if not isinstance(data, dict):
			return None
		if data.get("version") != STATE_VERSION:
			logger.warning("State version mismatch (got %s, want %s) — ignoring %s", data.get("version"), STATE_VERSION, path)
			return None
		return data
	except Exception as e:
		logger.warning("Failed to load camfx state from %s: %s", path, e)
		return None


def clear_state() -> None:
	path = _state_path()
	try:
		if path.exists():
			path.unlink()
	except Exception:
		pass
