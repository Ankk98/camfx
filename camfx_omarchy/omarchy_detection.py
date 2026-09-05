"""Omarchy detection — query-only, no side effects (docs/file-layout.md Env bootstrap)."""

from __future__ import annotations

import os
import shutil
from pathlib import Path


def is_omarchy() -> bool:
	"""Return True if running on Omarchy (Arch + omarchy-shell).

	Checks, in order:
	- OMARCHY_PATH env (authoritative; set by default/bash/env-bootstrap, uwsm/env.d)
	- ~/.local/share/omarchy existence (seeded by omarchy-settings / omarchy package)
	- `which omarchy` router binary (bin/omarchy, 449 commands)
	"""
	return bool(
		os.environ.get("OMARCHY_PATH")
		or (Path.home() / ".local/share/omarchy").exists()
		or shutil.which("omarchy")
	)


def omarchy_path() -> Path:
	"""Resolve $OMARCHY_PATH (or default /usr/share/omarchy)."""
	raw = os.environ.get("OMARCHY_PATH") or "/usr/share/omarchy"
	return Path(raw)


def current_theme_dir() -> Path:
	"""Path to active Omarchy theme dir: ~/.local/state/omarchy/current/theme."""
	return Path.home() / ".local/state/omarchy/current/theme"


def current_theme_name_file() -> Path:
	return Path.home() / ".local/state/omarchy/current/theme.name"


def current_background_link() -> Path:
	return Path.home() / ".local/state/omarchy/current/background"


def shell_config_path() -> Path:
	return Path.home() / ".config/omarchy/shell.json"


def hooks_dir(name: str) -> Path:
	"""e.g. hooks_dir('theme-set') → ~/.config/omarchy/hooks/theme-set.d"""
	return Path.home() / ".config/omarchy/hooks" / f"{name}.d"


def plugins_dir() -> Path:
	return Path.home() / ".config/omarchy/plugins"
