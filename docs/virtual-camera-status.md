# Virtual Camera Status and Limitations

## Current Implementation

camfx creates a virtual camera using PipeWire's `pipewiresink` GStreamer element with `media.class=Video/Source`.

### What Works

✅ **Technical Implementation**
- GStreamer pipeline successfully created
- Pipeline reaches PLAYING state
- Frames are being sent to PipeWire
- PipeWire source node is created
- No kernel modules required

✅ **Preview Mode**
- Live preview window works perfectly
- Real-time video processing and display
- Background blur and replacement effects work

### What Doesn't Work

❌ **Application Compatibility**
- Virtual camera is NOT visible to most applications
- Zoom, Teams, Discord, Slack don't see it
- Most browsers don't see it (without special configuration)
- Standard camera apps expecting `/dev/video*` don't see it

## Why Applications Don't See It

### The Problem

**PipeWire Sources ≠ V4L2 Devices**

1. **What camfx creates:** A PipeWire source node (`media.class=Video/Source`)
2. **What apps expect:** V4L2 video devices (`/dev/video0`, `/dev/video1`, etc.)
3. **The gap:** PipeWire sources are NOT automatically exposed as V4L2 devices

### Application Types

**PipeWire-Native Applications (Work):**
- OBS Studio (can use PipeWire sources directly)
- Some browsers with special configuration:
  - Firefox: Set `media.webrtc.camera.allow-pipewire=true` in `about:config`
  - Chrome/Chromium: Launch with `--enable-features=WebRTCPipeWireCapturer`

**V4L2-Expecting Applications (Don't Work):**
- Video conferencing: Zoom, Teams, Discord, Slack, Google Meet
- Most browsers by default
- Standard camera applications (Cheese, etc.)
- Recording software

## Verification

You can verify the virtual camera is created in PipeWire:

```bash
# Check PipeWire nodes
pw-dump | python3 -c "
import sys, json
data = json.load(sys.stdin)
nodes = [obj for obj in data if obj.get('type') == 'PipeWire:Interface:Node']
video_sources = [n for n in nodes if n.get('info', {}).get('props', {}).get('media.class') == 'Video/Source']
for n in video_sources:
    props = n.get('info', {}).get('props', {})
    print(f\"Video/Source: {props.get('media.name', 'unnamed')}\")
"

# Check with wpctl
wpctl status
```

The source appears in PipeWire but **not** in:
```bash
v4l2-ctl --list-devices  # Won't show PipeWire sources
ls /dev/video*           # Won't show PipeWire sources
```

## Solutions

### Option 1: Use v4l2loopback (Recommended for Compatibility)

Install and configure v4l2loopback:

```bash
# Install
sudo dnf install v4l2loopback akmod-v4l2loopback  # Fedora
sudo apt install v4l2loopback-dkms                # Ubuntu

# Load module
sudo modprobe v4l2loopback video_nr=10 card_label="camfx"

# Verify
v4l2-ctl --list-devices
```

Then modify camfx to write to `/dev/video10` instead of PipeWire.

**Pros:**
- ✅ Works with ALL applications
- ✅ Standard V4L2 interface
- ✅ Proven solution

**Cons:**
- ❌ Requires kernel module
- ❌ Needs root to load module
- ❌ Can have stability issues with some kernels

### Option 2: PipeWire-Only with v4l2 Camera Module

PipeWire has a `v4l2` camera module that can bridge PipeWire sources to V4L2, but:
- Still requires v4l2loopback underneath
- More complex configuration
- Not a true "no kernel module" solution

### Option 3: Accept Limited Compatibility

Keep current PipeWire-only approach and document:
- Works for preview/testing
- Works for PipeWire-native apps (limited)
- Recommend v4l2loopback for production use

## Diagnostic Tools

Created diagnostic script in `scripts/`:

**`collect_diagnostics.sh`** - Comprehensive system diagnostics
- PipeWire, Wireplumber, GStreamer status
- Package versions and configuration checks
- Service logs and status
- Python dependencies
- Environment variables

Usage:
```bash
# Run diagnostics and save to file
./scripts/collect_diagnostics.sh

# Or specify output file
./scripts/collect_diagnostics.sh my_diagnostics.txt
```

This script is useful for:
- Troubleshooting PipeWire/Wireplumber issues
- Creating bug reports
- Documenting system configuration
- Verifying all dependencies are installed

## Recommendations

### For Users

**Current Best Practice:**
1. Use `--preview` mode to test and demonstrate effects
2. If you need virtual camera in applications:
   - Install v4l2loopback
   - Use OBS Studio with PipeWire support
   - Or wait for v4l2loopback backend in camfx

**Command Examples:**
```bash
# Best for testing/demonstration
camfx blur --strength 25 --preview

# See effect in real-time
camfx replace --image ~/wallpaper.jpg --preview

# Experiment with different strengths
camfx blur --strength 15 --preview  # Subtle
camfx blur --strength 45 --preview  # Strong
```

### For Development

**Priority Tasks:**
1. Add v4l2loopback backend (fallback when available)
2. Auto-detect available backends (PipeWire vs v4l2loopback)
3. Improve documentation with application-specific guides
4. Add backend selection CLI flag: `--backend [pipewire|v4l2loopback]`

**Backend Detection Logic:**
```python
def detect_backends():
    backends = []
    
    # Check for v4l2loopback
    if os.path.exists('/dev/video10') and is_v4l2loopback('/dev/video10'):
        backends.append('v4l2loopback')
    
    # Check for PipeWire
    if is_pipewire_available():
        backends.append('pipewire')
    
    return backends
```

## Conclusion

The PipeWire implementation is **technically successful** but has **limited practical use** due to application compatibility.

**Current State:**
- ✅ Works as a video effect preview tool
- ✅ Demonstrates MediaPipe segmentation
- ✅ Shows PipeWire virtual camera creation
- ❌ Not usable with most video conferencing apps

**Path Forward:**
- Document limitations clearly
- Add v4l2loopback backend for compatibility
- Keep PipeWire option for PipeWire-native workflows
- Make backend selection automatic or configurable

