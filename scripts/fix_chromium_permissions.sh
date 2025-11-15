#!/bin/bash
# Fix Flatpak Chromium permissions for PipeWire camera access

set -e

CHROMIUM_ID="org.chromium.Chromium"

echo "============================================================"
echo "Fixing Flatpak Chromium PipeWire Permissions"
echo "============================================================"

# Check if Chromium is installed as Flatpak
if ! flatpak list --app | grep -q "$CHROMIUM_ID"; then
    echo "⚠️  Chromium Flatpak not found. Checking for other Chromium packages..."
    
    # Check for Google Chrome Flatpak
    if flatpak list --app | grep -qi "chrome"; then
        CHROMIUM_ID=$(flatpak list --app | grep -i chrome | awk '{print $1}' | head -1)
        echo "✅ Found: $CHROMIUM_ID"
    else
        echo "❌ No Chromium/Chrome Flatpak found"
        echo "   If using system Chromium, permissions should work automatically"
        exit 1
    fi
fi

echo ""
echo "📦 Granting PipeWire permissions to: $CHROMIUM_ID"
echo ""

# Grant PipeWire portal access
flatpak override --user --talk-name=org.freedesktop.portal.PipeWire "$CHROMIUM_ID"

# Also grant access to the session bus (needed for PipeWire)
flatpak override --user --socket=session-bus "$CHROMIUM_ID"

echo ""
echo "✅ Permissions granted!"
echo ""
echo "Next steps:"
echo "  1. Enable PipeWire in Chromium:"
echo "     - Open: chrome://flags/#enable-webrtc-pipewire-capturer"
echo "     - Set to 'Enabled'"
echo "     - Restart Chromium"
echo ""
echo "  2. Start camfx:"
echo "     camfx blur --name 'camfx'"
echo ""
echo "  3. Check camera in Chromium:"
echo "     - Open: chrome://settings/content/camera"
echo "     - Look for 'camfx' in the list"
echo ""
echo "============================================================"

