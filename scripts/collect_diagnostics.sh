#!/bin/bash
# Diagnostic script to collect information about PipeWire, Wireplumber, and dependencies
# for camfx virtual camera functionality

OUTPUT_FILE="${1:-camfx_diagnostics_$(date +%Y%m%d_%H%M%S).txt}"

# Function to output (both to terminal and file)
output() {
    echo "$@" | tee -a "$OUTPUT_FILE"
}

# Initialize output file
> "$OUTPUT_FILE"

output "=========================================="
output "camfx Dependency Diagnostics"
output "Generated: $(date)"
output "=========================================="
output ""

# Function to run command and capture output
run_check() {
    local title="$1"
    local cmd="$2"
    
    output "----------------------------------------"
    output "$title"
    output "----------------------------------------"
    if eval "$cmd" 2>&1 | tee -a "$OUTPUT_FILE"; then
        output "[OK]"
    else
        output "[FAILED or NOT FOUND]"
    fi
    output ""
}

# System Information
run_check "System Information" "uname -a"
run_check "Distribution Info" "cat /etc/os-release 2>/dev/null || echo 'Not available'"
run_check "Kernel Version" "uname -r"

# PipeWire Information
run_check "PipeWire Service Status (systemd --user)" "systemctl --user status pipewire 2>&1 || echo 'Service check failed'"
run_check "PipeWire Service Status (systemd --system)" "systemctl status pipewire 2>&1 || echo 'Service check failed'"
run_check "PipeWire Process Check" "pgrep -a pipewire || echo 'No pipewire process found'"
run_check "PipeWire Version" "pipewire --version 2>&1 || echo 'pipewire command not found'"
run_check "PipeWire Libraries" "ldconfig -p | grep pipewire || echo 'No pipewire libraries found'"
run_check "PipeWire Package Info (RPM)" "rpm -qi pipewire 2>&1 || echo 'Not installed via RPM or not available'"
run_check "PipeWire Package Info (DPKG)" "dpkg -l | grep pipewire 2>&1 || echo 'Not installed via DPKG or not available'"

# Wireplumber Information
run_check "Wireplumber Service Status (systemd --user)" "systemctl --user status wireplumber 2>&1 || echo 'Service check failed'"
run_check "Wireplumber Service Status (systemd --system)" "systemctl status wireplumber 2>&1 || echo 'Service check failed'"
run_check "Wireplumber Process Check" "pgrep -a wireplumber || echo 'No wireplumber process found'"
run_check "Wireplumber Version" "wireplumber --version 2>&1 || echo 'wireplumber command not found'"
run_check "Wireplumber Package Info (RPM)" "rpm -qi wireplumber 2>&1 || echo 'Not installed via RPM or not available'"
run_check "Wireplumber Package Info (DPKG)" "dpkg -l | grep wireplumber 2>&1 || echo 'Not installed via DPKG or not available'"

# GStreamer Information
run_check "GStreamer Version" "gst-launch-1.0 --version 2>&1 || echo 'gst-launch-1.0 not found'"
run_check "GStreamer Plugins (pipewiresink)" "gst-inspect-1.0 pipewiresink 2>&1 | head -30 || echo 'pipewiresink plugin not found'"
run_check "GStreamer Plugins (videoconvert)" "gst-inspect-1.0 videoconvert 2>&1 | head -20 || echo 'videoconvert plugin not found'"
run_check "GStreamer Plugins (appsrc)" "gst-inspect-1.0 appsrc 2>&1 | head -20 || echo 'appsrc plugin not found'"
run_check "GStreamer Package Info (RPM)" "rpm -qa | grep -i gstreamer | head -20 || echo 'No GStreamer packages found'"
run_check "GStreamer Package Info (DPKG)" "dpkg -l | grep -i gstreamer | head -20 || echo 'No GStreamer packages found'"

# Python Dependencies
run_check "Python Version" "python3 --version 2>&1 || python --version 2>&1"
run_check "Python GI (PyGObject) Check" "python3 -c 'import gi; gi.require_version(\"Gst\", \"1.0\"); from gi.repository import Gst; print(f\"GStreamer Python bindings: OK (GStreamer {Gst.version_string()})\")' 2>&1 || echo 'PyGObject/GStreamer Python bindings not available'"
run_check "Python OpenCV Check" "python3 -c 'import cv2; print(f\"OpenCV version: {cv2.__version__}\")' 2>&1 || echo 'OpenCV not available'"
run_check "Python MediaPipe Check" "python3 -c 'import mediapipe; print(f\"MediaPipe version: {mediapipe.__version__}\")' 2>&1 || echo 'MediaPipe not available'"
run_check "Python NumPy Check" "python3 -c 'import numpy; print(f\"NumPy version: {numpy.__version__}\")' 2>&1 || echo 'NumPy not available'"
run_check "Installed Python Packages" "pip list 2>&1 | grep -E '(opencv|mediapipe|PyGObject|numpy|click)' || echo 'No matching packages found'"

# Environment Variables
run_check "Relevant Environment Variables" "env | grep -iE '(pipewire|gstreamer|gst|xdg|wayland|display)' || echo 'No relevant environment variables found'"

# User Session Information
run_check "User ID and Groups" "id"
run_check "XDG Runtime Directory" "echo \"XDG_RUNTIME_DIR: \${XDG_RUNTIME_DIR:-not set}\""
run_check "XDG Runtime Directory Contents" "ls -la \${XDG_RUNTIME_DIR:-/tmp} 2>/dev/null | grep -E '(pipewire|wireplumber)' || echo 'No pipewire/wireplumber sockets found'"

# PipeWire Socket Check
run_check "PipeWire Socket" "test -S \${XDG_RUNTIME_DIR:-/tmp}/pipewire-0 && echo 'PipeWire socket exists' || echo 'PipeWire socket not found'"

# Systemd User Services
run_check "Systemd User Services Status" "systemctl --user list-units --type=service --state=running 2>&1 | grep -E '(pipewire|wireplumber)' || echo 'No pipewire/wireplumber services running'"

# Logs (last 20 lines)
run_check "Recent PipeWire Logs (journalctl --user)" "journalctl --user -u pipewire -n 20 --no-pager 2>&1 || echo 'No pipewire logs found'"
run_check "Recent Wireplumber Logs (journalctl --user)" "journalctl --user -u wireplumber -n 20 --no-pager 2>&1 || echo 'No wireplumber logs found'"

# GStreamer Registry
run_check "GStreamer Registry Info" "gst-inspect-1.0 --print-plugin-auto-install-info 2>&1 | head -10 || echo 'Could not query registry'"

# Test GStreamer Pipeline (dry run)
run_check "GStreamer Pipeline Test (parse only)" "gst-launch-1.0 --parse-only 'appsrc ! videoconvert ! pipewiresink' 2>&1 || echo 'Pipeline parse test failed'"

output "=========================================="
output "Diagnostics Complete"
output "Output saved to: $OUTPUT_FILE"
output "=========================================="

