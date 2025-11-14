camfx
=====

A lightweight, modular camera video enhancement middleware for Linux that provides background blur and basic background replacement, outputting to a virtual camera via PipeWire for use with video apps.

Features (MVP)
--------------
- Background blur with adjustable strength
- Basic background replacement with a static image
- CLI with input device selection, resolution, FPS, and optional preview window
- PipeWire virtual camera (no kernel module required)

Prerequisites
-------------
- Linux with PipeWire (default on Fedora, GNOME, and modern distributions)
- Python 3.9+
- GStreamer and GStreamer plugins (usually pre-installed with PipeWire)

**System packages (Fedora):**
```bash
sudo dnf install python3-gobject gstreamer1 gstreamer1-plugins-base gstreamer1-plugins-good pipewire
```

**System packages (Ubuntu/Debian):**
```bash
sudo apt install python3-gi python3-gi-cairo gir1.2-gstreamer-1.0 gstreamer1.0-plugins-base gstreamer1.0-plugins-good pipewire
```

Quickstart
----------
```bash
# 1) Create and activate virtual environment (optional but recommended)
python3 -m venv .venv
source .venv/bin/activate

# 2) Install package in editable mode
pip install -U pip wheel
pip install -e .

# 3) Run with background blur
camfx blur --strength 25 --preview

# 4) Or run with background replacement
camfx replace --image /path/to/background.jpg --preview
```

CLI Reference (MVP)
-------------------
```bash
# Background blur
camfx blur --strength 25 --input 0 --width 1280 --height 720 --fps 30 --preview

# Background replacement
camfx replace --image /path/to/background.jpg --input 0 --width 1280 --height 720 --fps 30 --preview

# List devices
camfx list-devices

# Preview-only (no virtual camera) for debugging
camfx blur --input 0 --strength 25 --preview --no-virtual

# Custom virtual camera name
camfx blur --strength 25 --name "My Virtual Camera"
```

Troubleshooting
---------------
- **PipeWire not detected**: Ensure PipeWire is installed and running:
  ```bash
  systemctl --user status pipewire
  ```
  On Fedora/GNOME, PipeWire is usually pre-installed.

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

- **Preview window does not appear**: Try `--no-virtual` to isolate the preview, and verify input index with `camfx list-devices`.

License
-------
MIT


