// CamfxModel.js — helper for Camfx.qml icon/label mapping (Q9 defaults)
// Kept presentational; Python CLI remains single source of truth for effect types.
.pragma library

var effectIcons = {
    "blur": "󰻂",
    "replace": "󰻃",
    "brightness": "󰃠",
    "beautify": "󰃭",
    "autoframe": "󰹑",
    "gaze-correct": "󰔷"
}

function iconFor(label, active, count) {
    if (!active) return "󰻄" // off
    if (count > 1) return "󰻃"
    return effectIcons[label] || "󰻂"
}

function labelFor(payload) {
    if (!payload || !payload.label) return ""
    return String(payload.label)
}
