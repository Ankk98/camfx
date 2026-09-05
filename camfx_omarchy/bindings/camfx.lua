-- camfx — Omarchy Hyprland bindings (Q15 keyboard-first, Q20 no-overwrite)
-- Installed to: ~/.config/hypr/bindings/camfx.lua
-- Required by ~/.config/hypr/bindings.lua via: require("hypr.bindings.camfx")
-- Q20: This file is only installed if SUPER ALT+C/B/R are free. If occupied, installer skips and notifies.
--       With --force, installer emits hl.unbind() before each o.bind(); that path is not the default.
local o = require("default.hypr.omarchy")

-- Toggle camera — primary (keyboard-driven, no wheel per Q15)
o.bind("SUPER ALT + C", "camfx: toggle camera", { exec = "omarchy-camfx toggle" })
-- GUI
o.bind("SUPER ALT + SHIFT + C", "camfx: GUI", { launch = "camfx gui" })
-- Blur toggle
o.bind("SUPER ALT + B", "camfx: blur toggle", { exec = "omarchy-camfx effect toggle blur" })
-- Replace toggle (uses default_background.jpg fallback if no --image, Q16 decoupled from theme backgrounds)
o.bind("SUPER ALT + R", "camfx: replace toggle", { exec = "omarchy-camfx effect toggle replace" })
-- Popover (commit 3) — middle-click equivalent for keyboard users
o.bind("SUPER ALT + G", "camfx: effects popover", { exec = "omarchy-camfx cycle" })
