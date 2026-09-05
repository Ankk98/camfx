"""Human-settings config for camfx on Omarchy (Q19: TOML = human, JSON = machine).

File: ~/.config/camfx/config.toml
Schema:
  [general]
  # no general yet

  [notifications]
  enabled = true
  level = "low"          # low|normal|critical — maps to notify-send -u
  on_toggle = true       # camera toggle
  on_effect = true       # effect toggle

  [theme]
  live_reload = true     # Gio.FileMonitor hot-swap (Q7)

  [bar]
  position = "right"     # for docs; actual layout in shell.json
  section_after = "omarchy.audio"
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger("camfx_omarchy.config")

try:
	import tomllib  # Python 3.11+
except ImportError:  # pragma: no cover — fallback for older interpreters (should not happen on Omarchy/Arch)
	import tomli as tomllib  # type: ignore[no-redef]

CONFIG_DIR = Path.home() / ".config" / "camfx"
CONFIG_FILE = CONFIG_DIR / "config.toml"

_DEFAULT_CONFIG: dict[str, Any] = {
	"notifications": {
		"enabled": True,
		"level": "low",
		"on_toggle": True,
		"on_effect": True,
	},
	"theme": {
		"live_reload": True,
	},
	"bar": {
		"position": "right",
		"section_after": "omarchy.audio",
	},
}

_COMMENTED_DEFAULT = """# camfx — Omarchy human settings (TOML)
# This file is created on first `omarchy camfx install` and never overwritten on upgrade.
# Keys are merged with defaults via tomllib; unknown keys are preserved.

[notifications]
# Show OS notifications on camera/effect toggles via notify-send / shell notifications service
enabled = true
level = "low"          # low | normal | critical — maps to `notify-send -u <level>`
on_toggle = true       # notify on `omarchy camfx toggle` (camera on/off)
on_effect = true       # notify on `omarchy camfx effect toggle <key>`

[theme]
live_reload = true     # Hot-swap ~/.config/camfx/gtk.css via Gio.FileMonitor (Q7) — no restart required

[bar]
position = "right"
section_after = "omarchy.audio"   # omarchy-shell `omarchy plugin enable camfx.camfx --after omarchy.audio` (Q17)
"""


def _config_path() -> Path:
	import os
	ov = os.environ.get("CAMFX_CONFIG_FILE")
	if ov:
		return Path(ov)
	return CONFIG_FILE


def _deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
	out = {k: (v.copy() if isinstance(v, dict) else v) for k, v in base.items()}
	for k, v in overlay.items():
		if isinstance(v, dict) and isinstance(out.get(k), dict):
			out[k] = _deep_merge(out[k], v)  # type: ignore[arg-type]
		else:
			out[k] = v
	return out


def load_config() -> dict[str, Any]:
	"""Load merged config (defaults + file). Never raises."""
	path = _config_path()
	if not path.exists():
		return {k: (v.copy() if isinstance(v, dict) else v) for k, v in _DEFAULT_CONFIG.items()}
	try:
		with path.open("rb") as f:
			data = tomllib.load(f)
		if not isinstance(data, dict):
			return {k: (v.copy() if isinstance(v, dict) else v) for k, v in _DEFAULT_CONFIG.items()}
		return _deep_merge(_DEFAULT_CONFIG, data)
	except Exception as e:
		logger.warning("Failed to load camfx config %s: %s — using defaults", path, e)
		return {k: (v.copy() if isinstance(v, dict) else v) for k, v in _DEFAULT_CONFIG.items()}


def ensure_config_file() -> Path:
	"""Create ~/.config/camfx/config.toml with commented defaults if absent. Returns path."""
	path = _config_path()
	if path.exists():
		return path
	try:
		path.parent.mkdir(parents=True, exist_ok=True)
		path.write_text(_COMMENTED_DEFAULT, encoding="utf-8")
		logger.info("Created camfx config at %s", path)
	except Exception as e:
		logger.warning("Failed to create config file %s: %s", path, e)
	return path


def get_notifications_enabled(cfg: dict[str, Any] | None = None) -> bool:
	if cfg is None:
		cfg = load_config()
	return bool(cfg.get("notifications", {}).get("enabled", True))


def get_notification_level(cfg: dict[str, Any] | None = None) -> str:
	if cfg is None:
		cfg = load_config()
	lvl = str(cfg.get("notifications", {}).get("level", "low"))
	return lvl if lvl in ("low", "normal", "critical") else "low"


def save_config_value(key_path: str, value: Any) -> None:
	"""Naive dotted-key setter for `omarchy camfx config set notifications.enabled false`.

	Writes back preserving comments is hard; instead we do a merge-write of overrides
	into a minimal TOML without comments when `config get/set` is used. First install's
	commented file stays commented; subsequent `config set` calls rewrite only the needed table.

	This is intentionally simple — manual editing the file is the canonical path.
	"""
	path = _config_path()
	cfg = load_config()
	# set dotted
	parts = key_path.split(".")
	cur = cfg
	for p in parts[:-1]:
		cur = cur.setdefault(p, {})  # type: ignore[attr-defined]
	cur[parts[-1]] = value
	# naive serialize — only needed tables
	try:
		path.parent.mkdir(parents=True, exist_ok=True)
		lines: list[str] = []
		for section, vals in cfg.items():
			if isinstance(vals, dict):
				lines.append(f"[{section}]")
				for k, v in vals.items():
					if isinstance(v, bool):
						lines.append(f"{k} = {'true' if v else 'false'}")
					elif isinstance(v, (int, float)):
						lines.append(f"{k} = {v}")
					else:
						# escape quotes
						ev = str(v).replace('"', '\\"')
						lines.append(f'{k} = "{ev}"')
				lines.append("")
			else:
				ev = str(vals).replace('"', '\\"')
				lines.append(f'{section} = "{ev}"' if isinstance(vals, str) else f"{section} = {vals}")
		path.write_text("\n".join(lines), encoding="utf-8")
	except Exception as e:
		logger.warning("Failed to save config %s: %s", path, e)
