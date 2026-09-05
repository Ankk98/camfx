# camfx on Omarchy

> Omarchy-native install via the **plugin registry** (`omarchy plugin catalog`) — no AUR (Q1), no Waybar (Quattro is Quickshell), keyboard-first (Q15), live-reload theming no restart (Q7), configurable notifications (Q8), `video_nr=-1` auto (Q3), always-show widget (Q26).

## Install

On your Omarchy VM (Q14):

```bash
# Core + Omarchy plugin (pip). On Omarchy, Python 3.11+ has tomllib so no backport.
pip install -e ".[omarchy]"          # or pip install camfx[omarchy]
# Or: pip install -e . && pip install omarchy  # same wheel

# System deps (once)
sudo pacman -S --needed v4l2loopback-dkms linux-headers dkms ffmpeg v4l-utils gtk4 python-gobject python-dbus

# Load v4l2loopback (kernel-picked node, card_label=camfx, exclusive_caps=1 — see §7.6 video_nr=-1 table)
sudo modprobe v4l2loopback exclusive_caps=1 card_label="camfx" video_nr=-1
v4l2-ctl --list-devices  # verify camfx appears

# Install Omarchy integration (idempotent, never overwrites occupied bindings without --force, Q20)
omarchy camfx install --bindings --bar
# or: python -m camfx_omarchy.cli install --bindings --bar

# Verify
omarchy plugin catalog | jq -e '.[] | select(.id=="camfx.camfx")'
omarchy camfx status --json | jq .
omarchy camfx doctor --json | jq .
hyprctl configerrors  # should be empty
omarchy theme set "Tokyo Night"  # should rewrite ~/.config/camfx/gtk.css and live-reload any open camfx gui (Q7)
```

For a persistent modprobe across reboots (opt-in):

```bash
omarchy camfx install --persistent   # writes /etc/modprobe.d/camfx.conf  options v4l2loopback exclusive_caps=1 card_label="camfx" video_nr=-1
# To also enable the daemon at boot (Q11 default is manual):
omarchy camfx install --enable-service  # systemctl --user enable --now camfx
```

## Use

### Bar widget `camfx.camfx` — `right` after `omarchy.audio` (Q17)

The rich widget shows `󰻄` off / `󰻂` on / `󰻃` count>1 + badge count (commit 2). It is **always shown** dimmed when daemon off (Q26) so you can one-click start.

- Left click: `omarchy camfx toggle` (on/off, `notify -u low` Q18)
- Middle click: `omarchy camfx cycle` (ring `blur → replace → brightness → beautify → autoframe → gaze-correct → clear`, keyboard-driven)
- Right click: `omarchy-camfx gui` (via `uwsm-app -- camfx gui`, Q21)

Improve over commits: badge → popover (`SUPER ALT+G`) with toggles+sliders (Q23 both) → portal file picker for `replace` background (Q24).

Enable/move:

```bash
omarchy plugin enable camfx.camfx --after omarchy.audio
omarchy bar move camfx.camfx --section right --after omarchy.audio  # explicit
omarchy-shell shell rescanPlugins
```

### Keyboard (Hyprland, Q15/Q20)

Only installed if the keys are free; if occupied the installer **skips with `notify-send -u normal`** and prints `manual intervention needed`.

- `SUPER ALT+C` — toggle camera
- `SUPER ALT+SHIFT+C` — GUI
- `SUPER ALT+B` — blur toggle
- `SUPER ALT+R` — replace toggle
- `SUPER ALT+G` — effects popover / cycle (commit 3)

If skipped, free the binding or force: `omarchy camfx install --bindings --force`.

### Theme (Q7 live-reload, Q19 TOML/JSON)

`~/.local/state/omarchy/current/theme/colors.toml` → `~/.config/camfx/gtk.css` via `camfx_omarchy.theme_adapter` (`python -m camfx_omarchy.theme_adapter --theme-name foo`). The hook `~/.config/omarchy/hooks/theme-set.d/50-camfx.sh` does this on every `omarchy theme set`; any open `camfx gui` hot-swaps via `Gtk.CssProvider` + `Gio.FileMonitor` — **no restart**.

Human settings: `~/.config/camfx/config.toml` (TOML, Q19)

```toml
[notifications]
enabled = true
level = "low"          # low|normal|critical
on_toggle = true
on_effect = true
```

Machine state: `~/.local/state/camfx/state.json` (JSON, Q22 persist) and `~/.local/state/camfx/install.json`.

```bash
omarchy camfx config get notifications.enabled
omarchy camfx config set notifications.enabled false  # or --quiet per-command
omarchy camfx theme-sync --theme-name "Tokyo Night"
```

### Video background vs theme background (Q16)

`camfx replace --image /path/to.jpg` (video) and Omarchy theme `backgrounds/` are independent — the picker starts at the last camfx image, not the theme's `backgrounds/`. No hidden copy.

### D-Bus / CLI

```bash
camfx start --dbus --name camfx --input 0 --fps 30
camfx status --json                 # {available,active,count,label,effects,camera}
camfx camera-status --json          # {active,available}
camfx get-effects --json            # [{type,class,config}]
camfx doctor --json
omarchy camfx status --json         # alias for bar widget (Q6 a CLI helper)
omarchy camfx toggle --on --quiet
omarchy camfx effect toggle blur --strength 25
```

## Troubleshooting

- `omarchy plugin catalog | jq '.[] | select(.id=="camfx.camfx")'` missing → `omarchy camfx install --bar && omarchy-shell shell rescanPlugins`
- `hyprctl configerrors` after bindings → `grep -n camfx ~/.config/hypr/bindings.lua` and remove duplicates
- `v4l2loopback` not loaded → `sudo modprobe v4l2loopback exclusive_caps=1 card_label="camfx" video_nr=-1` and `omarchy camfx doctor --json | jq .v4l2loopback`
- `notify-send` spam → `omarchy camfx config set notifications.enabled false` or `omarchy camfx toggle --quiet`
- Theme not syncing → `python -m camfx_omarchy.theme_adapter && cat ~/.config/camfx/gtk.css` — the hook logs to `omarchy hook` tracer; ensure `~/.config/camfx/gtk.css` exists

## Distribution (Q13)

This branch publishes to the **Omarchy plugins registry** (`~/.config/omarchy/plugins/camfx.camfx/` + `omarchy plugin catalog`) — not pacman/AUR. The `packaging/omarchy/PKGBUILD` is for local `makepkg -si` on your VM only.

Release: `git tag omarchy-v0.2.0 && gh release upload camfx-omarchy-registry.zip` containing `camfx.camfx/` + `hooks/` + `bindings/` + `INSTALL.md`.

## Publishability

- Core stays `pip install camfx` (OS-neutral); Omarchy adds `pip install camfx[omarchy]` (extra is pure-python).
- No file under `~/.config` is overwritten without `CAMFX_STATE_FILE` guard or `--force`; `omarchy update` preserves hooks via `hooks/*.d` ordering.
- Contract tests: `test/shell.d/fixtures/bar-widget-contract/` etc. stay green — no new `default/themed/*.tpl` in MVP, so `theme-staging-test` trivially passes.
