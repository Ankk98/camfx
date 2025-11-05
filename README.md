camfx
=====

A lightweight, modular camera video enhancement middleware for Linux that provides background blur and basic background replacement, outputting to a virtual camera device for use with video apps.

Features (MVP)
--------------
- Background blur with adjustable strength
- Basic background replacement with a static image
- CLI with input/output device selection, resolution, FPS, and optional preview window

Prerequisites
-------------
- Linux with v4l2loopback kernel module available
- Python 3.9+

Quickstart
----------
```bash
# 1) Create virtual camera device (requires sudo)
sudo modprobe v4l2loopback devices=1 video_nr=10 card_label="camfx" exclusive_caps=1

# 2) Create and activate virtual environment (optional but recommended)
python3 -m venv .venv
source .venv/bin/activate

# 3) Install package in editable mode
pip install -U pip wheel
pip install -e .

# 4) Run with background blur
camfx blur --strength 25 --preview

# 5) Or run with background replacement
camfx replace --image /path/to/background.jpg --preview
```

CLI Reference (MVP)
-------------------
```bash
# Background blur
camfx blur --strength 25 --input 0 --vdevice /dev/video10 --width 1280 --height 720 --fps 30 --preview

# Background replacement
camfx replace --image /path/to/background.jpg --input 0 --vdevice /dev/video10 --width 1280 --height 720 --fps 30 --preview

# List devices
camfx list-devices

# Preview-only (no virtual device) for debugging
camfx blur --input 0 --strength 25 --preview --no-virtual
```

Troubleshooting
---------------
- Ensure your user has permission to write to the virtual device (e.g., `/dev/video10`). You may need to adjust udev rules or run your terminal within a group that has access to video devices (often the `video` group).
- If `camfx` cannot open the virtual camera, confirm `v4l2loopback` is loaded and the device node exists.
- If `camfx list-devices` hangs, update to the latest CLI (now uses a non-blocking sysfs scan) or run: `for n in /sys/class/video4linux/video*/name; do echo "$n: $(cat "$n")"; done`.
- If preview window does not appear, try `--no-virtual` to isolate the preview, and verify input index with `camfx list-devices`.

License
-------
MIT


