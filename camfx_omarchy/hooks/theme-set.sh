#!/bin/bash
# camfx Omarchy — theme-set hook (Q7 live-reload, Q18 throttled: never notifies)
# Installed to: ~/.config/omarchy/hooks/theme-set.d/50-camfx.sh
# Contract: THEME_NAME=$1 (hooks.md), never clobbers user content, exit 0
set -euo pipefail
THEME_NAME="${1:-}"
# Derive GTK CSS from Omarchy palette — also `touch`es file for Gio.FileMonitor
python3 -m camfx_omarchy.theme_adapter --theme-name "$THEME_NAME" 2>/dev/null || true
# Live-reload hint for running GUI (Gio.FileMonitor on ~/.config/camfx/gtk.css)
if [[ -f "$HOME/.config/camfx/gtk.css" ]]; then
	touch "$HOME/.config/camfx/gtk.css" 2>/dev/null || true
fi
