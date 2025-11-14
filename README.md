camfx
=====

A lightweight, modular camera video enhancement middleware for Linux that provides background blur and basic background replacement, outputting to a virtual camera via PipeWire for use with video apps.

Features
--------
- Background blur with adjustable strength (odd kernel sizes, auto-adjusted if even)
- Basic background replacement with a static image
- CLI with input device selection, resolution, FPS, and optional preview window
- PipeWire virtual camera (no kernel module required)
- Custom virtual camera naming support
- Automatic wireplumber availability detection

Status
------
- Background blur, size options and background replacement are working fine
- Preview mode is working fine
- Virtual Cam is not working - `Pipeline is stuck in PAUSED state and cannot transition to PLAYING.` I need to work on it.

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

Troubleshooting
---------------
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

- **Virtual camera not appearing in apps**: Check if PipeWire source is created:
  ```bash
  pw-cli list-sources | grep camfx
  ```
  If the source doesn't appear, check that wireplumber is running (see above).

- **Pipeline stuck in PAUSED state**: This usually means wireplumber is not running. Start it with:
  ```bash
  systemctl --user start wireplumber
  ```

- **Preview window does not appear**: Try `--no-virtual` to isolate the preview, and verify input index with `camfx list-devices`.

- **Strength value errors**: The `--strength` parameter must be a positive odd integer (3, 5, 7, ...). Even values are automatically adjusted to the next odd number with a warning.

Examples
--------
See the `examples/` directory for programmatic usage examples.

Notes
-----
- This project in entirely vibe coded.

License
-------
MIT License - see [LICENSE](LICENSE) file for details.


