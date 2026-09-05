import QtQuick
import Quickshell.Io
import qs.Ui

// camfx — Omarchy bar widget (v0.4.0, Q2 rich iterative, Q15 keyboard-first, Q26 always show)
// Contract: queries `omarchy-camfx status --json` via Process (Q6 a), renders as BarWidget.
// Live in: ~/.config/omarchy/plugins/camfx.camfx/ (discovered by omarchy plugin catalog).
// Iteratively: v1 minimal toggle+badge (below), v2 badge+label, v3 keyboard-navigable popover.
BarWidget {
    id: root
    moduleName: "camfx.camfx"

    property bool camAvailable: false
    property bool camActive: false
    property string effectLabel: ""
    property int effectCount: 0

    // Q26: always show even when daemon off — one-click start affordance (visible:true dimmed)
    visible: true
    implicitWidth: button.implicitWidth + (badge.visible ? badge.implicitWidth + 4 : 0)
    implicitHeight: button.implicitHeight

    function refresh() {
        if (!statusProc.running) statusProc.running = true
    }

    onBarChanged: refresh()
    Component.onCompleted: refresh()

    // Optional: timer fallback if D-Bus signals not trusted in QML — low frequency (4s)
    Timer {
        interval: 4000
        running: true
        repeat: true
        onTriggered: root.refresh()
    }

    Process {
        id: statusProc
        // Q6 a: CLI JSON helper — simple, upgradeable later to direct QML DBus
        command: ["bash", "-c", "omarchy-camfx status --json 2>/dev/null || echo '{\"available\":false}'"]
        stdout: StdioCollector {
            waitForEnd: true
            onStreamFinished: {
                var raw = String(text || "")
                var d = {}
                try {
                    // BarIndicator's extractData handles non-JSON wrappers; replicate minimal parse
                    var start = raw.indexOf("{")
                    var end = raw.lastIndexOf("}")
                    if (start !== -1 && end !== -1) raw = raw.substring(start, end + 1)
                    d = JSON.parse(raw)
                } catch (e) { d = {} }
                root.camAvailable = !!d.available
                root.camActive = !!d.active
                root.effectLabel = String(d.label || "")
                root.effectCount = Number(d.count || 0)
            }
        }
        onExited: function(code) {
            if (code !== 0) root.camAvailable = false
        }
    }

    Row {
        anchors.centerIn: parent
        spacing: 2

        BarIconButton {
            id: button
            bar: root.bar
            // Q9 defaults: off 󰻄 , on 󰻂 , effects>1 󰻃
            text: root.camActive ? (root.effectCount > 1 ? "󰻃" : "󰻂") : "󰻄"
            active: root.camActive
            // Dim when daemon off but still clickable (Q26)
            dimmed: !root.camActive
            tooltipText: root.camAvailable
                ? (root.camActive
                    ? ("camfx · " + (root.effectLabel || "on") + "  · Click off · Right GUI · Middle cycle")
                    : "camfx · off  · Click on")
                : "camfx · daemon off  · Click start"

            onPressed: function(ev) {
                if (ev === Qt.RightButton) {
                    if (root.bar) root.bar.run("omarchy-camfx gui")
                    return
                }
                if (ev === Qt.MiddleButton) {
                    if (root.bar) root.bar.run("omarchy-camfx cycle")
                    return
                }
                // Left click: toggle on/off
                if (root.camActive) {
                    if (root.bar) root.bar.run("omarchy-camfx toggle --off")
                } else {
                    // When daemon off, try to start it (one-click); fallback message is via notify critical
                    if (root.bar) root.bar.run("omarchy-camfx toggle --on")
                }
                // Refresh shortly after action
                refreshTimer.restart()
            }
            // Q15: Omarchy is keyboard-first — no onWheelMoved handler.
        }

        // Badge: effect count when >1 (commit 2 affordance, minimalist)
        Text {
            id: badge
            visible: root.effectCount > 1 && root.camActive
            text: String(root.effectCount)
            color: Style.foreground
            font.pixelSize: 9
            verticalAlignment: Text.AlignVCenter
            leftPadding: 2
        }
    }

    Timer {
        id: refreshTimer
        interval: 700
        onTriggered: root.refresh()
    }

    // Commit 3 placeholder: keyboard-navigable popover Loader (toggles + active-effect sliders)
    // Loader { id: popover; visible: false; sourceComponent: effectGrid; ... }
    // Triggered via SUPER ALT+G binding (exec = "omarchy-camfx cycle") and middle-click.
}
