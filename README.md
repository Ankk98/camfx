# camfx

A lightweight, modular camera video enhancement middleware for Linux that provides real-time effects with live switching and effect chaining, outputting to a virtual camera via PipeWire.

## Features

- **Real-time effects**: Background blur, background replacement, brightness adjustment, face beautification, auto-framing, and eye gaze correction
- **Effect chaining**: Apply multiple effects in sequence (e.g., blur + brightness + beautify)
- **Live effect switching**: Change effects at runtime without restarting (via D-Bus)
- **On-demand camera**: Camera only activates when virtual source is being consumed (lazy camera mode)
- **Live preview**: Preview the output from a running camfx instance
- **Person segmentation**: Real-time person segmentation using MediaPipe
- **CLI with device selection**: Resolution, FPS, and camera selection options
- **Works on Wayland and X11**

## Status

- ✅ All effects: Working
- ✅ Effect chaining: Working
- ✅ Live effect switching: Working (D-Bus)
- ✅ Preview mode: Working
- ✅ PipeWire virtual camera: Working
- ✅ Lazy camera mode: Working
- ⚠️ Application compatibility: Limited (see Known Limitations below)
- Preview functionality: Not working, preview hangs with black output

## Prerequisites

- Linux with PipeWire (default on Fedora, GNOME, and modern distributions)
- Python 3.10+ (uses modern type hints)
- GStreamer and GStreamer plugins (usually pre-installed with PipeWire)
- Wireplumber (PipeWire session manager) - usually pre-installed with PipeWire

**System packages (Fedora):**
```bash
sudo dnf install python3-gobject gstreamer1 gstreamer1-plugins-base gstreamer1-plugins-good pipewire
```

**System packages (Ubuntu/Debian):**
```bash
sudo apt install python3-gi python3-gi-cairo gir1.2-gstreamer-1.0 gstreamer1.0-plugins-base gstreamer1.0-plugins-good pipewire
```

## Installation

```bash
# 1) Clone the repository
git clone <repository-url>
cd camfx

# 2) Create and activate virtual environment (recommended)
python3 -m venv .venv
source .venv/bin/activate

# 3) Install package in editable mode
pip install -U pip wheel
pip install -e .
```

## Quickstart

```bash
# Start virtual camera with blur effect
camfx start --effect blur --strength 25 --dbus

# In another terminal, preview the output
camfx preview

# Change effect at runtime (requires --dbus flag)
camfx set-effect --effect brightness --brightness 10

# Add another effect to the chain
camfx add-effect --effect beautify --smoothness 5

# Check current effects
camfx get-effects
```

## CLI Reference

### Start Virtual Camera

```bash
# Start with initial effect
camfx start --effect blur --strength 25

# Start with D-Bus enabled for runtime control
camfx start --effect blur --strength 25 --dbus

# Start with lazy camera (only activates when source is in use)
camfx start --effect blur --strength 25 --lazy-camera --dbus

# Start without initial effect (can add effects via D-Bus)
camfx start --dbus

# Custom resolution and FPS
camfx start --effect blur --width 1280 --height 720 --fps 30

# Custom virtual camera name
camfx start --effect blur --name "My Virtual Camera"
```

### Preview

```bash
# Preview output from running camfx instance
camfx preview

# Preview specific virtual camera
camfx preview --name "My Virtual Camera"

# Fallback: Preview camera directly with effect (if camfx not running)
camfx preview --effect blur --strength 25
```

### Runtime Effect Control (D-Bus)

These commands require `camfx start --dbus` to be running:

```bash
# Replace all effects with a new one
camfx set-effect --effect brightness --brightness 10

# Add effect to chain
camfx add-effect --effect beautify --smoothness 5

# Get current effect chain
camfx get-effects
```

### Utility Commands

```bash
# List available camera devices
camfx list-devices
```

## Available Effects

- **blur**: Background blur with adjustable strength
  - `--strength`: Blur strength (must be odd: 3, 5, 7, ...)
  
- **replace**: Replace background with static image
  - Requires background image (not yet supported via CLI, use D-Bus)
  
- **brightness**: Adjust brightness and contrast
  - `--brightness`: Brightness adjustment (-100 to 100)
  - `--contrast`: Contrast multiplier (0.5 to 2.0)
  - `--face-only`: Apply only to face region (requires segmentation)
  
- **beautify**: Face beautification and skin smoothing
  - `--smoothness`: Smoothing strength (1-15)
  
- **autoframe**: Auto-frame and center on face
  - `--padding`: Padding around face (0.0-1.0)
  - `--min-zoom`: Minimum zoom level
  - `--max-zoom`: Maximum zoom level
  
- **gaze-correct**: Correct eye gaze to appear looking at camera
  - `--strength`: Correction strength (0.0-1.0)

## Effect Chaining

You can chain multiple effects together:

```bash
# Start with blur
camfx start --effect blur --strength 25 --dbus

# Add brightness adjustment
camfx add-effect --effect brightness --brightness 10

# Add beautification
camfx add-effect --effect beautify --smoothness 5

# Check the chain
camfx get-effects
# Output:
# Current effect chain (3 effects):
#   0: blur (BackgroundBlur) - strength=25
#   1: brightness (BrightnessAdjustment) - brightness=10
#   2: beautify (FaceBeautification) - smoothness=5
```

Effects are applied in the order they were added to the chain.

## Lazy Camera Mode

With `--lazy-camera`, the camera only activates when the virtual source is being consumed:

```bash
camfx start --effect blur --lazy-camera --dbus
```

- Camera stays off when no application is using the virtual camera
- Automatically starts when an application connects
- Automatically stops when all applications disconnect
- Saves resources and privacy

## Known Limitations

### Virtual Camera Compatibility

**Current Status:** The virtual camera creates a PipeWire source but is **not visible to most applications**.

**Why?** Most applications (Zoom, Teams, Google Meet, browsers, etc.) expect V4L2 devices (`/dev/video*`), not PipeWire sources. PipeWire virtual sources are NOT automatically exposed as V4L2 devices.

**What Works:**
- ✅ Preview window (always works)
- ✅ PipeWire-native applications (limited: OBS Studio, some browsers with special configuration)

**What Doesn't Work:**
- ❌ Most video conferencing applications (Zoom, Teams, Discord, Slack, etc.)
- ❌ Most browsers by default (Chrome, Firefox without special flags)
- ❌ Standard camera applications expecting `/dev/video*` devices

**Workaround for Broad Compatibility:**

To make the virtual camera visible to all applications, v4l2loopback kernel module is still required:

```bash
# Install v4l2loopback
sudo dnf install v4l2loopback akmod-v4l2loopback  # Fedora
# OR
sudo apt install v4l2loopback-dkms              # Ubuntu/Debian

# Load the module
sudo modprobe v4l2loopback video_nr=10 card_label="camfx Virtual Camera"

# Verify it's loaded
v4l2-ctl --list-devices
```

## Troubleshooting

### PipeWire Virtual Camera

- **PipeWire not detected**: Ensure PipeWire is installed and running:
  ```bash
  systemctl --user status pipewire
  ```

- **Wireplumber not running**: The virtual camera requires wireplumber:
  ```bash
  systemctl --user start wireplumber
  systemctl --user enable wireplumber
  systemctl --user status wireplumber
  ```

- **Virtual camera not appearing in apps**: This is expected. See "Known Limitations" above.

### D-Bus Control

- **D-Bus commands fail**: Make sure `camfx start --dbus` is running
- **D-Bus not available**: Install `dbus-python`:
  ```bash
  pip install dbus-python
  ```

### Camera Issues

- **Camera in use error**: Another process is using the camera. Close other camera applications or use a different camera index.
- **Preview shows black**: Make sure `camfx start` is running if previewing virtual camera output.

### General

- **Preview window does not appear**: Try previewing camera directly: `camfx preview --effect blur`
- **Strength value errors**: The `--strength` parameter must be a positive odd integer (3, 5, 7, ...)

## Examples

### Basic Usage

```bash
# Terminal 1: Start virtual camera
camfx start --effect blur --strength 25 --dbus

# Terminal 2: Preview output
camfx preview

# Terminal 3: Change effect
camfx set-effect --effect brightness --brightness 10
```

### Effect Chaining

```bash
# Start with blur
camfx start --effect blur --strength 25 --dbus

# Add brightness
camfx add-effect --effect brightness --brightness 10

# Add beautify
camfx add-effect --effect beautify --smoothness 5

# View chain
camfx get-effects
```

### Lazy Camera

```bash
# Start with lazy camera - camera only activates when source is used
camfx start --effect blur --lazy-camera --dbus

# Connect an application to the virtual camera
# Camera will automatically start

# Disconnect all applications
# Camera will automatically stop
```

## Testing

Run the test suite:

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run specific test file
pytest tests/test_effect_chaining.py
```

## Development Notes

- Effect chaining supports applying multiple effects in sequence
- D-Bus interface enables runtime effect control
- Lazy camera mode saves resources by only activating when needed
- Preview command can show output from running camfx instance
- All effects are thread-safe and can be changed at runtime

## Contributing

Contributions welcome! Areas for improvement:
- Add v4l2loopback backend for broad application compatibility
- Add more effects (color grading, filters, etc.)
- Performance optimizations
- GUI control panel using D-Bus interface

## License

MIT License - see [LICENSE](LICENSE) file for details.
