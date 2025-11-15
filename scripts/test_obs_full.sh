#!/bin/bash
# Test script to validate OBS Studio virtual camera solution

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║  OBS Studio Virtual Camera Solution - Test Script         ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Track test results
TESTS_PASSED=0
TESTS_FAILED=0
WARNINGS=0

# Helper functions
pass() {
    echo -e "${GREEN}✓${NC} $1"
    ((TESTS_PASSED++))
}

fail() {
    echo -e "${RED}✗${NC} $1"
    ((TESTS_FAILED++))
}

warn() {
    echo -e "${YELLOW}⚠${NC} $1"
    ((WARNINGS++))
}

info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

# Test 1: Check if OBS Studio is installed
echo -e "\n${BLUE}[Test 1]${NC} Checking OBS Studio installation..."
if command -v obs &> /dev/null; then
    OBS_VERSION=$(obs --version 2>&1 | head -1 || echo "unknown")
    pass "OBS Studio is installed: $OBS_VERSION"
    OBS_INSTALLED=true
else
    fail "OBS Studio is NOT installed"
    echo "      Install with: sudo dnf install obs-studio"
    OBS_INSTALLED=false
fi

# Test 2: Check for OBS plugins
echo -e "\n${BLUE}[Test 2]${NC} Checking OBS plugins directory..."
if [ -d "/usr/lib64/obs-plugins" ] || [ -d "/usr/lib/obs-plugins" ] || [ -d "$HOME/.config/obs-studio/plugins" ]; then
    pass "OBS plugins directory exists"
    ls /usr/lib64/obs-plugins/ 2>/dev/null | grep -q "linux-pipewire" && \
        pass "   PipeWire plugin found" || \
        warn "   PipeWire plugin may not be available"
else
    warn "OBS plugins directory not found (this may be okay)"
fi

# Test 3: Check PipeWire is running
echo -e "\n${BLUE}[Test 3]${NC} Checking PipeWire..."
if pgrep -x pipewire > /dev/null; then
    pass "PipeWire is running"
    PIPEWIRE_VERSION=$(pipewire --version 2>&1 | head -1 || echo "unknown")
    info "   Version: $PIPEWIRE_VERSION"
else
    fail "PipeWire is NOT running"
    echo "      Start with: systemctl --user start pipewire"
fi

# Test 4: Check WirePlumber
echo -e "\n${BLUE}[Test 4]${NC} Checking WirePlumber..."
if pgrep -x wireplumber > /dev/null; then
    pass "WirePlumber is running"
else
    fail "WirePlumber is NOT running"
    echo "      Start with: systemctl --user start wireplumber"
fi

# Test 5: Check camfx installation
echo -e "\n${BLUE}[Test 5]${NC} Checking camfx installation..."
cd "$(dirname "$0")"
if [ -d ".venv" ]; then
    source .venv/bin/activate
    if command -v camfx &> /dev/null; then
        pass "camfx is installed in venv"
    else
        fail "camfx command not found"
        echo "      Install with: pip install -e ."
    fi
else
    warn "Virtual environment not found"
    info "   Looking for system-wide camfx..."
    if command -v camfx &> /dev/null; then
        pass "camfx is installed system-wide"
    else
        fail "camfx not found"
    fi
fi

# Test 6: Test camfx can start (quick test)
echo -e "\n${BLUE}[Test 6]${NC} Testing if camfx can start..."
if command -v camfx &> /dev/null; then
    # Try to get help text (doesn't start camera)
    if camfx --help &> /dev/null; then
        pass "camfx command works"
    else
        fail "camfx command fails"
    fi
else
    fail "Cannot test camfx - not installed"
fi

# Test 7: Check for v4l2loopback conflicts
echo -e "\n${BLUE}[Test 7]${NC} Checking for v4l2loopback conflicts..."
if lsmod | grep -q v4l2loopback; then
    warn "v4l2loopback module is loaded"
    info "   OBS solution doesn't need this module"
    info "   Consider removing: sudo modprobe -r v4l2loopback"
    if [ -e /dev/video10 ]; then
        warn "   /dev/video10 exists from v4l2loopback"
    fi
else
    pass "No v4l2loopback module loaded (good!)"
fi

# Test 8: Check GStreamer installation
echo -e "\n${BLUE}[Test 8]${NC} Checking GStreamer..."
if command -v gst-launch-1.0 &> /dev/null; then
    pass "GStreamer is installed"
    GST_VERSION=$(gst-launch-1.0 --version 2>&1 | grep version | head -1)
    info "   $GST_VERSION"
else
    fail "GStreamer not found"
fi

# Test 9: Check if we can list PipeWire nodes
echo -e "\n${BLUE}[Test 9]${NC} Testing PipeWire node listing..."
if command -v pw-cli &> /dev/null; then
    pass "pw-cli is available"
    NODE_COUNT=$(pw-cli ls Node 2>/dev/null | grep -c "id" || echo "0")
    info "   Found $NODE_COUNT PipeWire nodes"
else
    warn "pw-cli not found (optional tool)"
fi

# Test 10: Check browser installations
echo -e "\n${BLUE}[Test 10]${NC} Checking browser installations..."
BROWSERS_FOUND=0
if command -v chromium-browser &> /dev/null || command -v chromium &> /dev/null; then
    pass "Chromium is installed (native PipeWire support)"
    ((BROWSERS_FOUND++))
fi
if command -v google-chrome &> /dev/null; then
    pass "Google Chrome is installed (native PipeWire support)"
    ((BROWSERS_FOUND++))
fi
if command -v firefox &> /dev/null; then
    info "Firefox is installed (needs OBS bridge)"
    ((BROWSERS_FOUND++))
fi
if [ $BROWSERS_FOUND -eq 0 ]; then
    warn "No browsers found"
fi

# Test 11: Interactive test (optional)
echo -e "\n${BLUE}[Test 11]${NC} Interactive PipeWire camera test..."
if [ "$OBS_INSTALLED" = true ] && [ "$1" != "--skip-interactive" ]; then
    echo ""
    read -p "Start camfx and test with OBS? This will open OBS. (y/N) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        info "Starting camfx in background..."
        
        # Start camfx in background
        if command -v camfx &> /dev/null; then
            camfx blur --preview &
            CAMFX_PID=$!
            
            # Wait a bit for camfx to start
            sleep 3
            
            # Check if camfx is running
            if kill -0 $CAMFX_PID 2>/dev/null; then
                pass "camfx started successfully (PID: $CAMFX_PID)"
                
                # Check if PipeWire camera appeared
                if command -v pw-cli &> /dev/null; then
                    sleep 2
                    if pw-cli ls Node 2>/dev/null | grep -i camfx &> /dev/null; then
                        pass "PipeWire 'camfx' node detected!"
                        
                        echo ""
                        echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"
                        echo -e "${GREEN}camfx is running with PipeWire camera!${NC}"
                        echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"
                        echo ""
                        echo "Next steps:"
                        echo "  1. OBS will open now"
                        echo "  2. Click '+' under Sources"
                        echo "  3. Add 'PipeWire Capture' (or 'Screen Capture' if no PipeWire option)"
                        echo "  4. Select 'camfx' from the camera list"
                        echo "  5. Click 'Start Virtual Camera' button"
                        echo "  6. Check if virtual camera appears"
                        echo ""
                        read -p "Press Enter to open OBS Studio..."
                        
                        obs &
                        OBS_PID=$!
                        
                        echo ""
                        echo "Waiting for you to test OBS..."
                        echo "(Press Ctrl+C when done testing)"
                        
                        # Wait for user to test
                        sleep 5
                        
                        echo ""
                        echo "Checking for OBS virtual camera device..."
                        sleep 2
                        
                        # Check if OBS created a virtual camera
                        FOUND_OBS_CAMERA=false
                        for dev in /dev/video*; do
                            if [ -e "$dev" ]; then
                                NAME=$(cat /sys/class/video4linux/$(basename $dev)/name 2>/dev/null || echo "")
                                if echo "$NAME" | grep -qi "obs"; then
                                    pass "OBS virtual camera found: $dev ($NAME)"
                                    FOUND_OBS_CAMERA=true
                                fi
                            fi
                        done
                        
                        if [ "$FOUND_OBS_CAMERA" = false ]; then
                            warn "No OBS virtual camera detected yet"
                            info "   Make sure you clicked 'Start Virtual Camera' in OBS"
                        fi
                        
                        echo ""
                        read -p "Press Enter to cleanup and stop processes..."
                        
                        # Cleanup
                        kill $CAMFX_PID 2>/dev/null || true
                        kill $OBS_PID 2>/dev/null || true
                        
                    else
                        warn "PipeWire 'camfx' node not detected"
                        kill $CAMFX_PID 2>/dev/null || true
                    fi
                fi
            else
                fail "camfx failed to start"
            fi
        fi
    else
        info "Skipped interactive test"
    fi
else
    info "Skipped (use without --skip-interactive to enable)"
fi

# Summary
echo ""
echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║  Test Summary                                              ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${GREEN}Passed:${NC}   $TESTS_PASSED"
echo -e "${RED}Failed:${NC}   $TESTS_FAILED"
echo -e "${YELLOW}Warnings:${NC} $WARNINGS"
echo ""

# Final assessment
if [ $TESTS_FAILED -eq 0 ]; then
    echo -e "${GREEN}✓ All critical tests passed!${NC}"
    echo ""
    echo "The OBS solution should work. Here's how to use it:"
    echo ""
    echo "1. Start camfx:"
    echo "   $ camfx blur"
    echo ""
    echo "2. Open OBS Studio:"
    echo "   $ obs"
    echo ""
    echo "3. In OBS:"
    echo "   - Click '+' under Sources"
    echo "   - Add 'PipeWire Capture'"
    echo "   - Select 'camfx' camera"
    echo "   - Click 'Start Virtual Camera'"
    echo ""
    echo "4. Open Firefox/Google Meet:"
    echo "   - Select 'OBS Virtual Camera' as your camera"
    echo "   - You should see your camfx effects!"
    echo ""
else
    echo -e "${RED}✗ Some tests failed${NC}"
    echo ""
    echo "Please fix the failed tests before proceeding."
    echo ""
    if [ "$OBS_INSTALLED" = false ]; then
        echo "Install OBS Studio:"
        echo "  sudo dnf install obs-studio obs-studio-plugins"
        echo ""
    fi
fi

exit $TESTS_FAILED

