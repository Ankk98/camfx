# camfx × Omarchy Integration Plan

**Version:** 0.4.0 — decisions locked (Q1–Q26, build-ready)  
**Date:** 2026-04-28 (v0.1 draft) / 2026-05-13 (v0.2) / 2026-05-13 (v0.3 Q15–Q21) / 2026-05-13 (v0.4 Q22–Q26)  
**Branch surveyed:** `basecamp/omarchy#quattro` (≈ `v4`, commit `6,347` on `quattro`) — current rolling. Also cross-checked Omarchy 3 manual (`learn.omacom.io`) for Waybar-era assumptions.  
**camfx baseline:** `v0.2.0a1` (`camfx/core.py:18`, `camfx/output_v4l2_ffmpeg.py:106`, `camfx/dbus_control.py:17`, `packaging/fedora/camfx.spec:1`)  
**Decisions incorporated:** Q1–Q26 answers 2026-05-13 (rich bar widget iterative, plugin registry, live-reload theming, configurable notifications, keyboard-first, TOML/JSON split, no-overwrite bindings, persist last chain, toggle+slider popover, portal picker, VM test rig)

---

## 1. Executive Summary

This document is a build-ready plan to make `camfx` feel native on **Omarchy** (Arch + Hyprland + Quickshell `omarchy-shell` + `~/.config/omarchy` hooks/theming) while keeping 100% compatibility with other Linux distros (Fedora, Ubuntu, Arch-vanilla).

**Recommended approach (LOCKED per Q1–Q14):** *Omarchy-native plugin layer, no AUR/PipeWire scope* — no fork, no `if omarchy` branches inside core. Core stays OS-agnostic (`V4L2` + `FFmpeg` + `OpenCV` + `MediaPipe` + `D-Bus`). An optional plugin `camfx` (PyPI `camfx[omarchy]`) + **Quickshell plugin `camfx.camfx` published to Omarchy's plugin registry** (`omarchy plugin catalog` / `~/.config/omarchy/plugins/`) provides: the richer full bar widget (iterative, B2 — Q2), `omarchy camfx` CLI shims (`docs/cli-router.md`), theme hook with **live-reload** (no restart — Q7), configurable notifications (Q8), Hyprland bindings, Walker `.desktop`, and systemd user unit. When absent, `camfx` behaves exactly as today on Fedora/Ubuntu.

Distribution is **Omarchy plugins registry** (Q13), not AUR (`Q1: skip AUR`). Existing feature set only (Q12: no PipeWire rewrite in this branch). Test rig is the author's Omarchy VM (Q14).

---

## 2. Goals / Non-Goals

### Goals
- `camfx` runs on Omarchy without manual `modprobe`/`.venv` rituals.
- **Topbar/panel:** Quickshell `omarchy-shell` bar shows live `camfx` status (off / on / which effects, effect count) as a **richer full bar widget `camfx.camfx`** (Q2 — shipped iterative: v1 minimal widget with toggle + badge, later commits add popover/effect-cycle) — not just an indicator row clone. Feels identical to native widgets (`shell/plugins/bar/widgets/`).
- **Themes:** Follows Omarchy theme switch (`omarchy theme set …` → `bin/omarchy-theme-set:29`, `config/omarchy/shell.json`, `default/themed/*.tpl`, `~/.config/omarchy/current/theme`). GTK GUI and icon tint track `colors.toml` (`background`/`foreground`/`accent`/`muted`) via **live-reload** `Gtk.CssProvider` (Q7 — no restart required), not a hardcoded palette.
- **Hooks/automation:** Plays nicely with `omarchy hook` (`~/.config/omarchy/hooks/theme-set.d/`, `post-boot.d/`, `post-update.d/`) for theme-sync and autostart, without overwriting user files.
- **Settings & Hyprland:** Adds opt-in keybindings under `~/.config/hypr/bindings.lua` pattern (`hyprland.md` skill), window rules, and a `Setup > Camera FX` path — survives `omarchy update`.
- **Panels/menus:** Appears in Walker app launcher (`*.desktop`) and bar widget; deeper `omarchy-menu` branch deferred to follow-up (Q10: default — bar + desktop only).
- **Modular & publishable:** Published to **Omarchy plugins registry** (Q13 — `omarchy plugin catalog` / `shell/plugins`), with fallback that omits the plugin cleanly on non-Omarchy systems. PyPI `camfx[omarchy]` extra (Q5: default). **No PipeWire rewrite** in this branch (Q12).

### Non-Goals (expanded per Q12)
- Replacing `v4l2loopback` with PipeWire for this milestone (tracked separately in `docs/kernel-module-alternatives.md` — noted as future work). Q12 explicitly: *no new output-backend features in this branch; integrate existing V4L2 tool as-is*.
- Adding AUR packaging in this branch (Q1: skipped — Omarchy plugin registry is the sole publish lane).
- Forking or vendoring Omarchy defaults under `~/.local/share/omarchy` at user creation time (that is `omarchy-settings` / `/etc/skel` territory — see `docs/file-layout.md: Seed/Finalize/Resync`).
- Reimplementing `omarchy-shell` itself; we consume its plugin APIs.

---

## 3. Current Architectures

### 3.1 camfx (today)

```
camfx/
  cli.py               # click.Group CamfxCLI, commands: start, preview-camera/virtual, list-devices,
                       #   effects, set-effect/add-effect/remove-effect/get-effects, camera-start/stop/status, models-download, gui
  core.py              # VideoEnhancer — capture (cv2.VideoCapture), EffectController chain, V4L2OutputFFmpeg, D-Bus service
  control.py           # EffectChain + EffectController (thread-safe, add/remove/clear/update_param)
  effects.py           # BackgroundBlur, BackgroundReplace, BrightnessAdjustment, FaceBeautification, AutoFraming, EyeGazeCorrection
  output_v4l2_ffmpeg.py# V4L2OutputFFmpeg — subprocess ffmpeg bgr24 → v4l2 yuyv422, _resolve_v4l2_device() via sysfs + v4l2-ctl
  dbus_control.py      # org.camfx.Control1 /org/camfx/Control1 — methods + signals (SetEffect/AddEffect/RemoveEffect*/ClearChain/GetCurrentEffects/
                       #   UpdateEffectParameter, StartCamera/StopCamera/GetCameraState, ListCameraSources/GetCameraModes/GetCameraConfig/ApplyCameraConfig)
  camera_devices.py    # list_camera_devices(), probe_camera_modes()
  gui/                 # GTK4 + PyGObject (gi.require_version Gtk 4.0) — main_window.py, dbus_client.py, preview_widget.py, etc.
  resources/           # default_background.jpg
packaging/fedora/      # camfx.spec, camfx.service (systemd user unit), camfx.desktop
setup.py               # extras_require gui/dbus, entry console_scripts camfx=camfx.cli:cli
```

**Key OS-coupled points:**
- `output_v4l2_ffmpeg.py:33` `_resolve_v4l2_device(device, card_label)` assumes `/sys/class/video4linux/*/name` + `v4l2-ctl` + `/dev/videoX`.
- `V4L2OutputFFmpeg:134` `ffmpeg` on `PATH`; no PipeWire fallback.
- `core.py:90` `CamfxControlService` bound to *session* D-Bus — works under Hyprland/UWSM, but no `omarchy` awareness.
- `packaging/fedora/*`: `dnf`-style deps (`akmod-v4l2loopback`), GNOME `xdg-desktop-portal-gnome` restart hint in README — not `omarchy` (`pacman` `v4l2loopback-dkms`, `xdg-desktop-portal-hyprland`, UWSM `uwsm-app --` wrapping per `bin/omarchy-restart-waybar`).
- GUI is plain GTK4; no consumption of `~/.config/omarchy/current/theme/colors.toml` or `shell.toml`.

On non-Omarchy, nothing here is broken — that is the baseline to preserve.

### 3.2 Omarchy (quattro, 2026-03 surveyed)

Source: clone at `/tmp/opencode/omarchy` branch `quattro` + `docs/*.md` + `default/agents/skills/omarchy/*.md`.

```
omarchy/
  bin/omarchy-*            # 449 binaries, routed by bin/omarchy router (docs/cli-router.md) — longest-prefix exec, metadata # omarchy:*
  config/                  # seeds → /etc/skel/.config + /usr/share/omarchy/config (resync source) — hypr/*.lua, omarchy/shell.json, etc.
  default/                 # → /usr/share/omarchy/default — hypr/*.lua, bash/*, themed/*.tpl, shell/ (Quickshell), etc.
  config/omarchy/hooks/    # battery-low.d, font-set.d, post-boot.d, post-update.d, theme-set.d (+ *.sample)
  config/omarchy/shell.json# bar {position, transparent, centerAnchor, layout{left,center,right}}, plugins[], idle{}
  themes/<name>/           # colors.toml + backgrounds/ + icons.theme + shell.toml/.lock.toml overrides etc.
  default/themed/*.tpl     # alacritty.toml.tpl, shell.toml.tpl, hyprland.lua.tpl, etc. — rendered on omarchy-theme-set
  shell/                   # Quickshell omarchy-shell — shell.qml, Ui/, Commons/, plugins/{bar,menu,lock,panel,services,…}
  shell/plugins/bar/       # Bar.qml + BarModel.js, widgets/{ActiveWindow,Indicators,Tray,Workspaces,…}, indicators/{Dnd,NightLight,ScreenRecording,…}
  shell/plugins/panels/    # clock, weather, bluetooth, network, audio, power, etc.
  install/ + migrations/   # provisioning & per-user migrations
  docs/file-layout.md      # repo→installed map, Seed/Finalize/Resync model
```

**Integration seams relevant here:**

- **Bar:** Not Waybar anymore (Waybar was Omarchy ≤3; manual still mentions it). Quattro's bar lives in `shell/plugins/bar/Bar.qml` + `shell/plugins/bar/widgets/Indicators.qml` hosting `shell/plugins/bar/indicators/*.qml` via `BarIndicator` (`shell/Ui/BarIndicator.qml`). Add indicators by adding a `.qml` file + manifest entry in `Indicators.manifest.json` `options` (see §7.2).
- **Widget layout:** `omarchy bar {move,put,set}` (`bin/omarchy-bar:1`) + `~/.config/omarchy/shell.json` hot-reload + `omarchy plugin {clone,enable,disable}` (`bin/omarchy-plugin-clone:1`). Docs at `default/agents/skills/omarchy/plugins.md`.
- **Themes:** `bin/omarchy-theme-set:29` stages `next-theme` → `current/theme`, overlays `~/.config/omarchy/themes/<slug>`, derives `colors.toml` if missing, runs `omarchy-theme-set-templates` (renders `default/themed/*.tpl` over `colors.toml`), flips `~/.local/state/omarchy/current/{theme,theme.name,background}`, `shell_ipc shell applyTheme`, then parallel retint (`omarchy-restart-{terminal,hyprctl,btop,…}`, `omarchy-theme-set-{foot,browser,vscode,…}`) and `omarchy-hook theme-set $THEME`.
- **Hooks:** `bin/omarchy-hook:1` executes `~/.config/omarchy/hooks/<name>` and `~/.config/omarchy/hooks/<name>.d/*`. Desired events: `theme-set`, `post-boot`, `post-update`.
- **Hyprland:** Lua config `config/hypr/hyprland.lua:1` → `require("default.hypr.omarchy")` then `require("hypr.{monitors,input,bindings,looknfeel,autostart})` + toggles. Users edit `~/.config/hypr/bindings.lua` (`default/agents/skills/omarchy/hyprland.md`) with `o.bind()` / `hl.unbind()`.
- **Apps/menus:** `bin/omarchy-menu` is Walker dmenu; panels `shell/plugins/panels/*.qml`. Walker discovers `/usr/share/applications/*.desktop` and `/etc/skel/.local/share/applications/`.
- **Distribution:** Two Arch packages built from `omarchy` repo but shipped via `omarchy-pkgs/PKGBUILDs`: `omarchy` (bin/install/migrations/themes/shell) and `omarchy-settings` (pre-useradd seeds, `/usr/share/omarchy/config` resync source). File-layout, env bootstrap (`default/bash/env-bootstrap` → `OMARCHY_PATH`), `etc-overrides` logic in `docs/file-layout.md`. Third parties typically ship via AUR and are enabled with `pacman -S` / `yay -S`.

---

## 4. Design Principles (modularity)

1. **Core stays clean.** `camfx` core (`core.py`, `effects.py`, `output_v4l2_ffmpeg.py`, `control.py`) gains *zero* `if omarchy:` branches. Runtime feature detection only (`try: import camfx_omarchy` or `OMARCHY_PATH` env, `shutil.which("omarchy")`).
2. **Adapter/plugin not fork.** Omarchy support lives in `camfx_omarchy/` (Python `camfx[omarchy]` extra) + `shell/plugins/camfx.camfx/` (QML bar widget) + `bin/omarchy-camfx-*` shims. Install on Omarchy via `omarchy plugin` registry; omit elsewhere — no bloat on Fedora/Ubuntu.
3. **User-owned files win.** Anything under `~/.config/` (`hypr/bindings.lua`, `omarchy/shell.json`, `omarchy/hooks/*.d`, `omarchy/plugins/*`) is additive, never destructive, and survives `omarchy update` / migrations. Resync (`omarchy refresh …`) remains safe.
4. **No private API copying.** Use public contracts: `omarchy-hook`, `omarchy plugin`, `omarchy bar`, `omarchy theme`, D-Bus `org.camfx.Control1`, `colors.toml`/`shell.toml` keys. Pin against `shell` contract tests (`test/shell.d/fixtures/**`).
5. **Publishable to Omarchy plugin registry (Q13).** Primary lane is `omarchy plugin catalog` — a self-contained plugin under `~/.config/omarchy/plugins/` (and optionally `/usr/share/omarchy/shell/plugins/` if later merged upstream). AUR lane is explicitly out of scope for this branch (Q1). Upstream PR to `basecamp/omarchy` remains a *possible* Tier-2 after registry validation.
6. **Live-reload theming or nothing (Q7).** Theme changes must reflect in `camfx gui` without restart: `Gtk.CssProvider` hot-swap + QML `Color`/`Style` bindings. Notifications are on but configurable (Q8).

---

## 5. Approach Comparison

### 5.1 Option A — Direct Patch to `basecamp/omarchy` (monolithic PR)

Add `camfx` binaries, systemd unit, theme tpl, bar indicator, and theme-set steps straight into `omarchy` repo.

- Pros: Minimal install friction once merged; runs at first boot for new users.
- Cons: Requires upstream approval; tight coupling makes `camfx` changes need `omarchy` release; not usable on Fedora/Ubuntu; conflicts with `omarchy-settings` seed policy (`/etc/skel` only at user creation).
- Verdict: **Do not start here.** Offer as Tier-2 follow-up after Tier-1 plugin proves demand.

### 5.2 Option B — Omarchy Plugin Registry (`camfx.camfx` shell plugin, registry-native, SELECTED)

A plugin published to Omarchy's plugin registry (discovered via `omarchy plugin catalog` over `$OMARCHY_PATH/shell/plugins` + `~/.config/omarchy/plugins/`, `shell/plugins/bar/widgets/Indicators.qml` → `BarIndicator`). Ships as `camfx_omarchy` Python package (`pip install camfx[omarchy]` — Q5 default) plus QML widget `camfx.camfx` (full bar widget, rich — Q2) plus `bin/omarchy-camfx-*` shims for `docs/cli-router.md` routing. No AUR (`Q1: skip AUR`). Registered via `omarchy plugin enable camfx.camfx` / `omarchy hook install` against the *user* layer (`~/.config/omarchy/**`). Core `camfx` stays importable and distro-neutral.

- Pros: No upstream gate, modular, distro-neutral core, easy to version separately, iterative bar widget (Q2 — start small, improve over commits), live-reload theming (Q7), aligns with `Q13: plugins registry` publish lane; trivial to graduate to upstream `basecamp/omarchy` later.
- Cons: One extra install step; needs an idempotent installer (`omarchy camfx install`) for hooks/plugins/bindings.
- Verdict: **SELECTED — per Q1/Q2/Q5/Q13. This plan's §§6–10 assume this.**

### 5.3 Option C — Inline Detection Inside `camfx`

Sprinkle `if os.environ.get("OMARCHY_PATH")` checks inside `core.py`/`cli.py`/`output_v4l2_ffmpeg.py` to auto-switch behavior on Omarchy.

- Pros: Zero extra package.
- Cons: Couples core to a single distro's internals; fragile as `omarchy-shell`/`quattro` evolves; violates §4/#1.
- Verdict: **Rejected.**

### 5.4 Option D — Dedicated `camfx` Bar + Daemon UI (ignores shell design)

Ship a custom floating bar/overlay or Electron panel instead of a Quickshell plugin.

- Pros: Full design freedom.
- Cons: Duplicates `omarchy-shell`'s Quickshell singleton; breaks theming/layout hot-reload; heavier; not what users expect from Omarchy's palette.
- Verdict: **Rejected for Omarchy; out of scope.**

### Decision Table

| Axis | A (monolithic PR) | **B (Omarchy plugin, SELECTED)** | C (inline if) | D (own bar) |
|---|---|---|---|---|
| Works off-Omarchy | No | **Yes (omit plugin)** | Yes (fragile) | Yes |
| Needs upstream merge | Yes | **No (registry-native)** | No | No |
| Publish lane (Q1/Q13) | pacman | **plugins registry ✓** | none | none |
| Bar widget richness (Q2) | Full | **Full iterative B2 ✓** | N/A | Own |
| Theme live-reload (Q7) | Maybe | **Yes ✓** | No | No |
| Uses public hook/bar contracts | Yes | **Yes** | Partially | No |
| Maintains user files safely | Yes | **Yes** | No | N/A |
| Upgradable with `omarchy update` | Yes | **Yes (post-update hook)** | N/A | N/A |
| Risk to omarchy-shell updates | Medium | **Low** | High | High |

Recorded answers: Q1 skip AUR, Q2 richer full bar widget iterative, Q5 default PyPI, Q13 plugins registry.

---

## 6. Recommended Architecture (Plugin Layer)

```
camfx (core, unmodified except tiny adapter hook — live-reload GTK CSS opt-in)
  │  python -m camfx  / camfx gui  / camfx start --dbus
  │  D-Bus org.camfx.Control1 (control.py / dbus_control.py)
  │
  ├─ (optional) camfx_omarchy/  — Python package installed as camfx[omarchy] (Q5 default, no AUR per Q1)
  │     omarchy_detection.py     # OMARCHY_PATH / which omarchy / ~/.config/omarchy existence
  │     theme_adapter.py         # read ~/.local/state/omarchy/current/theme/colors.toml + shell.toml → GTK css live-reload (Q7)
  │     config.py                # ~/.config/camfx/config.toml {notifications: {enabled:bool, level:string}} (Q8 configurable)
  │     hooks/                   # executables installed to ~/.config/omarchy/hooks/*.d/
  │     shell_plugin/            # QML plugin source — camfx.camfx full bar widget (Q2, iterative)
  │     bindings/                # Hyprland snippet camfx.lua
  │     bin_src/omarchy-camfx-*  # CLI shims routed by omarchy's CLI router (Q6: CLI-JSON helper, upgradeable to direct D-Bus)
  │     systemd/ camfx.service   # user unit variant (WantedBy=graphical-session.target, uwsm-aware)
  │     templates/camfx.css.tpl  # optional default/themed override for GTK accent
  │
  └─ omarchy-shell (Quickshell) — loads plugin via omarchy plugin catalog:
        ~/.config/omarchy/plugins/camfx.camfx/  (or /usr/share/omarchy/shell/plugins/ if later upstreamed)
        Bar.qml → Camfx.qml (BarWidget, not indicator-row)  [Q2 rich widget, iterative]
                ↑ via omarchy-camfx status --json Process/StdioCollector (Q6 a, improvable)
```

**Runtime wiring (detailed in §7, post-Q6/Q7/Q8 decisions):**

1. Installed plugin's `Camfx.qml` (full bar widget, Q2) talks to `org.camfx.Control1` via **`omarchy-camfx status --json` helper (Q6: option a — simple, improvable later to direct QML D-Bus)**; direct `dbus-python` in QML deferred. Bar re-queries on `onPressed`/`onBarChanged`/`indicatorHost.refreshRequested` — no tight polling.
2. `omarchy camfx toggle` etc. call D-Bus `StartCamera/StopCamera/SetEffect/...`, emit a **configurable notification** if `~/.config/camfx/config.toml [notifications].enabled==true` (Q8), and poke bar refresh.
3. Theme switches: `bin/omarchy-theme-set:…` fires `theme-set` hook; `camfx` hook at `~/.config/omarchy/hooks/theme-set.d/50-camfx.sh` regenerates `~/.config/camfx/gtk.css` from `colors.toml` and **live-reloads** any running `camfx gui` via `Gtk.CssProvider` hot-swap (Q7 — no restart required).
4. Hyprland bindings: `~/.config/hypr/bindings.lua` includes `require("hypr.bindings.camfx")` or the installer appends a block that `o.bind()`s keys (with prior `hl.unbind` per `hyprland.md` protocol).

---

## 7. Integration Points (what "native" means)

### 7.1 Detection & Identity

```python
# camfx_omarchy/omarchy_detection.py
from pathlib import Path
import os, shutil

def is_omarchy() -> bool:
    return bool(
        os.environ.get("OMARCHY_PATH")
        or (Path.home() / ".local/share/omarchy").exists()
        or shutil.which("omarchy")  # bin/omarchy router present
    )

def omarchy_path() -> Path:
    raw = os.environ.get("OMARCHY_PATH") or "/usr/share/omarchy"
    return Path(raw)

def current_theme_dir() -> Path:
    return Path.home() / ".local/state/omarchy/current/theme"

def shell_config_path() -> Path:
    return Path.home() / ".config/omarchy/shell.json"
```

- Spec: respect existing env bootstrap (`docs/file-layout.md: Env bootstrap`) — `OMARCHY_PATH` is canonical; `/tmp/opencode/omarchy/default/bash/env-bootstrap` style detection.
- No auto-enable that mutates user state on import; detection is query-only. Enabling is an explicit `omarchy-camfx install` / installer script.

### 7.2 Bar / Topbar (Quickshell, the actual Omarchy 4 surface)

**Context:** Omarchy ≤3 used Waybar (`config/waybar/config.jsonc` style: `custom/camfx` with `exec`/`signal`/CSS `@import "../omarchy/current/theme/waybar.css"`). Quattro replaced it with a Quickshell singleton (`shell/plugins/bar/Bar.qml`). Both patterns are documented below; the active target is **Quickshell**.

#### Quickshell target (quattro, primary)

**Pattern to copy:** `shell/plugins/bar/indicators/ScreenRecording.qml` (properties `recording`, `active`/`inactiveText`, `refresh()` probing `pgrep`, `onPressed` running `omarchy-capture-screenrecording …`) and `shell/Ui/BarIndicator.qml` (`extractData`, `syncIndicatorOpacity`, `revealInactiveIndicators`). `shell/plugins/bar/widgets/Indicators.qml` hosts them.

**Proposed plugin (LOCKED per Q2): richer full bar widget `camfx.camfx`, iterative**

Per Q2 the plugin is a **standalone `bar-widget` `camfx.camfx`** (not an indicator-row append). Start small and improve over commits. The smaller `CamfxIndicator` inside `Indicators` is no longer the target; keep its pattern as reference only.

**Canonical new files (installed to Omarchy plugin registry — Q13, §10):**

```
# B2 (SELECTED per Q2): standalone full bar widget outside Indicators — iterative
~/.config/omarchy/plugins/camfx.camfx/
  manifest.json   # id=camfx.camfx, kinds=[bar-widget], entryPoints.barWidget=Camfx.qml
  Camfx.qml       # v1 minimal: icon + badge + toggle; later commits add popover/effect-cycle/replace picker
  CamfxModel.js   # optional helper (icon mapping, label formatting) — parity with Microphone.qml TrayModel.js

# (Reference only, not shipped) Indicator-row path — documents why not chosen:
# shell/plugins/bar/indicators/CamfxIndicator.qml + Indicators.manifest.json options++ — would have been B1.
```

If later a registry-priced upstream merge is pursued, the same `camfx.camfx/manifest.json` + `Camfx.qml` moves to `/usr/share/omarchy/shell/plugins/camfx.camfx/` with no behavioural change. For richer effect-cycling popovers, add a second widget `camfx.effects` or extend `Camfx.qml` with a `Loader` panel — iterative, no breaking `shell.json` layout.

**v1 `Camfx.qml` bar widget contract (modeled on `Microphone.qml`/`ScreenRecording.qml`, but as `BarWidget`, keyboard-first — Q15 no wheel):**

```qml
import QtQuick
import Quickshell.Io
import qs.Ui

BarWidget {
  id: root
  moduleName: "camfx.camfx"
  property bool camAvailable: false
  property bool camActive: false
  property string effectLabel: ""    // Q9 default: short key, e.g. "blur"
  property int effectCount: 0

  visible: true
  implicitWidth: button.implicitWidth
  implicitHeight: button.implicitHeight

  function refresh(){ if(!statusProc.running) statusProc.running=true }
  onBarChanged: refresh()
  Component.onCompleted: refresh()

  Process {
    id: statusProc
    command: ["bash","-c","omarchy-camfx status --json 2>/dev/null || echo '{\"available\":false}'"] // Q6 a
    stdout: StdioCollector { waitForEnd:true; onStreamFinished: {
        var raw=String(text||""); var d=(root.extractData?root.extractData(raw):JSON.parse(raw));
        root.camAvailable=!!d.available; root.camActive=!!d.active; root.effectLabel=String(d.label||""); root.effectCount=Number(d.count||0)
    }}
    onExited: function(code){ if(code!==0) root.camAvailable=false }
  }

  BarIconButton {
    id: button
    anchors.fill: parent; bar: root.bar
    text: root.camActive ? (root.effectCount>1 ? "󰻃" : "󰻂") : "󰻄" // Q9 defaults kept
    active: root.camActive
    tooltipText: root.camActive ? ("camfx · "+(root.effectLabel||"on")+"  · Click off · Right GUI · Middle cycle") : (root.camAvailable?"camfx · off  · Click on":"camfx · daemon off  · Click start")
    onPressed: function(ev){
      if(ev===Qt.RightButton){ if(root.bar) root.bar.run("omarchy-camfx gui"); return }
      if(ev===Qt.MiddleButton){ if(root.bar) root.bar.run("omarchy-camfx cycle"); return } // keyboard cycle also exposed via SUPER ALT+B/R etc. (§7.4)
      if(root.camActive){ if(root.bar) root.bar.run("omarchy-camfx toggle --off") } else { if(root.bar) root.bar.run("omarchy-camfx toggle --on") }
    }
    // Q15: Omarchy is keyboard-first — no onWheelMoved handler. Effect cycling is keyboard-driven (SUPER ALT+B/R) and middle-click.
  }

  // Iterative follow-ups (keyboard-first): commit 2 adds badge Text { text: effectCount>1?String(effectCount):"" }
  // commit 3 adds popover Loader (keyboard-navigable) with effect grid (blur/replace/… toggle) — opened via middle-click or SUPER ALT+G.
}
```

- Refresh cadence: event-driven (`onBarChanged` + post-toggle callback + optional `Timer { interval: 4000 }` fallback). Q6 a helper (`omarchy-camfx status --json`) is the stable contract; a later commit can swap to direct QML `DBus` without changing the bar widget API.
- Iterative plan (keyboard-first, Q15): commit 1 = minimal widget (above, click toggle + middle-click cycle). commit 2 = count badge + label. commit 3 = keyboard-navigable popover with effect toggles bound to `SUPER ALT+…` same as bindings — no mouse-wheel affordance.

**Placement & enablement (plugin registry, Q13):** `~/.config/omarchy/plugins/camfx.camfx/` discovered by `omarchy plugin catalog` (`$OMARCHY_PATH/shell/plugins` + `~/.config/omarchy/plugins`), enabled via `omarchy plugin enable camfx.camfx --after omarchy.audio` (and `omarchy bar move …`). QML then self-contains richer controls; layout stored in `~/.config/omarchy/shell.json` → hot-reload. Iteration commits simply overwrite `Camfx.qml` and `omarchy-shell shell rescanPlugins`.

**Canonical manifest (full widget, locked per Q2):**

```jsonc
// ~/.config/omarchy/plugins/camfx.camfx/manifest.json
{
  "schemaVersion": 1,
  "id": "camfx.camfx",
  "name": "Camfx",
  "version": "1.0.0",
  "author": "camfx",
  "description": "Camera effects — virtual camera status and quick toggles (iterative)",
  "kinds": ["bar-widget"],
  "entryPoints": { "barWidget": "Camfx.qml" },
  "barWidget": {
    "displayName": "Camfx",
    "description": "Toggle camera, cycle effects (right-click GUI, middle cycle, wheel cycle)",
    "category": "Media",
    "allowMultiple": false,
    "defaultSection": "right"
  }
}
```

**Legacy Waybar appendix (Omarchy 3 / users still on Waybar):** not shipped in this branch (Q12: existing tool only, and Quattro is Quickshell-native). Kept for reference: would have been `config/waybar/config.jsonc` `custom/camfx` with `exec: "omarchy-camfx status --waybar-json"`, `signal: 10`, `@import "../omarchy/current/theme/waybar.css"`. Out of scope.

### 7.3 Themes

**Goal:** `camfx gui` (GTK4) and tray icon tint follow `omarchy theme set <name>` **with live reload, no restart** (Q7).

- **Source of truth:** `~/.local/state/omarchy/current/theme/colors.toml` (`mode`, `background`/`foreground`, `accent`, `selection`, named colors — spec in `docs/theming.md` and `themes/tokyo-night/colors.toml`). For Quickshell surfaces also `~/.local/state/omarchy/current/theme/shell.toml` (roles, `Style`/`Color` singletons).
- **Rendering:** No new templates under `default/themed/` needed for MVP. GTK CSS is derived at hook time by `camfx_omarchy/theme_adapter.py` reading `colors.toml` (and optionally `shell.toml`) and writing `~/.config/camfx/gtk.css` (GTK CSS) + `~/.config/camfx/icon-theme.css` if using `icons.theme`. CLI `omarchy-camfx theme-sync` does the same on demand. The GUI **hot-swaps** the CSS: `camfx/gui/main_window.py` watches `~/.config/camfx/gtk.css` via `Gio.FileMonitor` or reapplies on `map`/`focus-in`, calling `Gtk.CssProvider.load_from_path()` → `Gtk.StyleContext.add_provider_for_display()` — so the window repaints live.
- **Hook wiring:** Installer runs `omarchy hook install theme-set camfx-theme-sync` which installs `~/.config/omarchy/hooks/theme-set.d/50-camfx.sh` (`THEME_NAME=$1` — contract in `default/agents/skills/omarchy/hooks.md`):

```bash
#!/bin/bash
# Installed by camfx to ~/.config/omarchy/hooks/theme-set.d/50-camfx.sh — Q7 live-reload, Q8 notification-gated
set -euo pipefail
THEME_NAME="${1:-}"
python3 -m camfx_omarchy.theme_adapter --theme-name "$THEME_NAME" 2>/dev/null || true
# Live-reload: signal running GUI via file-monitor; fallback poke (no pkill)
if pgrep -f "camfx gui" >/dev/null 2>&1; then
  # touch triggers Gio.FileMonitor in the GUI; as fallback, send SIGUSR1 or D-Bus ReloadCss if implemented
  touch ~/.config/camfx/gtk.css
fi
```

- **Template-override alternative (future, optional):** Ship a user template `~/.config/omarchy/themed/camfx.css.tpl` consumed by `omarchy-theme-set-templates` to drop `~/.local/state/omarchy/current/theme/camfx.css` directly (pattern: `shell.toml`'s `[lock]` partials `shell.lock.toml`). Requires documenting that `INSTALLED_THEME_DENIED` does not apply (`.css` not code). Deferred to stretch; file-based hook covers all users immediately and does not require upstream deny-list change (`bin/omarchy-theme-set: INSTALLED_THEME_DENIED` + `test/shell.d/theme-staging-test.sh`). Live-reload logic stays regardless.

### 7.4 Hyprland — `Hyprland`/`xdph`/`hyprsunset`, monitors, window rules

Per `default/agents/skills/omarchy/hyprland.md`: never edit `config/hypr/hyprland.lua` directly. Users edit `~/.config/hypr/bindings.lua`, `looknfeel.lua`, etc., which are `require`'d after defaults (`config/hypr/hyprland.lua: require("hypr.bindings")`). Validate with `hyprctl reload && hyprctl configerrors`.

**Proposed:** installer deposits `~/.config/hypr/bindings.d/camfx.lua` or an appended block in `~/.config/hypr/bindings.lua` gated by marker comments (`-- camfx:begin … -- camfx:end`), then sources it via `require("hypr.bindings.camfx")` insertion in user `hyprland.lua` if not present.

**Bindings (keyboard-first, Q15 — `SUPER ALT` modifier to avoid stomping Omarchy's `SUPER` core; Q20: never override, skip + notify if taken):**

```lua
-- ~/.config/hypr/bindings.d/camfx.lua (sourced by ~/.config/hypr/bindings.lua) — Q15/Q20 policy
local o  = require("default.hypr.omarchy")
-- Q20: installer checks `omarchy menu keybindings --print` / ~/.config/hypr/bindings.lua for occupancy BEFORE binding.
-- If SUPER ALT+C is already bound, this file skips that o.bind() and the installer prints:
--   "⚠ SUPER ALT+C already bound to '…' — camfx toggle not installed. Free it or run: omarchy camfx install --bindings --force"
-- No hl.unbind() is emitted in the default path. Only with --force does the installer use hl.unbind().
-- Keyboard-driven effect cycling (no wheel per Q15):
o.bind("SUPER ALT + C", "camfx: toggle camera", { exec = "omarchy-camfx toggle" })
o.bind("SUPER ALT + SHIFT + C", "camfx: GUI", { launch = "camfx gui" })
o.bind("SUPER ALT + B", "camfx: blur toggle", { exec = "omarchy-camfx effect toggle blur" })
o.bind("SUPER ALT + R", "camfx: replace toggle", { exec = "omarchy-camfx effect toggle replace" })
-- Future keyboard cycle (commit 3 popover): SUPER ALT+G to open popover, j/k to navigate effects (Q15 keyboard flow)
```

**Window rules (placed in `~/.config/hypr/looknfeel.lua` or `hyprland.lua` via `o.window` helper):**

```lua
o.window("org.camfx.ControlPanel", { float = true, size = "1200 800", center = true })
```

**Monitors/xdph:** `camfx` virtual camera resolution should not force monitor scale. Expose `camfx camera-status` resolution hint; `monitors.lua` stays user-authored. Optional `xdph.conf` tweak for screen sharing not needed — `camfx` is `/dev/video*` V4L2, not `xdg-desktop-portal-hyprland` stream.

### 7.5 Walker / App Launcher / Menu

- **Walker:** Drop `camfx.desktop` to `/usr/share/applications/camfx.desktop` (or `~/.local/share/applications/camfx.desktop` for user-only) with `Exec=uwsm-app -- camfx gui`, `Icon=camera-web`, `Categories=AudioVideo;Video;`. Walker (`bin/omarchy-launch-walker` style walkers) discovers it immediately; verified pattern in `default/applications/*.desktop` + `config/omarchy` seeding (`docs/file-layout.md`). Also register terminal verbs: `omarchy-camfx gui` callable from walker CLI palette.
- **omarchy-menu (optional deep nesting):** Avoid patching `bin/omarchy-menu` itself (upstream churn). Ship a user extension `~/.config/omarchy/extensions/camfx-menu.sh` that hooks into the menu tree via the documented user hook point (sourcing after `bin/omarchy-menu`'s definitions). Simpler v1: rely on Walker + bar indicator right-click menu, defer deeper `omarchy menu` branch (`Trigger > Capture > Camera FX` with `omarchy capture …`-style flow mirroring `bin/omarchy-capture-screenrecording`) to Tier-2 after user feedback.

### 7.6 System services / Autostart / Idle / Screensaver — with `video_nr` policy (Q3 recommendation)

**Q3 context — kernel-picked vs. pinned `video_nr`:**

| Policy | How | Pros | Cons | When to choose |
|---|---|---|---|---|
| `video_nr=-1` (kernel-picked, **RECOMMENDED default**) | `modprobe v4l2loopback exclusive_caps=1 card_label="camfx" video_nr=-1` + discovery via `output_v4l2_ffmpeg.py:33` `_resolve_v4l2_device(..., card_label)` (sysfs `name` match, then `v4l2-ctl` parse) | Never collides with physical cams (`/dev/video0` is often the real webcam) or with other virtual cams (`OBS`); quatto-plugin pattern mirrors Omarchy's `screenrecording` `v4l2-ctl --list-devices` discovery; survives `OBS virtualcam` already owning `video10` | Node number non-deterministic → must discover by `card_label` every launch (camfx already does); `v4l2loopback` `video_nr` param is array (`video_nr=-1` is scalar form meaning one auto device) | **Default for Omarchy laptops with single hw cam + OBS** |
| `video_nr=42` pinned | `video_nr=42 card_label="camfx"` | Deterministic `/dev/video42` for docs/scripts | Collides if `42` occupied → `modprobe` fails or creates different minor; wastes fixed slot; `OBS` often wants `0,1` | Use only if user explicitly wants a known node for Zoom/Meet config |
| `devices=1 video_nr=10` pinned single | `devices=1 video_nr=10` | Matches old Fedora doc `video_nr=10` | Same collision risk, plus `devices=1` vs `devices=2` mismatch with OBS | Legacy — avoid |
| Persistent `/etc/modprobe.d/v4l2loopback.conf` (`options …`) + `/etc/modules-load.d/v4l2loopback.conf` (`v4l2loopback`) | File: `options v4l2loopback exclusive_caps=1 card_label="camfx" video_nr=-1` | Auto-load on boot without hook | Writes to `/etc` (needs `sudo`, pacman-owned path contention if `omarchy-settings` manages it); less reversible; conflicts if OBS also writes same file with different `card_label` (last writer wins) | Prefer hook for user-only, config file only if user opts into “make persistent” |
| **Recommendation (locked):** **Default install uses transient `modprobe` with `video_nr=-1` + card-label discovery; `post-boot` hook is opt-in and transient as well. Persistent `/etc/modprobe.d` file is offered only via `omarchy camfx install --persistent` flag that appends a drop-in to `/etc/modprobe.d/camfx.conf` (merge-safe) and runs `sudo modprobe`. Installer probes `lsmod | grep v4l2loopback` first and never overwrites an already-loaded module with different `card_label` — it just discovers the existing node.** |

- **Systemd user unit:** `camfx` currently ships `packaging/fedora/camfx.service` (`WantedBy=default.target`). For Omarchy, ship `config/systemd/user/camfx.service` + `default/systemd/user/camfx.service` variant that:
  ```
  [Unit] Description=camfx Virtual Camera — Omarchy
  After=graphical-session.target
  Wants=graphical-session.target
  PartOf=graphical-session.target
  [Service] Type=simple
  ExecStart=/usr/bin/camfx start --dbus --name camfx --input 0 --fps 30
  Restart=on-failure
  RestartSec=5
  ExecReload=/usr/bin/omarchy-camfx reload
  Environment=XDG_CURRENT_DESKTOP=Hyprland
  [Install] WantedBy=graphical-session.target
  ```
  Wrapping via `uwsm-app --` only for GUI launch; daemon itself is headless so plain `camfx start` is fine under `uwsm` session (matches `bin/omarchy-restart-waybar: setsid uwsm-app -- waybar` pattern).
  Enable intentionally **manual by default** per Q11 (`omarchy camfx install` does not `systemctl enable --now` unless `--enable-service`). When enabled, `systemctl --user enable --now camfx` and `post-boot` hook remains transient and checks `lsmod`.
- **Hyprland autostart alternative (user-owned):** `~/.config/hypr/autostart.lua` `exec_once = { "camfx start --dbus" }` — redundant with systemd but offered as fallback for users who prefer Hyprland's barrel. Installer supports either.
- **Idle/screensaver interaction:** `shell/plugins/services/idle` and bar `StayAwake` indicator already exist; `camfx` does not need to inhibit `hypridle`/`hyprlock` itself — camera-off path sends black frames (`core.py:441`); camera-on is inert regarding idle. If future "pause on lock" is desired, add a `~/.config/hypr/hypridle.conf` listener via `hyprlock` socket (deferred).

### 7.7 Audio / Notifications / Clipboard — configurable notifications (Q8, Q18 decision)

- **Audio:** `camfx` is video-only — no `PipeWire` audio graph (`shell/plugins/services/*` patterns not needed). Leave `omarchy.audio` panel alone.
- **Notifications (Q8: should have, configurable — Q18 decision: toggle low / effect normal / daemon critical, throttled):** `omarchy-camfx toggle` / `effect toggle` emit via `notify-send` / `shell/plugins/notifications` **only if** `~/.config/camfx/config.toml [notifications] enabled=true` (Q8, default on). Mapping (locked Q18): `toggle --on/--off` → `-u low` (`"camfx · camera on — blur 25"`), `effect toggle` → `-u normal` (`"camfx · blur on"`), `daemon not running` → `-u critical` (`"camfx · daemon off — run: camfx start --dbus"`). Theme-set hook **never notifies** (throttle — avoids spam on `omarchy theme set`). `--quiet` on any CLI suppresses. Level overridable via `config.toml level="low"|"normal"|"critical"`.
- **Clipboard:** Not needed.

---

## 8. Class & API Schema

### 8.1 Class Schema (Python + QML)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              camfx (core, distro-neutral)                  │
│  VideoEnhancer ──► EffectController ──► EffectChain ──► [Effect]           │
│       │                 │                    │              ├─ BackgroundBlur│
│       │                 │                    │              ├─ BackgroundReplace│
│       │                 │                    │              ├─ BrightnessAdjustment│
│       │                 │                    │              ├─ FaceBeautification│
│       │                 │                    │              ├─ AutoFraming  │
│       │                 │                    │              └─ EyeGazeCorrection│
│       │                 │                    │                              │
│       │                 └─ signals: EffectChanged (dbus_control.py:204)    │
│       │                                                                       │
│       ├──► V4L2OutputFFmpeg (_resolve_v4l2_device, _start_ffmpeg, send, sleep_until_next_frame, cleanup)│
│       │       ▲                                                              │
│       │       │ abstract OutputBackend (new, optional) — see §8.3            │
│       │       └── PipeWireOutput (future, docs/kernel-module-alternatives) │
│       │                                                                       │
│       └──► CamfxControlService ──► CamfxControlServiceObject                   │
│              SERVICE_NAME=org.camfx.Control1, OBJECT_PATH=/org/camfx/Control1 │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                camfx_omarchy (optional plugin, only on Omarchy)            │
│                 pip install camfx[omarchy]  (Q5 default) — plugin registry │
│  OmarchyDetector          # is_omarchy(), omarchy_path(), current_theme_dir()│
│  ThemeAdapter             # load colors.toml/shell.toml —► generate gtk.css, │
│  │                        #   Gio.FileMonitor live-reload (Q7)               │
│  │  colors: dict[str,str]       # background, foreground, accent, muted…    │
│  │  shell_roles: dict           # Color.* / Style.* roles                   │
│  │  render_gtk_css(colors) -> str  # template or inline                     │
│  │  apply(theme_name: str|None) # write ~/.config/camfx/gtk.css, touch     │
│  │  css_path: Path = ~/.config/camfx/gtk.css  # watched by GUI CssProvider │
│  Config                   # ~/.config/camfx/config.toml {notifications,    │
│  │                        #   theme{live_reload:bool}, bar{position}} (Q8) │
│  CLI — omarchy-camfx.*    # bin_src/ python -m camfx_omarchy.cli            │
│  Hooks                    # hooks/theme-set.d/50-camfx.sh etc.              │
│  BindingsInstaller        # idempotent edits to ~/.config/hypr/*.lua        │
│  SystemdInstaller         # systemctl --user enable camfx; modprobe policy  │
│  │                        #   video_nr=-1 recommended (Q3)                │
│  BarRefresh               # omarchy-shell shell rescanPlugins (Q6 CLI-JSON) │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                shell/plugins/*camfx* (Quickshell QML)                       │
│  CamfxIndicator.qml  ──► BarIndicator  ──► BarIconButton                    │
│     props: camAvailable, camActive, effectLabel, effectCount                │
│     fn: refresh() via Process{command: ["omarchy-camfx","status","--json"]} │
│         extractData(raw) → {available, active, count, label}                │
│     handlers: onPressed (toggle), onWheel (cycle), indicatorHost.refresh    │
│  Camfx.qml (optional full widget) ──► BarWidget (show badge, popout)        │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Inheritance / seams:**

- `OutputBackend` (new, extraction from `V4L2OutputFFmpeg` to allow `PipeWireOutput` later) — see §8.3. At this milestone `VideoEnhancer` still holds `self.virtual_cam: V4L2OutputFFmpeg | None`; the abstraction is additive and extracted without breaking `core.py` callers.
- `ThemeAdapter` has no dependency on `gi`/GTK at import time; `apply()` shells out or lazy-imports.

### 8.2 API Schema

#### 8.2.1 D-Bus (`org.camfx.Control1` @ `/org/camfx/Control1`, session bus)

Existing (`camfx/dbus_control.py:17`):

| Member | Kind | Signature | Description |
|---|---|---|---|
| `SetEffect` | method | `(sa{sv}) → b` | Replace entire chain with single effect `effect_type` + `config` |
| `AddEffect` | method | `(sa{sv}) → b` | Add/updated-idempotent by type (class_to_type map at `dbus_control.py:72`) |
| `RemoveEffect` | method | `(i) → b` | Remove by index |
| `RemoveEffectByType` | method | `(s) → b` | Remove by `effect_type` string (`blur` etc.) |
| `ClearChain` | method | `() → b` | Remove all |
| `GetCurrentEffects` | method | `() → a(ssa{sv})` | Returns `[(effect_type, class_name, config), …]` |
| `UpdateEffectParameter` | method | `(ssv) → b` | Patch one param (`strength`, …) |
| `EffectChanged` | signal | `ssa{sv}` | `(action, effect_type, config)` where action ∈ {set,add,remove,clear,update} |
| `StartCamera` | method | `() → b` | `VideoEnhancer._start_camera()` |
| `StopCamera` | method | `() → b` | |
| `GetCameraState` | method | `() → b` | `video_enhancer.camera_active` |
| `CameraStateChanged` | signal | `b` | `is_active` |
| `ListCameraSources` | method | `() → a(ss)` | `[(id,label)]` (`camera_devices.py`) |
| `GetCameraModes` | method | `(s) → a(uuai)` | `(width,height,[fps])` per probed source |
| `GetCameraConfig` | method | `() → suuu` | `(source_id,width,height,fps)` |
| `ApplyCameraConfig` | method | `(suuu) → b` | Source + resolution + fps |
| `CameraConfigChanged` | signal | `suuu` | |

Behavioral notes (to preserve on every OS): `EffectController.lock` ensures thread-safe chain; `AddEffect` is idempotent by `class_to_type` (blur→`BackgroundBlur` etc.), signals carry the resulting action.

#### 8.2.2 CLI (`camfx` core + `omarchy-camfx` shims)

**Core `camfx` (unchanged, from `camfx/cli.py:129` + `setup.py:28`):**

```
camfx start [--input N] [--width W] [--height H] [--fps N] [--name STR] [--v4l2-device auto|/dev/videoX] [--v4l2-card-label STR] [--dbus]
camfx preview-camera [--input 0]
camfx preview-virtual [--name camfx] [--v4l2-device auto]
camfx list-devices
camfx effects   # prints EFFECT_SPECS (effect_specs.py)
camfx set-effect  --effect {blur,replace,brightness,beautify,autoframe,gaze-correct} [--strength N] [--image PATH] [--brightness N] [--contrast F] [--face-only] …
camfx add-effect  (same flags, appends/updates)
camfx remove-effect  (--index N | --effect KEY)
camfx get-effects
camfx camera-start | camera-stop | camera-status
camfx models-download
camfx gui
```

All `set/add-effect` ultimately call `dbus: SetEffect/AddEffect` when `--dbus` mode is active.

**Omarchy shims (`bin/omarchy-camfx-*`, routed as `omarchy camfx …`):**

Conforms to router spec (`docs/cli-router.md`, `agents/skills/command-metadata.md`): each file `bin/omarchy-camfx-<sub>` with header `# omarchy:summary=` etc. Selected subset:

```
# omarchy-camfx         — omarchy:group=camfx ; dispatches to camfx_omarchy/cli.py
#   omarchy camfx status --json|--waybar-json  →  {"available":bool,"active":bool,"count":int,"label":str,"effects":[{"type":str,"class":str,"config":{}}],"camera":{"source_id":str,"width":int,"height":int,"fps":int}}
#   omarchy camfx toggle [--on|--off|--next]   → flip GetCameraState; pokes bar refresh
#   omarchy camfx effect toggle <key> [params] → AddEffect if missing else RemoveEffectByType; notify
#   omarchy camfx cycle                        → iterate EFFECT_KEYS ring
#   omarchy camfx gui                          → uwsm-app -- camfx gui
#   omarchy camfx install                      → idempotent installer (see §10)
#   omarchy camfx theme-sync [--theme-name NAME] → ThemeAdapter.apply()
#   omarchy camfx doctor                       → checks: v4l2loopback loaded, ffmpeg present, /dev/video* exists, D-Bus reachable, MediaPipe cache

# omarchy-capture-camfx-preview … (optional) mirrors bin/omarchy-capture-* patterns for Waybar parity
```

Router examples:

```bash
omarchy camfx status --json
omarchy camfx toggle
omarchy camfx effect toggle blur --strength 25
omarchy theme set "Tokyo Night"   # fires hook → omarchy-camfx theme-sync
```

Signals for bar refresh (QML): either have QML `Process` poll after each `toggle`, or `omarchy-camfx toggle` call `omarchy-shell shell rescanPlugins` / trigger `Indicators.rescan` (cheap). For Waybar-compat fallback: `pkill -RTMIN+10 waybar`.

#### 8.2.3 QML contracts (shell plugins)

Every plugin ships `manifest.json` (`schemaVersion:1`, `id`, `kinds`, `entryPoints`). Bar widgets use `entryPoints.barWidget`; indicators register under `bar.widgets.Indicators` options list.

- `camfx.camfx` (B2 full widget) `barWidget: {displayName, category:"Media", defaultSection:"right", allowMultiple:false, schema:[…]}`
- `CamfxIndicator` (B1 indicator) `active`, `activeText`/`inactiveText`, `activeTooltipText`, `extractData`, `onPressed`, `visible/revealInactiveIndicators` parity with `BarIndicator.qml`.

Contract tests to pin against: `test/shell.d/fixtures/bar-widget-contract/`, `indicator-contract/`, `plugin-registry/` (enumerated in `bin/omarchy-plugin-catalog` JSON shape `{id,kinds,entryPoints,barWidget,bar,sourceDir,manifestPath}`).

---

## 9. File Map (before → after)

### 9.1 Repo `camfx` (what this PR/delta touches)

```
camfx/
  cli.py                         # add --json to camera-status / new `camfx status --json` for QML helper (Q6 a)
  camfx_omarchy/                 # NEW — optional plugin python package (pip install camfx[omarchy] — Q5 default)
    __init__.py
    omarchy_detection.py         # is_omarchy(), current_theme_dir(), shell_config_path()
    theme_adapter.py             # ThemeAdapter: read colors.toml/shell.toml → write gtk.css + touch live-reload (Q7)
    config.py                    # Config: ~/.config/camfx/config.toml loader {notifications, theme}
    cli.py                       # backing for bin/omarchy-camfx* (argparse — status/theme-sync/toggle/cycle/doctor/install)
    hooks/
      theme-set.sh.tmpl          # source for ~/.config/omarchy/hooks/theme-set.d/50-camfx.sh (live-touch, Q7)
      post-boot.sh.tmpl          # ensure v4l2loopback video_nr=-1 transient (Q3 recommendation) + respect existing
    bindings/
      camfx.lua.tmpl             # Hyprland bindings snippet
    systemd/
      camfx.service              # Omarchy-tuned user unit (WantedBy=graphical-session.target, manual enable Q11)
    templates/
      camfx.css.tpl              # optional default/themed additive template (GTK accent) — stretch, not MVP

camfx/output_v4l2_ffmpeg.py      # no breaking change; optionally extract OutputBackend ABC (add class OutputBackend; V4L2OutputFFmpeg(OutputBackend))
camfx/gui/main_window.py         # live-reload consumer: watch ~/.config/camfx/gtk.css via Gio.FileMonitor + Gtk.CssProvider hot-swap (Q7, no restart)
camfx/gui/config.py              # optional: read ~/.config/camfx/config.toml for notification toggle (Q8) — shared with camfx_omarchy/config.py

packaging/
  fedora/                        # untouched (distro-neutral core still builds there)
  omarchy/                       # NEW — source for Omarchy plugin registry publish (Q13), not AUR (Q1)
    PKGBUILD                     # optional Arch split (camfx / camfx-omarchy) for local VM install — registry is primary lane (§9.3)
    omarchy-shell-plugin/        # source for shell plugin shipped to registry (~/.config/omarchy/plugins/camfx.camfx)
      camfx.camfx/               # bar widget (Q2 rich, iterative) — id=camfx.camfx
        manifest.json            #  kind=bar-widget, entryPoints.barWidget=Camfx.qml
        Camfx.qml                #  v1 minimal toggle+badge → later popover
        CamfxModel.js            #  optional helper — icon/label map
    bin/                         # fellows of /usr/bin/omarchy-camfx* (also /usr/share/omarchy/bin/)
      omarchy-camfx              # dispatcher → python -m camfx_omarchy.cli
      omarchy-camfx-status       # (thin, optional)
      omarchy-camfx-toggle
      omarchy-camfx-cycle
      omarchy-camfx-theme-sync   # also called by theme-set hook
      omarchy-camfx-doctor
      omarchy-camfx-install      # idempotent registry installer (hooks/plugins/bindings)
    hooks/                       # template sources copied to ~/.config/omarchy/hooks/*.d/
      theme-set.sh               #  → theme-set.d/50-camfx.sh  (Q7 live-touch)
      post-boot.sh               #  → post-boot.d/50-camfx.sh (Q3 video_nr=-1 transient)
    bindings/
      camfx.lua                  #  → ~/.config/hypr/bindings.d/camfx.lua or appended guarded block
    systemd/
      camfx.service              #  → ~/.config/systemd/user/camfx.service (or /usr/lib/systemd/user)

docs/
  omarchy-integration-plan.md    # THIS FILE
  releases/v0.2.x-omarchy.md     # user-facing notes

tests/
  test_camfx_omarchy_detection.py
  test_camfx_omarchy_theme_adapter.py
  test_camfx_omarchy_cli_json.py
```

**What does NOT change on Fedora/Ubuntu:** if `camfx_omarchy` not installed, `camfx` imports never touch it; `omarchy_detection` never runs unless explicitly invoked via `omarchy-camfx` command.

### 9.2 Installed locations (Omarchy plugin registry lane — Q13, `docs/file-layout.md` compliant)

```
# From camfx plugin registry artifact (primary lane — Q13; AUR not used per Q1)
# Published as: camfx_omarchy Python (pip install camfx[omarchy]) + shell plugin dir camfx.camfx
# Registry entry points: omarchy plugin catalog over $OMARCHY_PATH/shell/plugins + ~/.config/omarchy/plugins/

# System-wide (if later upstreamed to basecamp/omarchy — Tier-2, optional):
/usr/share/omarchy/shell/plugins/camfx.camfx/
  manifest.json / Camfx.qml / CamfxModel.js       # Q2 rich bar widget, iterative
/usr/share/omarchy/bin/omarchy-camfx*            # shim binaries (also /usr/bin per env-bootstrap)
# /usr/share/omarchy/config/… seeding happens via /etc/skel only on user creation per file-layout.md — avoid here

# User-writable (seeded lazily on first `omarchy camfx install`, the installer invoked from VM test rig Q14):
~/.config/omarchy/plugins/camfx.camfx/           # cloned/enabled user plugin — hot-reload via omarchy-shell shell rescanPlugins
  manifest.json / Camfx.qml / CamfxModel.js
~/.config/omarchy/hooks/theme-set.d/50-camfx.sh  # Q7 live-touch hook (python3 -m camfx_omarchy.theme_adapter)
~/.config/omarchy/hooks/post-boot.d/50-camfx.sh  # Q3 transient modprobe video_nr=-1 + lsmod guard
~/.config/camfx/gtk.css                          # generated by hook/ThemeAdapter, watched live by GUI
~/.config/camfx/config.toml                      # [notifications] enabled=true level="low" (Q8 configurable), managed by `omarchy camfx config`
~/.config/hypr/bindings.lua  — appended guarded block or require("hypr.bindings.camfx") → bindings/camfx.lua
~/.config/omarchy/shell.json — updated via `omarchy plugin enable camfx.camfx --after omarchy.audio` + `omarchy bar move …`
~/.config/systemd/user/camfx.service             # optional, enabled only with --enable-service (Q11 default manual)
~/.local/state/omarchy/current/theme/camfx.css   # optional template renderer output (stretch, not MVP)

# Legacy Waybar assets — NOT shipped in this branch (Omarchy 3 reference only, Q12 no Waybar lane)
```

### 9.3 Packaging sketch (`packaging/omarchy/PKGBUILD` — kept for local VM installs, not the publish lane)

Primary publish lane per Q13 is **Omarchy plugins registry** (`omarchy plugin catalog` over `~/.config/omarchy/plugins/` + `$OMARCHY_PATH/shell/plugins/`), not `pacman`/AUR (Q1 explicitly skips AUR). The `PKGBUILD` here is retained only for the author's Omarchy VM (Q14) local `makepkg -si` installs and as a reference for a future `omarchy-pkgs` split if eventually desired.

```bash
pkgbase=camfx-omarchy
pkgname=(camfx camfx-omarchy)   # local-only; upstream publish is registry, not AUR
pkgver=0.2.0
pkgrel=1
arch=(any)
url="https://github.com/…/camfx"
license=(MIT)
makedepends=(python-build python-installer)
depends_camfx=(python python-opencv python-mediapipe python-click python-numpy ffmpeg v4l-utils)
optdepends_camfx=(gtk4 python-gobject dbus-python v4l2loopback-dkms: virtual camera kernel module (Q3 recommendation: video_nr=-1 transient))
depends_camfx-omarchy=(camfx omarchy omarchy-settings python)  # pulls Arch Omarchy shell stack
# Python extra already supplies the same: pip install camfx[omarchy] (Q5 default) → camfx_omarchy/
```

`camfx` builds from `setup.py` (`python -m build`), installs `camfx` CLI. `camfx-omarchy` installs the `camfx_omarchy` python pkg, the `omarchy-camfx*` bins, shell plugin source under `packaging/omarchy/omarchy-shell-plugin/camfx.camfx/`, and hook/binding templates into mapped locations (`docs/file-layout.md: Build-time map`). `.install` (if used) runs:

```bash
post_install_camfx-omarchy() {
  # registry-native path — idempotent, never clobbers user content without marker
  omarchy hook install theme-set /usr/share/omarchy/camfx/hooks/theme-set.sh --as 50-camfx || true
  # B2 widget (Q2): enable rich bar widget; indicator-row path no longer used
  omarchy plugin enable camfx.camfx --after omarchy.audio || true
  omarchy-shell shell rescanPlugins || true
}
```

**Publish flow (registry, Q13):** `camfx_omarchy` + `shell/plugins/camfx.camfx/` + `bin/omarchy-camfx*` are versioned together in this repo under `packaging/omarchy/`; a registry release is `git tag omarchy-v0.2.0` + `gh release upload camfx-omarchy-registry-v0.2.0.zip` containing exactly `~/.config/omarchy/plugins/camfx.camfx/` + hook/binding sources + `INSTALL.md`. User on Omarchy VM runs `omarchy camfx install` (which pulls that artifact or clones the tagged dir) rather than `yay -S`.

---

## 10. Implementation Steps (zero-ambiguity checklist)

### Phase 0 — Guardrails & Pre-flight (1 day, no product change)

- [ ] Pin CI against `omarchy quattro` shell contract tests: add `test/shell.d/theme-staging-test` parity check for any new `default/themed/*.tpl` we introduce (must mark `code` vs `colour` — `docs/theming.md: What an installed theme…`). For this branch: no new `default/themed` file in MVP, so the gate is effectively “no new tpl”.
- [ ] Vendor/update `/tmp/opencode/omarchy` clone in CI cache used for linting QML (`shell/plugins/**` `manifest.json` schema validated via `omarchy plugin catalog` + `jq` — Q13 registry lane). Cache the VM snapshot (Q14) for `hyprctl configerrors`-free `Camfx.qml` load.
- [ ] Confirm Q1–Q14 decisions are locked (§12 updated 2026-05-13). Any remaining “ask more questions till clarity” candidates are now in §12 new Q15–Q21.

### Phase 1 — Core seams (keep OS-neutral)

- [ ] Extract `OutputBackend` ABC in `camfx/output_v4l2_ffmpeg.py` (add `class OutputBackend(Protocol)` with `send(bytes)`, `sleep_until_next_frame()`, `cleanup()`, `device: str`). `V4L2OutputFFmpeg(OutputBackend)`. No behavior change, no import-time side effect. Keeps Q12's “no new backend” promise (ABC only, no PipeWire).
- [ ] Add `~/.config/camfx/gtk.css` **live-reload** loader to `camfx/gui/main_window.py` (Q7): on startup `Gtk.CssProvider().load_from_path()` into `Gtk.StyleContext`, plus `Gio.File.monitor_file()` on the CSS file that calls `provider.load_from_path()` again on `CHANGED` — so `theme-set` hook's `touch` repaints without restart. Guard `try/except` (non-fatal if file absent).
- [ ] Add `~/.config/camfx/config.toml` read in `camfx/gui/` as well (shares `camfx_omarchy/config.py` helper) for notification config pass-through (Q8).
- [ ] Add `--json` flag to `camfx camera-status` / new `camfx status --json` that emits machine-readable `{"available":bool,"active":bool,"count":int,"label":str,"effects":[…],"camera":{…}}` for the bar widget helper without parsing human strings (`camfx/cli.py:565` today prints `"Camera is ON"`). Also expose `camfx doctor --json` stub.
- [ ] Write `tests/test_output_backend_contract.py` to assert `OutputBackend` invariant.

### Phase 2 — Plugin Python package `camfx_omarchy` (pip `camfx[omarchy]`, Q5)

- [ ] Scaffold `camfx_omarchy/` with `omarchy_detection.py`, `theme_adapter.py`, `config.py`, `cli.py`, `__init__.py` + `py.typed`.
- [ ] `omarchy_detection.py`: `is_omarchy()`, `omarchy_path()`, `current_theme_dir()`, `shell_config_path()` — same as §7.1; query-only, no side effects.
- [ ] `theme_adapter.py`: read `~/.local/state/omarchy/current/theme/colors.toml` via `tomllib` (Python 3.11+), expose `load_colors(path)->dict`, `render_gtk_css(colors, template:str|None)->str`, `apply(theme_name)->Path` writing `~/.config/camfx/gtk.css` with `fchmod 0o644` **and** `Path.touch()` signalling live-reload; also write `~/.config/camfx/icon-theme.css` if icons needed. Hardcoded mapping: `background→window bg`, `foreground→fg_color`, `accent→accent_color`, `muted→dim_label`. No `pki` or restart.
- [ ] `config.py`: `~/.config/camfx/config.toml` loader with defaults `{notifications: {enabled:true, level:"low", on_toggle:true, on_effect:true}, theme:{live_reload:true}, bar:{position:"right"}}` (Q8 configurable, Q7 live-reload toggle). Exposed as `load_config()->dict`, `save_config()`.
 - [ ] `cli.py`: argparse subcommands `status --json|--waybar-json` (waybar kept stub-only for completeness), `toggle [--on|--off] [--quiet]`, `effect toggle <key> [--quiet]` (keyboard-first — no `cycle --wheel` flag after Q15; cycle is middle-click + `SUPER ALT+B/R` bindings §7.4), `cycle [--next|--prev]` for binding layer, `theme-sync [--theme-name NAME]`, `config {get,set}` (Q19 TOML human-settings), `doctor [--json]` (Q3-aware: reports `lsmod | grep v4l2loopback` + resolved `card_label` device), `install [--enable-service] [--persistent] [--force]` / `uninstall`. Every mutating command checks `~/.config/camfx/config.toml` `notifications.enabled` and emits per Q18 mapping (`low/normal/critical`) unless `--quiet` (Q8). `cycle --wheel` flag **removed** per Q15.
- [ ] Unit tests: `tests/test_camfx_omarchy_{detection,theme_adapter,config,cli_json}.py` — `cli_json` asserts both TOML config shape (`~/.config/camfx/config.toml`) and JSON manifest/status shapes.

### Phase 3 — Shell (Quickshell) bar integration — rich full widget iterative (Q2, Q6 a, Q13 registry)

- [ ] Create `packaging/omarchy/omarchy-shell-plugin/camfx.camfx/Camfx.qml` from §7.2 **full bar widget** template (v1 minimal toggle+badge; commits 2–4 expand to popover). Wire `Process { command: ["omarchy-camfx","status","--json"] }` → `Max` → `BarIconButton` (Q6 a — simple CLI-JSON helper, upgradeable later). Validate with `omarchy plugin catalog | jq -e '.[] | select(.id=="camfx.camfx")'`.
- [ ] Author `packaging/omarchy/omarchy-shell-plugin/camfx.camfx/manifest.json` (`id=camfx.camfx`, `kinds=[bar-widget]`, `entryPoints.barWidget=Camfx.qml`, `barWidget:{defaultSection:right, category:Media}`) per §7.2 locked manifest.
- [ ] Optional helper `CamfxModel.js` for icon/label mapping parity with `Microphone.qml` helper — keep purely presentational so Python CLI stays the single source of truth.
- [ ] Iterative commits plan (documented in §7.2): v1 = icon toggle; v2 = count badge + label; v3 = popover effect grid (blur/replace/brightness…); v4 = `replace` background-image picker (deferred if scope creep).
- [ ] Waybar: **not shipped** in this branch (Q12/Q13 — Quickshell-native only); keep a one-line Waybar stub `omarchy-camfx status --waybar-json` in `cli.py` for completeness, no `custom/camfx` JSONC fragment.

### Phase 4 — Hooks, Bindings, Systemd, Walker (Q3 recommendation + Q11 manual + Q8 configurable + Q16 video/theme split + Q20 no-overwrite)

- [ ] Hooks: author `camfx_omarchy/hooks/theme-set.sh.tmpl` (Q7 live-touch, **no notification per Q18**) + `post-boot.sh.tmpl` (Q3 `video_nr=-1` transient with `lsmod | grep -q v4l2loopback || sudo modprobe … || true`, respecting existing loads, `card_label` discovery). Both `bash -eu`, `$THEME_NAME=$1`, never `rm -rf` user data. `post-boot` only installed if `--persistent` not chosen; persistent path writes `/etc/modprobe.d/camfx.conf` via `sudo tee` with `options … video_nr=-1` (merge-safe). **Q16 note:** camfx video background (`--image` for `replace`) and Omarchy theme background (`backgrounds/`) are deliberately decoupled — hook never copies theme backgrounds into camfx.
- [ ] Bindings: `camfx_omarchy/bindings/camfx.lua.tmpl` per §7.4 (keyboard-first, no wheel). Installer logic `camfx_omarchy/cli.py install --bindings` **probes occupancy first** (`grep` + `omarchy menu keybindings --print` parsing) and **skips occupied `SUPER ALT+C/B/R` with `notify-send -u normal` “⚠ … already bound — manual intervention needed”** (Q20 — no auto `hl.unbind()`), unless `--force` which then emits `hl.unbind()` before `o.bind()`. Validate `hyprctl reload && hyprctl configerrors`.
- [ ] Systemd: `camfx_omarchy/systemd/camfx.service` (`After=graphical-session.target`, `WantedBy=graphical-session.target`). Installer `systemctl --user enable --now` **only** with `--enable-service` (Q11 manual).
- [ ] Walker/.desktop: emit `/usr/share/applications/camfx.desktop` with `Exec=uwsm-app -- camfx gui` (Q21 — confirmed as Omarchy's UWSM wrapper; `WAYLAND_DISPLAY`/`GDK_BACKEND` needs no override vs. session defaults per current Hyprland env). Walker discovers it; **stay Walker/bar-only per Q10/Q21 — no `omarchy menu` Trigger>Camera branch for now.** Validate `desktop-file-validate`.
- [ ] Notifications wiring: `omarchy-camfx toggle/effect` reads `~/.config/camfx/config.toml` (`notifications.enabled` default true per Q8, `level` per Q18 mapping `toggle→low/effect→normal/daemon→critical`, throttled for hooks) via `camfx_omarchy/config.py` (Q19 TOML human-settings, JSON only for machine state). Provide `omarchy camfx config set notifications.enabled false` to silence.

### Phase 5 — Installer & `omarchy-camfx` router shims — plugin registry lane (Q13, Q6 a, Q19 TOML/JSON split, Q20 no-overwrite)

- [ ] Write `camfx_omarchy/cli.py install [--yes] [--bindings] [--service] [--persistent] [--bar] [--quiet] [--force]` subcommand: copies hook templates to `~/.config/omarchy/hooks/*.d/` (mkdir -p, chmod +x), clones/enables shell plugin `camfx.camfx` via `omarchy plugin enable camfx.camfx --after omarchy.audio` (`right` section per Q17) and `omarchy-shell shell rescanPlugins`, runs `ThemeAdapter.apply()` immediately (`Q7 live-reload`), seeds bindings **only for free keys** (Q20 probe-skip + notification on collision) unless `--force`, reloads shell (`omarchy restart shell`). Default `--bar` enabled (rich widget Q2). TOML `~/.config/camfx/config.toml` created with commented defaults on first install (Q19), never overwritten on upgrade (merge). JSON (`doctor --json`, `status --json`, `install.json` state) stays machine-saved state. Idempotent checks per step; prints `… already installed, skipping` rather than clobbering. Provide `omarchy camfx uninstall`.
- [ ] Author `bin/omarchy-camfx*` as executable shims with headers `# omarchy:summary=…` / `# omarchy:group=camfx` so the router surfaces them (`docs/cli-router.md`). Dispatcher `exec python3 -m camfx_omarchy.cli "$@"`; thin wrappers for `status|toggle|cycle|theme-sync|doctor|config|install|uninstall`. Q6 a transport: shims emit JSON for QML `Process` with zero QML D-Bus imports (upgradeable later). `cycle` here is keyboard/middle-click cycle; `--wheel` flag intentionally absent (Q15).
- [ ] Idempotency: every `install` step guarded by existence checks and marker `~/.local/state/camfx/install.json` (JSON, Q19 — `{version, installed_at, bar: "camfx.camfx", bindings: ["SUPER ALT+C" …]}`) with `version` and `installed_at`. Provide `omarchy camfx install --reinstall` to force.

### Phase 6 — Packaging & CI matrix (VM-first, Q14)

- [ ] Add CI job that on Arch container installs `ffmpeg` + `v4l2loopback-dkms` mock (or at least `v4l2-ctl` stub) + `dbus-python` + `gtk4`, then checks `pip install -e .[gui,dbus,omarchy]` + `omarchy camfx doctor --json` schema conforms to §8.2.2. The VM's `omarchy plugin catalog | jq` asserts `camfx.camfx` appears after `install`.
- [ ] Keep `packaging/omarchy/PKGBUILD` + `.install` for **local** `makepkg -si` on the author's Omarchy VM (Q14), not for AUR publish. Publish dry-run `makepkg --printsrcinfo` in CI.
- [ ] For plugin registry publish: artifact is `packaging/omarchy/omarchy-shell-plugin/camfx.camfx/` + hooks/bindings + `INSTALL.md`. Release via `git tag omarchy-v0.2.x && gh release create` + `omarchy plugin add camfx.camfx --from ./dist/camfx-camfx.zip` flow documented in `docs/omarchy.md`. The upstream `basecamp/omarchy` PR lane (adding under `/usr/share/omarchy/shell/plugins/`) is deferred until registry validation (Q1).

### Phase 7 — Docs, Previews & Release

- [ ] User doc `docs/omarchy.md` (Install / Controls / Themes — live-reload demo / Hooks / Notifications configurable / Troubleshooting `video_nr=-1` card_label discovery — with screenshots for `bar` widget + `gui` themed under `Tokyo Night`, `Catppuccin`, `Kanagawa`, etc.).
- [ ] Entry in `docs/releases/v0.2.x-omarchy.md` + `README.md` installation matrix: Fedora `dnf` vs. Omarchy `pip install camfx[omarchy]` + `omarchy plugin enable camfx.camfx` (not `pacman -S`/`yay -S` — Q1).
- [ ] Recording/demos for manual — short `gpu-screen-recorder` captures (Q14 VM) showing `Camfx.qml` toggle + `omarchy theme set` live-reload + `notify-send` (Q8) on effect cycle.
- [ ] Version gate: if any new file under `default/themed/*.tpl` is added, declare its `code`/`colour` nature so `test/shell.d/theme-staging-test.sh` stays green; otherwise forbids landing. For this branch, gate is “no new tpl” so trivially green.

---

## 11. Verification Matrix (Q14 VM rig, plugin registry lane)

| Area | Check | How (on Omarchy VM — Q14) |
|---|---|---|
| Core still OS-neutral | `pip install -e .` (no omarchy extra) on Fedora container → `pytest -q` green, no `OMARCHY_PATH` import at import time | `pytest tests/test_effect_chaining.py tests/test_camera_devices.py tests/test_output_backend_contract.py -v` |
| Theme sync (Q7 live-reload) | `omarchy theme set catppuccin` writes `~/.config/camfx/gtk.css` containing `accent` colour; **existing** `camfx gui` window repaints without restart (CssProvider FileMonitor) | `camfx gui & sleep 2; omarchy theme set tokyo-night; sleep 1; grep -q "$(grep -m1 accent ~/.local/state/omarchy/current/theme/colors.toml | cut -d'"' -f2)" ~/.config/camfx/gtk.css && echo ok` |
| Bar full widget (Q2) | `omarchy camfx install && omarchy plugin catalog | jq -e '.[] | select(.id=="camfx.camfx")'` and bar shows `󰻂/󰻄`; click toggles `GetCameraState` | `omarchy-shell shell rescanPlugins && omarchy plugin enable camfx.camfx --after omarchy.audio && sleep 1; omarchy camfx toggle; omarchy camfx status --json | jq -e '.active==true'` |
| Iterative widget growth | v1 icon only → v2 badge (`effectCount`) → v3 popover (`effect toggle`) each preserve prior layout | `git diff packaging/omarchy/omarchy-shell-plugin/camfx.camfx/Camfx.qml` review per commit |
| Hooks idempotent + Q3 | Repeated `omarchy camfx install` leaves timestamps on `50-camfx.sh`; `video_nr=-1` transient probe respects already-loaded module with different `card_label` | `stat ~/.config/omarchy/hooks/theme-set.d/50-camfx.sh` + repeat; `lsmod | grep v4l2loopback` before/after |
| Bindings | `hyprctl configerrors` empty after install; `SUPER ALT+C` fires `omarchy camfx toggle` | `hyprctl reload && hyprctl configerrors 2>&1 | tee /tmp/err; grep -q camfx ~/.config/hypr/bindings.lua` |
| D-Bus on Hyprland/UWSM | `dbus.SessionBus().get_object('org.camfx.Control1',…)` works inside `uwsm` session, not only `gnome-session` | `busctl --user status org.camfx.Control1; omarchy camfx doctor --json | jq .dbus.reachable` |
| Notifications configurable (Q8) | With `notifications.enabled=true` toggle emits `notify-send`; with `false` silent | `omarchy camfx config set notifications.enabled true; omarchy camfx toggle; journalctl --user -n 20 | grep camfx` vs `false` |
| CLI bridge (Q6 a) | `omarchy camfx status --json` matches schema in §8.2.2; QML `Process` parses it | `omarchy camfx status --json | python3 -m json.tool` + QML `StdioCollector` visual |
| Publishability (Q13 registry) | Install from registry artifact recreates same layout as local `install` | `rm -rf ~/.config/omarchy/plugins/camfx.camfx; omarchy plugin add camfx.camfx --from ./dist/camfx-camfx.zip` (or clone tagged dir) |
| Waybar (out of scope) | NOT checked for this branch (Q12) | — |

---

## 12. Resolved Questions (Q1–Q26 — all answers 2026-05-13, build-ready)

### Resolved Q1–Q21 (locked — §§4–10 already reflect these)

**Q1. Scope: Tier-1 vs. Tier-2?** → **Skip AUR, focus on Omarchy itself** (registry-native plugin). *Applied: §4/#5, §5.2 selected, §9.3 PKGBUILD demoted to local VM helper only.*

**Q2. Bar surface B1 vs B2?** → **Richer full bar widget `camfx.camfx`, iterative over commits** (start small, improve). *Applied: §6, §7.2, §9.1, §10 Phase 3 iterative commits.*

**Q3. `v4l2loopback` `video_nr` policy?** → **See recommendation chart in §7.6 — default `video_nr=-1` kernel-picked + card_label discovery, transient `post-boot` hook, persistent `/etc/modprobe.d/camfx.conf` only with `--persistent`.** Details in table comparing `-1` vs. pinned `42`/`10` vs. persistent file, including OBS collision rationale. *Applied: §7.6 table, §10 Phase 4 hook.* User asked for chart — chart shipped; the choice is locked to `-1` default.

**Q4. Namespace?** → **As recommended: Python `camfx` + `camfx[omarchy]` extra, shell plugin `camfx.camfx` (not AUR `python-camfx-omarchy`).** Since AUR is out of scope, no `pkgbase` naming contention. *Applied: §5.2, §8.1, §9.1.*

**Q5. Python distribution?** → **Default (PyPI `camfx` + `camfx[omarchy]` extra, `pip install camfx[omarchy]`).** Not Arch `python-camfx`. *Applied: §8.1, §9.2, §10 Phase 6.*

**Q6. Bar ↔ D-Bus bridge?** → **Start with (a) `Process ["omarchy-camfx","status","--json"]` CLI-JSON helper, improvable later to direct QML D-Bus/file portal.** QML stays free of `DBus` import for MVP. *Applied: §6 wiring, §7.2 QML, §10 Phase 3.*

**Q7. Theme retint: live-reload vs restart?** → **Live reload (no restart) — Gio.FileMonitor + Gtk.CssProvider hot-swap, hook `touch`es the CSS.** `pkill -f "camfx gui"` explicitly rejected. *Applied: §7.3 code, §10 Phase 1.*

**Q8. Notifications on toggle?** → **Yes, configurable — `~/.config/camfx/config.toml [notifications] enabled=true level="low"` default on for Omarchy, `--quiet` or `enabled=false` to silence.** Every mutating CLI command checks the config. *Applied: §7.7, `camfx_omarchy/config.py`, §10 Phase 2/4.*

**Q9. Icons & labels?** → **Default glyphs kept** (`off=󰻄`, `on=󰻂`, `effects>1=󰻃` variant) and `effectLabel` short key (`blur` etc.). *Applied: §7.2 QML defaults.*

**Q10. Walker/omarchy-menu depth?** → **Default: bar + Walker `*.desktop` only, no deep `omarchy-menu` branch in v1** (menu branch deferred to follow-up). *Applied: §7.5.*

**Q11. `camfx start` auto-boot?** → **Default manual — `omarchy camfx install` does not `systemctl --user enable` unless `--enable-service`.** Camera off / daemon ready only when opted. *Applied: §7.6, §10 Phase 4.*

**Q12. PipeWire coexistence / new features?** → **Focus on existing V4L2 → Omarchy integration only, no new output backend in this branch.** PipeWire deferred to `docs/kernel-module-alternatives.md`. *Applied: §2 Non-Goals, §6 ABC-only.*

**Q13. Publish lane?** → **Omarchy plugins registry** (`omarchy plugin catalog` / `~/.config/omarchy/plugins/camfx.camfx`, `shell/plugins` discovery). Not AUR, not `omarchy-pkgs/pacman`, not direct `basecamp/omarchy` PR for now — registry artifact (`git tag omarchy-v*` zip). *Applied: §4/#5, §5.2, §9.2, §10 Phase 5/6.*

**Q14. Testing rig?** → **Author provides Omarchy VM.** Plan assumes VM for `hyprctl configerrors`, QML lint, `omarchy plugin catalog | jq`, `omarchy theme set` live-reload, and `gpu-screen-recorder` demos. CI mirrors the VM with stubs. *Applied: §10 Phase 6, §11 matrix.*

### Resolved — Q15–Q21 (answers 2026-05-13, second round)

**Q15. Effect cycle order & wheel?** → **No wheel — keyboard-first.** Remove `onWheelMoved` from `Camfx.qml`; cycling is `middle-click` + `SUPER ALT+B/R` (+ future `SUPER ALT+G` popover). Order still `blur→replace→brightness→beautify→autoframe→gaze-correct→clear` but wheel plumbing dropped. *Applied: §7.2 QML, §7.4 bindings, §10 Phase 2/3 (`--wheel` flag removed).*

**Q16. `replace` background source on Omarchy?** → **Do not fix video background to theme background — keep independent.** Camfx video background (`--image` for `replace`, `control.py:146` + `resources/default_background.jpg` fallback) and Omarchy theme backgrounds (`~/.config/omarchy/backgrounds/<theme>/`, `~/Pictures`) are distinct domains. No coupling; picker commit 4 offers file chooser starting at last-used camfx path, not theme dir. Hook never copies theme backgrounds. *Applied: §7.6 Q16 note, §10 Phase 4 hook.*

**Q17. Bar position & section default?** → **`right`, after `omarchy.audio`** (media cluster). Confirmed. *Applied: §7.2 placement, `omarchy plugin enable camfx.camfx --after omarchy.audio`, §9.2, §10 Phase 5.*

**Q18. Notification level & throttle?** → **Author decision locked: `toggle→low`, `effect toggle→normal`, `daemon not running→critical`, theme-set hook never notifies (throttle).** Configurable via `~/.config/camfx/config.toml` (`--quiet` escapes). *Applied: §7.7, `config.py`, §10 Phase 4.*

**Q19. Config file format?** → **TOML for human settings (`~/.config/camfx/config.toml`, `colors.toml` family), JSON for manifests/machine state (`manifest.json`, `status --json`, `~/.local/state/camfx/install.json`).** `camfx_omarchy/config.py` creates commented TOML on first install, merges on upgrade (never overwrites). Shared between GUI + CLI. *Applied: §8.1 Config, §10 Phase 2/5, §11 matrix.*

**Q20. Hyprland binding collisions?** → **Do not override — skip occupied keys, notify that manual intervention is needed.** Probe first; if `SUPER ALT+C/B/R` taken, emit `notify-send -u normal "⚠ SUPER ALT+C already bound … — camfx binding not installed"` and skip that `o.bind()`. Only with explicit `--force` does installer emit `hl.unbind()` before `o.bind()`. *Applied: §7.4, §10 Phase 4.*

**Q21. `camfx gui` launch path & display?** → **Confirmed: `uwsm-app -- camfx gui` (UWSM wrapper), `WAYLAND_DISPLAY`/`GDK_BACKEND` need no override vs. Omarchy session defaults; stay Walker + bar right-click only (no `omarchy menu` Trigger>Camera branch for now, per Q10).** *Applied: §7.5 Walker `Exec=`, §10 Phase 4, §7.4 right-click.*

### Resolved Q22–Q26 (answers 2026-05-13, second popover round — now locked)

**Q22. Persist last chain?** → **Persist** (`~/.local/state/camfx/state.json` JSON per §8.2 + Q19 JSON/machine-state rule, restored at `camfx start --dbus`; absent file → start clean). *Applied: `control.py` restore path, `§11` doctor hint, `camfx_omarchy/config.py` adds `state_path`.*

**Q23. Popover content (commit 3)?** → **Both — toggles + per-effect controls.** Row of toggles for all `EFFECT_KEYS` (`blur/replace/brightness/beautify/autoframe/gaze-correct`) **and** a slider/param panel for the currently active effect (e.g., `blur strength`, `brightness brightness/contrast`). Minimal in v1 toggle flips; v1 popover shows controls for whichever effect is active, future commit adds per-toggle inline sliders. *Applied: `Camfx.qml` commit 3 Loader scope narrowed to toggle grid + active-effect panel.*

**Q24. Replace background picker (commit 4)?** → **Portal file picker** (`GTK FileChooser` via `xdg-desktop-portal`, `omarchy camfx replace --pick`). Not an inline QML thumbnail strip. *Applied: commit 4 scope §7.2 comment.*

**Q25. Media-keys?** → **Stay with default — `SUPER ALT` only, no `XF86Camera`/`XF86Video` media-key in v1.** Preserves deterministic binding set; can be revisited after `ls /dev/input/` audit on VM. *Applied: `§7.4` media section stays empty.*

**Q26. Widget visibility when daemon off?** → **Always show** (`visible: true` dimmed `󰻄`, tooltip `daemon off — Click start` → `camfx start --dbus`). One-click start affordance, not hidden. *Applied: `Camfx.qml` `visible` logic locked true, `§11` matrix.*

> All 26 questions now resolved. No remaining ambiguous defaults before first commit. Any new edge (e.g., OBS already owning `card_label`) is covered by Q3's `lsmod` guard — no further gate needed.

---

## Appendix A — Background Reader Map

- `omarchy` file layout & seeding: `docs/file-layout.md` (`Seed/Finalize/Resync`, `Env bootstrap`, `etc-overrides`).
- CLI router: `docs/cli-router.md` + `agents/skills/command-metadata.md`.
- Theming invariants & `INSTALLED_THEME_DENIED`: `docs/theming.md`, `bin/omarchy-theme-set: INSTALLED_THEME_DENIED`, `test/shell.d/theme-staging-test.sh`.
- Bar/widgets/plugins: `default/agents/skills/omarchy/plugins.md`, `shell/plugins/bar/{Bar.qml,BarModel.js,widgets/*.qml,indicators/*.qml}`, `shell/Ui/BarIndicator.qml`, `bin/omarchy-plugin-{clone,enable,catalog}`.
- Hooks: `default/agents/skills/omarchy/hooks.md`, `bin/omarchy-hook`, `config/omarchy/hooks/*.d/*.sample`.
- Hyprland Lua arch: `default/agents/skills/omarchy/hyprland.md`, `config/hypr/hyprland.lua` + `default/hypr/{omarchy,helpers,bindings/*}.lua`.
- Capture/screenrecord precedent: `bin/omarchy-capture-screenrecording`, `bin/omarchy-capture-webcam-list`, `shell/plugins/bar/indicators/ScreenRecording.qml`.

## Appendix B — Minimal Rust-free template example (deferred)

If a future `default/themed/camfx.css.tpl` were added, it would look like:

```css
/* default/themed/camfx.css.tpl → rendered to ~/.local/state/omarchy/current/theme/camfx.css */
window.background { background-color: {{ background }}; color: {{ foreground }}; }
button.suggested-action { background: {{ accent }}; color: {{ background }}; }
label.dim { color: {{ muted }}; }
```

But for MVP, `ThemeAdapter` renders `~/.config/camfx/gtk.css` at hook time instead, so no `default/themed` change and no `INSTALLED_THEME_DENIED` delta.

## Appendix C — Waybar legacy fragment (conditional)

```jsonc
// ~/.config/waybar/config.jsonc — added only if Waybar exists on disk
"custom/camfx": {
  "exec": "omarchy-camfx status --waybar-json",
  "return-type": "json",
  "interval": 5,
  "signal": 10,
  "on-click": "omarchy-camfx toggle",
  "on-click-right": "omarchy-camfx gui",
  "tooltip": true
}
```
```css
/* ~/.config/waybar/style.css — appended by installer */
@import "../omarchy/current/theme/waybar.css"; /* already present */
#custom-camfx { color: @foreground; }
#custom-camfx.active { color: @accent; }
```

Relies on `config/waybar/config.jsonc` era vars; ignored on Quickshell but harmless if present.

