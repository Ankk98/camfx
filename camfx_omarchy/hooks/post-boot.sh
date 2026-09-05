#!/bin/bash
# camfx Omarchy — post-boot hook (Q3 video_nr=-1 transient, respected if already loaded)
# Installed to: ~/.config/omarchy/hooks/post-boot.d/50-camfx.sh
# Is no-op if v4l2loopback already loaded (e.g. by OBS or prior install) — never fights existing module
set -euo pipefail
if lsmod 2>/dev/null | grep -q "^v4l2loopback"; then
	# Already loaded — discover and exit (camfx will resolve via card_label)
	exit 0
fi
# Try to load transient, kernel-picked node (Q3 recommendation: video_nr=-1, card_label discovery)
if modprobe -n v4l2loopback 2>/dev/null | grep -q "v4l2loopback"; then
	# not found
	exit 0
fi
sudo modprobe v4l2loopback exclusive_caps=1 card_label="camfx" video_nr=-1 2>/dev/null || true
# No notification — boot hooks are silent; doctor will report if still missing
