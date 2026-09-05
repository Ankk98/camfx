"""CLI for omarchy-camfx integration (bin/omarchy-camfx* shims, routed as `omarchy camfx ...`).

Uses `argparse` (no extra deps) and delegates to camfx's D-Bus interface
and to theme_adapter/config helpers. Notifications are gated by
~/.config/camfx/config.toml [notifications].enabled (Q8, Q18).
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

logger = logging.getLogger("camfx_omarchy.cli")

# ------------------------------------------------------------------ helpers

def _should_notify(args_quiet: bool | None = False) -> bool:
	if args_quiet:
		return False
	try:
		from .config import load_config
		cfg = load_config()
		return bool(cfg.get("notifications", {}).get("enabled", True))
	except Exception:
		return True


def _notify_level(cfg_level: str | None = None) -> str:
	if cfg_level:
		return cfg_level if cfg_level in ("low", "normal", "critical") else "low"
	try:
		from .config import get_notification_level
		return get_notification_level()
	except Exception:
		return "low"


def _notify(title: str, body: str = "", level: str | None = None, quiet: bool = False) -> None:
	if quiet or not _should_notify(quiet):
		return
	# Check specific sub-keys: on_toggle / on_effect
	try:
		from .config import load_config
		cfg = load_config()
		# gate by sub-key for effect notifications
		if "effect" in title.lower() or "blur" in body.lower():
			if not cfg.get("notifications", {}).get("on_effect", True):
				return
		if "camera" in title.lower() or "toggle" in title.lower():
			if not cfg.get("notifications", {}).get("on_toggle", True):
				return
	except Exception:
		pass
	lvl = level or _notify_level()
	if lvl not in ("low", "normal", "critical"):
		lvl = "low"
	if not shutil.which("notify-send"):
		return
	try:
		subprocess.run(["notify-send", "-u", lvl, title, body], timeout=3, check=False)
	except Exception:
		pass


def _dbus_control():
	try:
		import dbus  # type: ignore
		bus = dbus.SessionBus()
		svc = bus.get_object("org.camfx.Control1", "/org/camfx/Control1")
		ctrl = dbus.Interface(svc, "org.camfx.Control1")
		return ctrl
	except Exception as e:
		return None


def _status_payload() -> dict[str, Any]:
	"""Build status JSON payload (available/active/count/label/effects/camera)."""
	payload: dict[str, Any] = {"available": False, "active": False, "count": 0, "label": "", "effects": [], "camera": {}}
	ctrl = _dbus_control()
	if ctrl is None:
		payload["error"] = "D-Bus not available or camfx not running"
		return payload
	try:
		active = bool(ctrl.GetCameraState())
		effects = list(ctrl.GetCurrentEffects())
		payload["available"] = True
		payload["active"] = active
		payload["count"] = len(effects)
		if effects:
			types = [str(e[0]) for e in effects]
			payload["label"] = types[0] if len(types) == 1 else ",".join(types)
			payload["effects"] = [
				{"type": str(etype), "class": str(klass), "config": dict(cfg)}
				for etype, klass, cfg in effects
			]
		try:
			src, w, h, fps = ctrl.GetCameraConfig()
			payload["camera"] = {"source_id": str(src), "width": int(w), "height": int(h), "fps": int(fps)}
		except Exception:
			pass
	except Exception as e:
		payload["error"] = str(e)
	return payload


# ------------------------------------------------------------------ commands

def cmd_status(args: argparse.Namespace) -> int:
	payload = _status_payload()
	# Waybar legacy alias shape: text/class/tooltip — but we already use generic json; alias ok
	if args.json or args.waybar_json:
		print(json.dumps(payload))
	else:
		# human
		if not payload.get("available"):
			print(f"camfx not available: {payload.get('error','')}")
			return 1
		state = "ON" if payload["active"] else "OFF"
		print(f"Camera: {state}")
		if payload["count"]:
			print(f"Effects ({payload['count']}): {payload['label']}")
			for e in payload["effects"]:
				print(f"  - {e['type']} ({e['class']}) {e['config']}")
		else:
			print("Effects: none")
		if payload.get("camera"):
			c = payload["camera"]
			print(f"Camera config: {c.get('source_id')} {c.get('width')}x{c.get('height')}@{c.get('fps')}")
	return 0


def cmd_toggle(args: argparse.Namespace) -> int:
	ctrl = _dbus_control()
	if ctrl is None:
		print("camfx D-Bus not available — is `camfx start --dbus` running?", file=sys.stderr)
		_notify("camfx · daemon off", "Run: camfx start --dbus", level="critical", quiet=args.quiet)
		return 1
	try:
		cur = bool(ctrl.GetCameraState())
		target = cur
		if args.on and not args.off:
			target = True
		elif args.off and not args.on:
			target = False
		else:
			target = not cur
		if target == cur:
			print(f"Camera already {'ON' if cur else 'OFF'}")
			return 0
		ok = bool(ctrl.StartCamera() if target else ctrl.StopCamera())
		if ok:
			print(f"Camera {'ON' if target else 'OFF'}")
			_notify(f"camfx · camera {'on' if target else 'off'}", f"{'ON' if target else 'OFF'}", level="low", quiet=args.quiet)
			return 0
		print("Failed to toggle camera", file=sys.stderr)
		return 1
	except Exception as e:
		print(f"Error: {e}", file=sys.stderr)
		return 1


def cmd_effect_toggle(args: argparse.Namespace) -> int:
	ctrl = _dbus_control()
	if ctrl is None:
		print("camfx D-Bus not available", file=sys.stderr)
		return 1
	key = args.key
	# Check if effect already in chain
	try:
		effects = list(ctrl.GetCurrentEffects())
		types = [str(e[0]) for e in effects]
		if key in types:
			ok = bool(ctrl.RemoveEffectByType(key))
			if ok:
				print(f"Effect {key} removed")
				_notify(f"camfx · {key} off", "", level="normal", quiet=args.quiet)
				return 0
			print(f"Failed to remove {key}", file=sys.stderr)
			return 1
		else:
			# Add effect; for replace, no --image means use default (control.py handles fallback)
			cfg: dict[str, Any] = {}
			if key == "replace" and args.image:
				cfg["image"] = args.image
			if key == "blur" and args.strength is not None:
				cfg["strength"] = int(args.strength)
			if key == "brightness":
				if args.brightness is not None:
					cfg["brightness"] = int(args.brightness)
				if args.contrast is not None:
					cfg["contrast"] = float(args.contrast)
			# D-Bus wants dict with signature; km
			import dbus  # type: ignore
			# Pass as plain dict — dbus-python will coerce
			ok = bool(ctrl.AddEffect(key, cfg))
			if ok:
				print(f"Effect {key} added")
				_notify(f"camfx · {key} on", "", level="normal", quiet=args.quiet)
				return 0
			print(f"Failed to add {key}", file=sys.stderr)
			return 1
	except Exception as e:
		print(f"Error: {e}", file=sys.stderr)
		return 1


def cmd_cycle(args: argparse.Namespace) -> int:
	# Cycle through EFFECT_KEYS ring (for bar middle-click + keyboard)
	from camfx.effect_specs import EFFECT_KEYS  # type: ignore
	ctrl = _dbus_control()
	if ctrl is None:
		print("camfx D-Bus not available", file=sys.stderr)
		return 1
	try:
		effects = list(ctrl.GetCurrentEffects())
		cur = str(effects[0][0]) if effects else ""
		ring = list(EFFECT_KEYS) + [""]
		# Normalize "" as clear state
		if cur not in ring:
			cur = ""
		idx = ring.index(cur)
		# next / prev
		if args.prev:
			nidx = (idx - 1) % len(ring)
		else:
			nidx = (idx + 1) % len(ring)
		nxt = ring[nidx]
		if nxt == "":
			# clear
			for et in list(EFFECT_KEYS):
				try:
					ctrl.RemoveEffectByType(et)
				except Exception:
					pass
			print("Effects cleared")
			_notify("camfx · effects cleared", "", level="normal", quiet=args.quiet)
		else:
			# add/toggle — use AddEffect (idempotent) with defaults
			import dbus  # type: ignore
			ctrl.AddEffect(nxt, {})
			print(f"Cycled to {nxt}")
			_notify(f"camfx · {nxt} on", "", level="normal", quiet=args.quiet)
		return 0
	except Exception as e:
		print(f"Error: {e}", file=sys.stderr)
		return 1


def cmd_theme_sync(args: argparse.Namespace) -> int:
	try:
		from .theme_adapter import apply
		path = apply(args.theme_name)
		print(f"Wrote {path}")
		return 0
	except Exception as e:
		print(f"Error: {e}", file=sys.stderr)
		return 1


def cmd_doctor(args: argparse.Namespace) -> int:
	# Delegate to camfx doctor logic but reuse payload
	# For now, shell out to `camfx doctor --json`
	try:
		out = subprocess.run([sys.executable, "-m", "camfx.cli", "doctor", "--json"] if False else ["camfx", "doctor", "--json"],
		                     capture_output=True, text=True, timeout=5)
		if out.returncode == 0 and out.stdout.strip():
			print(out.stdout.strip())
			return 0
	except Exception:
		pass
	# fallback: build payload like camfx doctor
	import shutil, subprocess as sp
	payload: dict[str, Any] = {}
	payload["ffmpeg"] = {"ok": bool(shutil.which("ffmpeg"))}
	payload["v4l2_ctl"] = {"ok": bool(shutil.which("v4l2-ctl"))}
	try:
		ls = sp.run(["lsmod"], capture_output=True, text=True, timeout=3)
		payload["v4l2loopback"] = {"loaded": "v4l2loopback" in ls.stdout}
	except Exception as e:
		payload["v4l2loopback"] = {"loaded": False, "error": str(e)}
	payload["dbus"] = {"reachable": _dbus_control() is not None}
	if args.json:
		print(json.dumps(payload))
	else:
		print(json.dumps(payload, indent=2))
	return 0


def cmd_gui(args: argparse.Namespace) -> int:
	# Launch camfx gui via uwsm-app if on Omarchy, else plain
	cmd = ["camfx", "gui"]
	if shutil.which("uwsm-app"):
		cmd = ["uwsm-app", "--"] + cmd
	try:
		subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
		print("Launched camfx GUI")
		return 0
	except Exception as e:
		print(f"Error: {e}", file=sys.stderr)
		return 1


def cmd_config(args: argparse.Namespace) -> int:
	from .config import load_config, save_config_value
	if args.action == "get":
		cfg = load_config()
		if args.key:
			parts = args.key.split(".")
			cur: Any = cfg
			for p in parts:
				if isinstance(cur, dict):
					cur = cur.get(p)
				else:
					cur = None
					break
			print(json.dumps({args.key: cur}) if args.json else f"{args.key} = {cur}")
		else:
			print(json.dumps(cfg, indent=2) if args.json else str(cfg))
		return 0
	elif args.action == "set":
		if not args.key or args.value is None:
			print("Usage: omarchy camfx config set <key> <value>", file=sys.stderr)
			return 2
		# coerce value: "true"/"false" -> bool, numeric
		val: Any = args.value
		if val.lower() in ("true", "false"):
			val = val.lower() == "true"
		else:
			try:
				if "." in val:
					val = float(val)
				else:
					val = int(val)
			except Exception:
				pass
		save_config_value(args.key, val)
		print(f"Set {args.key} = {val}")
		return 0
	return 2


def _install_hooks() -> int:
	src_dir = Path(__file__).parent / "hooks"
	hooks = [
		("theme-set.sh", Path.home() / ".config/omarchy/hooks/theme-set.d/50-camfx.sh"),
		("post-boot.sh", Path.home() / ".config/omarchy/hooks/post-boot.d/50-camfx.sh"),
	]
	for src_name, dst in hooks:
		src = src_dir / src_name
		if not src.exists():
			continue
		dst.parent.mkdir(parents=True, exist_ok=True)
		if dst.exists():
			print(f"Skip {dst} — already exists")
			continue
		try:
			dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
			dst.chmod(0o755)
			print(f"Installed {dst}")
		except Exception as e:
			print(f"Failed to install {dst}: {e}", file=sys.stderr)
	return 0


def _install_bindings(force: bool = False) -> int:
	# Check for Hyprland bindings dir
	src = Path(__file__).parent / "bindings" / "camfx.lua"
	dst_dir = Path.home() / ".config/hypr/bindings"
	dst = dst_dir / "camfx.lua"
	main_bindings = Path.home() / ".config/hypr/bindings.lua"
	if not src.exists():
		print("No bindings source found", file=sys.stderr)
		return 0
	# Probe existing bindings for collision (Q20: no-overwrite)
	occupied: list[str] = []
	if main_bindings.exists():
		try:
			txt = main_bindings.read_text(encoding="utf-8")
			for combo in ["SUPER ALT + C", "SUPER ALT + SHIFT + C", "SUPER ALT + B", "SUPER ALT + R"]:
				if combo.lower() in txt.lower():
					occupied.append(combo)
		except Exception:
			pass
	if occupied and not force:
		print(f"⚠ Bindings already contain {', '.join(occupied)} — camfx bindings not installed.", file=sys.stderr)
		print("  Free them or run: omarchy camfx install --bindings --force", file=sys.stderr)
		_notify("camfx bindings skipped", f"Already bound: {', '.join(occupied)} — manual intervention needed", level="normal")
		return 0
	# Install snippet
	try:
		dst_dir.mkdir(parents=True, exist_ok=True)
		if dst.exists() and not force:
			print(f"Skip {dst} — already exists")
		else:
			dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
			print(f"Installed {dst}")
		# Ensure main bindings.lua requires it
		if main_bindings.exists():
			txt = main_bindings.read_text(encoding="utf-8")
			if "camfx" not in txt:
				with main_bindings.open("a", encoding="utf-8") as f:
					f.write('\n-- camfx (Omarchy plugin) — loaded via camfx.lua\nrequire("hypr.bindings.camfx")\n')
				print(f"Patched {main_bindings} to require hypr.bindings.camfx")
		else:
			# create minimal
			main_bindings.write_text('require("hypr.bindings.camfx")\n', encoding="utf-8")
			print(f"Created {main_bindings}")
		# validate
		try:
			subprocess.run(["hyprctl", "configerrors"], timeout=3, check=False)
		except Exception:
			pass
	except Exception as e:
		print(f"Bindings install failed: {e}", file=sys.stderr)
	return 0


def _install_bar() -> int:
	# Shell plugin: ~/.config/omarchy/plugins/camfx.camfx/
	# Resolve packaged plugin via importlib.resources (pip install) or fallback to repo packaging/
	user_plugin = Path.home() / ".config/omarchy/plugins/camfx.camfx"
	# Try importlib.resources first (installed site-packages)
	packaged_plugin: Path | None = None
	try:
		import importlib.resources as _res
		# Python 3.9+ API: files()
		try:
			packaged_plugin = Path(str(_res.files("camfx_omarchy") / "shell_plugin/camfx.camfx"))
			if not packaged_plugin.exists():
				packaged_plugin = None
		except Exception:
			packaged_plugin = None
	except Exception:
		pass
	if packaged_plugin is None:
		# Fallback to repo-relative (when running from checkout without pip install)
		candidates = [
			Path(__file__).parents[1] / "packaging/omarchy/omarchy-shell-plugin/camfx.camfx",
			Path(__file__).parent / "shell_plugin/camfx.camfx",
		]
		for cand in candidates:
			if cand.exists():
				packaged_plugin = cand
				break
	if packaged_plugin is not None and packaged_plugin.exists():
		try:
			import shutil as sh
			if user_plugin.exists():
				print(f"Skip {user_plugin} — already exists")
			else:
				sh.copytree(packaged_plugin, user_plugin)
				print(f"Installed plugin {user_plugin}")
			# Enable via omarchy plugin enable (right — after audio, Q17)
			try:
				subprocess.run(["omarchy", "plugin", "enable", "camfx.camfx", "--after", "omarchy.audio"], timeout=5, check=False)
				print("Enabled camfx.camfx after omarchy.audio")
			except Exception:
				pass
			try:
				subprocess.run(["omarchy-shell", "shell", "rescanPlugins"], timeout=5, check=False)
			except Exception:
				pass
		except Exception as e:
			print(f"Bar install failed: {e}", file=sys.stderr)
	else:
		print("No packaged shell plugin found — skipping bar", file=sys.stderr)
	return 0


def _install_systemd(enable: bool = False) -> int:
	src = Path(__file__).parent / "systemd/camfx.service"
	dst = Path.home() / ".config/systemd/user/camfx.service"
	if src.exists():
		dst.parent.mkdir(parents=True, exist_ok=True)
		if not dst.exists():
			try:
				dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
				print(f"Installed {dst}")
			except Exception as e:
				print(f"Failed to install {dst}: {e}", file=sys.stderr)
		if enable:
			try:
				subprocess.run(["systemctl", "--user", "daemon-reload"], timeout=5, check=False)
				subprocess.run(["systemctl", "--user", "enable", "--now", "camfx"], timeout=10, check=False)
				print("Enabled camfx.service")
			except Exception as e:
				print(f"systemd enable failed: {e}", file=sys.stderr)
	return 0


def cmd_install(args: argparse.Namespace) -> int:
	from .config import ensure_config_file
	ensure_config_file()
	# hooks always
	_install_hooks()
	if args.bindings:
		_install_bindings(force=args.force)
	if args.bar or not any([args.bindings, args.service]):
		# default: do bar as well when no specific flag given
		_install_bar()
	if args.service or args.enable_service:
		_install_systemd(enable=args.enable_service)
	# theme sync now (Q7 live)
	try:
		from .theme_adapter import apply
		apply()
	except Exception:
		pass
	print("omarchy camfx install done")
	# persist install marker (JSON per Q19)
	try:
		marker = Path.home() / ".local/state/camfx/install.json"
		marker.parent.mkdir(parents=True, exist_ok=True)
		marker.write_text(json.dumps({"version": "0.2.0", "installed_at": __import__("time").time()}), encoding="utf-8")
	except Exception:
		pass
	return 0


def cmd_uninstall(args: argparse.Namespace) -> int:
	paths = [
		Path.home() / ".config/omarchy/hooks/theme-set.d/50-camfx.sh",
		Path.home() / ".config/omarchy/hooks/post-boot.d/50-camfx.sh",
		Path.home() / ".config/hypr/bindings/camfx.lua",
		Path.home() / ".config/omarchy/plugins/camfx.camfx",
	]
	for p in paths:
		if p.exists():
			try:
				import shutil as sh
				if p.is_dir():
					sh.rmtree(p)
				else:
					p.unlink()
				print(f"Removed {p}")
			except Exception as e:
				print(f"Failed to remove {p}: {e}", file=sys.stderr)
	print("omarchy camfx uninstall done (shell.json layout left intact — use --keep-layout=false to prune)")
	return 0


def build_parser() -> argparse.ArgumentParser:
	p = argparse.ArgumentParser(prog="omarchy-camfx", description="camfx Omarchy integration (plugin registry lane, v0.4.0)")
	sub = p.add_subparsers(dest="cmd", required=True)

	# status
	ps = sub.add_parser("status", help="Aggregated status (for bar widget)")
	ps.add_argument("--json", action="store_true", help="JSON output")
	ps.add_argument("--waybar-json", action="store_true", help="Waybar legacy alias")
	ps.set_defaults(func=cmd_status)

	# toggle
	pt = sub.add_parser("toggle", help="Toggle camera on/off")
	pt.add_argument("--on", action="store_true", help="Force on")
	pt.add_argument("--off", action="store_true", help="Force off")
	pt.add_argument("--quiet", action="store_true", help="Suppress notification")
	pt.set_defaults(func=cmd_toggle)

	# effect
	pe = sub.add_parser("effect", help="Effect controls")
	esub = pe.add_subparsers(dest="ecmd", required=True)
	pet = esub.add_parser("toggle", help="Toggle an effect (add if missing, remove if present)")
	pet.add_argument("key", choices=["blur", "replace", "brightness", "beautify", "autoframe", "gaze-correct"])
	pet.add_argument("--image", help="Path for replace")
	pet.add_argument("--strength", type=int)
	pet.add_argument("--brightness", type=int)
	pet.add_argument("--contrast", type=float)
	pet.add_argument("--quiet", action="store_true")
	pet.set_defaults(func=cmd_effect_toggle)

	# cycle
	pc = sub.add_parser("cycle", help="Cycle effects ring (bar middle-click)")
	pc.add_argument("--prev", action="store_true", help="Previous instead of next")
	pc.add_argument("--quiet", action="store_true")
	pc.set_defaults(func=cmd_cycle)

	# theme-sync
	pts = sub.add_parser("theme-sync", help="Regenerate GTK CSS from Omarchy theme")
	pts.add_argument("--theme-name", default=None)
	pts.set_defaults(func=cmd_theme_sync)

	# doctor
	pd = sub.add_parser("doctor", help="Check prerequisites")
	pd.add_argument("--json", action="store_true")
	pd.set_defaults(func=cmd_doctor)

	# gui
	pg = sub.add_parser("gui", help="Launch camfx GUI via uwsm-app if present")
	pg.set_defaults(func=cmd_gui)

	# config
	pcfg = sub.add_parser("config", help="Human settings (TOML) — get/set")
	pcfg.add_argument("action", choices=["get", "set"])
	pcfg.add_argument("key", nargs="?", help="Dotted key e.g. notifications.enabled")
	pcfg.add_argument("value", nargs="?", help="Value for set")
	pcfg.add_argument("--json", action="store_true")
	pcfg.set_defaults(func=cmd_config)

	# install
	pi = sub.add_parser("install", help="Install hooks/plugins/bindings for Omarchy")
	pi.add_argument("--bindings", action="store_true", help="Install Hyprland bindings")
	pi.add_argument("--bar", action="store_true", help="Install bar widget")
	pi.add_argument("--service", action="store_true", help="Install systemd user unit")
	pi.add_argument("--enable-service", action="store_true", help="Also enable --now")
	pi.add_argument("--persistent", action="store_true", help="Write /etc/modprobe.d/camfx.conf (needs sudo)")
	pi.add_argument("--force", action="store_true", help="Overwrite occupied bindings")
	pi.add_argument("--quiet", action="store_true")
	pi.set_defaults(func=cmd_install)

	# uninstall
	pu = sub.add_parser("uninstall", help="Remove integration files")
	pu.set_defaults(func=cmd_uninstall)

	# reload alias
	pr = sub.add_parser("reload", help="Alias for theme-sync")
	pr.add_argument("--theme-name", default=None)
	pr.set_defaults(func=cmd_theme_sync)

	return p


def main(argv: list[str] | None = None) -> int:
	parser = build_parser()
	args = parser.parse_args(argv)
	return args.func(args)


if __name__ == "__main__":
	sys.exit(main())
