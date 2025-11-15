camfx
=====

A lightweight, modular camera video enhancement middleware for Linux that provides background blur and basic background replacement, outputting to a virtual camera via PipeWire for use with video apps.

Features
--------
- Real-time person segmentation using MediaPipe
- Background blur with adjustable strength
- Background replacement with static images
- Live preview window for testing effects
- CLI with device selection, resolution, FPS options
- Works on Wayland and X11

Status
------
- ✅ Background blur and replacement: Working
- ✅ Preview mode: Working
- ✅ PipeWire virtual camera: Technically working (pipeline reaches PLAYING state)
- ⚠️ Application compatibility: Limited (see Known Limitations below)
  - PipeWire sources created but not visible to most apps
  - Most apps need V4L2 devices, not PipeWire sources
  - v4l2loopback still required for broad compatibility

Prerequisites
-------------
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

Installation
------------
```bash
# 1) Clone the repository (if not already done)
git clone <repository-url>
cd camfx

# 2) Create and activate virtual environment (recommended)
python3 -m venv .venv
source .venv/bin/activate

# 3) Install package in editable mode
pip install -U pip wheel
pip install -e .
```

Quickstart
----------
```bash
# Run with background blur
camfx blur --strength 25 --preview

# Or run with background replacement
camfx replace --image /path/to/background.jpg --preview
```

CLI Reference
-------------
```bash
# Background blur
camfx blur --strength 25 --input 0 --width 1280 --height 720 --fps 30 --preview

# Background replacement
camfx replace --image /path/to/background.jpg --input 0 --width 1280 --height 720 --fps 30 --preview

# List available camera devices
camfx list-devices

# Preview-only (no virtual camera) for debugging
camfx blur --input 0 --strength 25 --preview --no-virtual

# Custom virtual camera name (spaces and special characters supported)
camfx blur --strength 25 --name "My Virtual Camera"

# Note: --strength must be an odd number (3, 5, 7, ...). Even values are automatically adjusted.
```

Known Limitations
-----------------

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

**Note:** This project was created to explore PipeWire as a v4l2loopback alternative. While PipeWire works technically, application compatibility requires V4L2 devices. A future version may add v4l2loopback support for broader compatibility.

Troubleshooting
---------------

### PipeWire Virtual Camera

- **PipeWire not detected**: Ensure PipeWire is installed and running:
  ```bash
  systemctl --user status pipewire
  ```
  On Fedora/GNOME, PipeWire is usually pre-installed.

- **Wireplumber not running**: The virtual camera requires wireplumber (PipeWire session manager) to be running:
  ```bash
  systemctl --user start wireplumber
  systemctl --user enable wireplumber  # Enable on login
  systemctl --user status wireplumber
  ```
  If wireplumber is not running, you'll see a timeout error and the pipeline will be stuck in PAUSED state.

- **GStreamer errors**: Ensure GStreamer and plugins are installed:
  ```bash
  # Fedora
  sudo dnf install gstreamer1 gstreamer1-plugins-base gstreamer1-plugins-good
  
  # Ubuntu/Debian
  sudo apt install gstreamer1.0-plugins-base gstreamer1.0-plugins-good
  ```

- **Virtual camera not appearing in apps**: This is expected. See "Known Limitations" above. The PipeWire source is created but not visible to most applications. Use `--preview` mode to test effects, or install v4l2loopback for application compatibility.

- **Chromium/Chrome cannot see the camera**: Check docs/chromium-compatibility-findings.md 

- **Pipeline stuck in PAUSED state**: This usually means wireplumber is not running. Start it with:
  ```bash
  systemctl --user start wireplumber
  ```

### General

- **Preview window does not appear**: Try `--no-virtual` to isolate the preview, and verify input index with `camfx list-devices`.

- **Strength value errors**: The `--strength` parameter must be a positive odd integer (3, 5, 7, ...). Even values are automatically adjusted to the next odd number with a warning.

- **Physical camera shows black in other apps**: Expected when camfx is running. OpenCV locks the camera. Other apps should use the virtual camera (requires v4l2loopback for compatibility).

Examples
--------
See the `examples/` directory for programmatic usage examples.

Development Notes
-----------------
- This project was created to explore PipeWire as a v4l2loopback alternative
- PipeWire virtual sources work technically but lack broad application compatibility
- Preview mode works well for testing and demonstrating effects
- Future versions may add v4l2loopback backend for application compatibility
- This project is entirely vibe coded

Contributing
------------
Contributions welcome! Areas for improvement:
- Add v4l2loopback backend for broad application compatibility
- Improve virtual camera detection and registration
- Add more effects (color grading, filters, etc.)
- Performance optimizations

License
-------
MIT License - see [LICENSE](LICENSE) file for details.


