# camfx

A lightweight, modular camera video enhancement middleware for Linux that provides real-time effects with live switching and effect chaining, outputting to a universal V4L2 virtual camera (/dev/videoX) via `v4l2loopback` + FFmpeg. Includes both CLI and GTK GUI interfaces for effect management.

## Features

- **Real-time effects**: Background blur, background replacement, brightness adjustment, face beautification, auto-framing, and eye gaze correction
- **Effect chaining**: Apply multiple effects in sequence (e.g., blur + brightness + beautify)
- **Live effect switching**: Change effects at runtime without restarting (via D-Bus)
- **GTK GUI**: Graphical interface for managing effects and adjusting parameters
- **Explicit camera control**: Camera can be started/stopped via D-Bus or CLI commands
- **Live preview**: Preview the output from a running camfx instance (CLI and GUI)
- **Person segmentation**: Real-time person segmentation using MediaPipe
- **CLI with device selection**: Resolution, FPS, and camera selection options
- **Works on Wayland and X11**

## Status

- ✅ All effects: Working
- ✅ Effect chaining: Working
- ✅ Live effect switching: Working (D-Bus)
- ✅ V4L2 loopback virtual camera: Working (requires v4l2loopback + /dev/videoX)
- ✅ Camera control: Working (start/stop via D-Bus or CLI)
- ✅ GTK GUI: Working (effect management, parameter controls, camera toggle)
- ⚠️ Application compatibility: Limited (see Known Limitations below)
- ⚠️ GUI Live Preview: Not working (pipeline stuck in PAUSED state, needs investigation)
- ⚠️ Preview mode using cli: Not Working

## Prerequisites

- FFmpeg installed (`ffmpeg`)
- v4l2loopback kernel module loaded (creates `/dev/videoX`)
- Python 3.12 (see `.python-version`)
 - MediaPipe (Tasks API) installed for ML effects (`pip install mediapipe`)

Optional (GUI):
- GTK4 + PyGObject (see “Optional Features” below)

Optional (D-Bus control + live effect switching):
- D-Bus Python bindings (`dbus-python`) and PyGObject

## Installation

```bash
# 1) Clone the repository
git clone <repository-url>
cd camfx

# 2) Create and activate virtual environment (recommended)
# This project targets Python 3.12 (see .python-version).
python3.12 -m venv .venv
source .venv/bin/activate

# 3) Install dependencies + package in editable mode
python -m pip install -U pip wheel setuptools
pip install -r requirements.txt
pip install -e .
```

Optional extras:
- GUI: `pip install -e ".[gui]"`
- D-Bus live control: `pip install -e ".[dbus]"`

## ML Models (MediaPipe Tasks)

camfx uses MediaPipe Tasks models for segmentation/landmarks. On first use it will download:
- selfie segmenter model (`.tflite`)
- face landmarker model (`.task`)

Models are cached under `~/.cache/camfx/models` by default.
Override with:
- `CAMFX_MODELS_DIR=/path/to/models`

Prefetch models explicitly (recommended for offline use):

```bash
camfx models-download
```

Optional: if you have `uv` installed, this can be even simpler/reliable:
```bash
cd /home/ankk98/repos/camfx
uv venv --python 3.12
source .venv/bin/activate
uv pip install -r requirements.txt
uv pip install -e .
```

## Quickstart

```bash
# v4l2loopback + FFmpeg must be available first.

# Option A (simplest): start output immediately (no D-Bus live switching)
camfx start --name camfx
camfx preview-virtual --name camfx

# Option B: enable D-Bus for live effect switching + camera toggle
camfx start --dbus --name camfx
camfx set-effect --effect blur --strength 25
camfx camera-start

# Live update effects (requires --dbus flag)
camfx set-effect --effect brightness --brightness 10

# Stop camera
camfx camera-stop

# Check camera status
camfx camera-status
```

## CLI Reference

### Start Virtual Camera

```bash
# Start virtual camera daemon (camera is OFF by default)
camfx start --dbus

# Custom resolution and FPS
camfx start --width 1280 --height 720 --fps 30

# Custom virtual camera name
camfx start --name "My Virtual Camera"
```

**Note**: Use `set-effect` or `add-effect` commands to configure effects after starting the daemon.

**Note**: The camera is **OFF by default**. You must start it explicitly using:
- `camfx camera-start` (CLI command)
- Camera toggle button in the GUI
- D-Bus `StartCamera()` method

### Preview

```bash
# Preview output from running camfx instance (v4l2loopback device)
camfx preview-virtual --name camfx

# Preview a specific virtual camera card_label
camfx preview-virtual --name "My Virtual Camera"

# Preview physical camera directly (bypasses v4l2loopback)
camfx preview-camera --input 0
```

### Camera Control

These commands require `camfx start --dbus` to be running:

```bash
# Start the camera
camfx camera-start

# Stop the camera
camfx camera-stop

# Check camera status
camfx camera-status
```

**Note**:
- If you start with `--dbus`, the camera starts OFF until `camfx camera-start`.
- If you start without `--dbus`, the camera starts immediately.

### Runtime Effect Control (D-Bus)

These commands require `camfx start --dbus` to be running:

```bash
# Replace all effects with a new one
camfx set-effect --effect brightness --brightness 10

# Add effect to chain
camfx add-effect --effect beautify --smoothness 5

# Update an effect (adding same type updates it, doesn't duplicate)
camfx add-effect --effect brightness --brightness 15

# Remove an effect by type
camfx remove-effect --effect blur

# Or remove by index (from get-effects output)
camfx remove-effect --index 0

# Get current effect chain
camfx get-effects
```

### GTK GUI

```bash
# Launch the GTK control panel
camfx gui
```

The GUI provides:
- **Effect Management**: Add, remove, and reorder effects in the chain
- **Parameter Controls**: Adjust effect parameters with sliders and controls
- **Camera Control**: Toggle camera on/off with a button
- **Live Preview Toggle**: Enable/disable live preview display
- **Live Preview**: Preview the virtual camera output (⚠️ Currently not working - see Status)
- **Effect Chain Display**: View all active effects with their current parameters

**Note**: The GUI requires `camfx start --dbus` to be running for full functionality. The live preview feature is currently not working (pipeline stuck in PAUSED state) and needs investigation.

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

You can chain multiple effects together. Each effect type can only appear once in the chain - adding the same effect type again will update its parameters instead of creating a duplicate:

```bash
# Start daemon
camfx start --dbus

# Set initial blur effect
camfx set-effect --effect blur --strength 25

# Add brightness adjustment
camfx add-effect --effect brightness --brightness 10

# Add beautification
camfx add-effect --effect beautify --smoothness 5

# Update brightness (updates existing, doesn't duplicate)
camfx add-effect --effect brightness --brightness 15

# Check the chain
camfx get-effects
# Output:
# Current effect chain (3 effects):
#   0: blur (BackgroundBlur) - strength=25
#   1: brightness (BrightnessAdjustment) - brightness=15  # Updated!
#   2: beautify (FaceBeautification) - smoothness=5

# Remove an effect
camfx remove-effect --effect blur

# Check again
camfx get-effects
# Output:
# Current effect chain (2 effects):
#   0: brightness (BrightnessAdjustment) - brightness=15
#   1: beautify (FaceBeautification) - smoothness=5
```

Effects are applied in the order they appear in the chain. When you update an effect, it maintains its position in the chain.

## Camera Control

The camera is **OFF by default** when you start the daemon. You must explicitly start it:

```bash
# Start the daemon
camfx start --dbus

# Set effect
camfx set-effect --effect blur --strength 25

# Start the camera (required for video output)
camfx camera-start

# Stop the camera
camfx camera-stop

# Check status
camfx camera-status
```

You can also control the camera via:
- **GUI**: Use the "Camera: ON/OFF" toggle button
- **D-Bus**: Call `StartCamera()` or `StopCamera()` methods
- **CLI**: Use `camera-start` and `camera-stop` commands

When the camera is off, the virtual camera outputs black frames. This saves resources and provides privacy control.

## Known Limitations

### V4L2 Loopback Compatibility

**Current Status:** camfx outputs directly to a **V4L2** virtual device (`/dev/videoX`) via `v4l2loopback`, so it should work in most apps that accept V4L2 cameras.

If an app still cannot see the camera:
- Some apps need `exclusive_caps=1` when loading `v4l2loopback`.
- Permissions/groups may prevent non-root access to `/dev/videoX`.
- The app may expect a specific pixel format; camfx streams `YUV420P` to the v4l2 device.

To load `v4l2loopback` with stable discovery (via `card_label`):

```bash
# Fedora
sudo dnf install v4l2loopback akmod-v4l2loopback

# Ubuntu/Debian
# sudo apt install v4l2loopback-dkms

# Load the module (let the kernel choose videoN)
sudo modprobe v4l2loopback exclusive_caps=1 card_label="camfx" video_nr=-1

# Verify
v4l2-ctl --list-devices
```

## Troubleshooting

### v4l2loopback

- **Virtual camera device not found**: ensure the module is loaded and a `/dev/videoX` node exists:
  ```bash
  lsmod | grep v4l2loopback
  ls -l /dev/video*
  v4l2-ctl --list-devices
  ```

- **Permissions denied opening `/dev/videoX`**: add your user to the `video` group (may require logout/login):
  ```bash
  sudo usermod -aG video "$USER"
  ```

- **App cannot open the device**: try reloading with `exclusive_caps=1` (see “V4L2 Loopback Compatibility” above).

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

- **Preview window does not appear**: try previewing the physical camera: `camfx preview-camera --input 0`
- **Strength value errors**: The `--strength` parameter must be a positive odd integer (3, 5, 7, ...)

## Examples

### Basic Usage

```bash
# Terminal 1: Start virtual camera daemon (camera is OFF by default)
camfx start --dbus

# Terminal 1: Set effect
camfx set-effect --effect blur --strength 25

# Terminal 1: Start the camera
camfx camera-start

# Terminal 2: Preview output
camfx preview-virtual --name camfx

# Terminal 3: Change effect
camfx set-effect --effect brightness --brightness 10

# Terminal 3: Stop the camera
camfx camera-stop
```

### Effect Chaining

```bash
# Start daemon
camfx start --dbus

# Set initial blur effect
camfx set-effect --effect blur --strength 25

# Add brightness
camfx add-effect --effect brightness --brightness 10

# Add beautify
camfx add-effect --effect beautify --smoothness 5

# Update brightness (updates existing, doesn't duplicate)
camfx add-effect --effect brightness --brightness 15

# Remove blur
camfx remove-effect --effect blur

# View chain
camfx get-effects
# Output:
# Current effect chain (2 effects):
#   0: brightness (BrightnessAdjustment) - brightness=15
#   1: beautify (FaceBeautification) - smoothness=5
```

### Camera Control

```bash
# Start daemon (camera is OFF by default)
camfx start --dbus

# Set effect
camfx set-effect --effect blur --strength 25

# Start the camera explicitly
camfx camera-start

# Use the virtual camera in applications
# (camera is now active and sending video)

# Stop the camera when done
camfx camera-stop
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
- D-Bus interface enables runtime effect and camera control
- Camera control is explicit - camera is OFF by default and must be started manually
- Preview command can show output from running camfx instance
- All effects are thread-safe and can be changed at runtime
- Camera can be toggled on/off via D-Bus, CLI, or GUI without restarting the daemon

## Contributing

Contributions welcome! Areas for improvement:
- Add v4l2loopback backend for broad application compatibility
- Add more effects (color grading, filters, etc.)
- Performance optimizations
- GUI control panel using D-Bus interface

## License

MIT License - see [LICENSE](LICENSE) file for details.
