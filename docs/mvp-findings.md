# MVP Findings (camfx)

## Environment
- Fedora 43, kernel 6.18.0-rc4 (vanilla)
- Python 3.10.18 (venv)
- v4l2loopback from RPM Fusion (akmod-v4l2loopback 0.15.2)

## What worked
- Project scaffolded: package, CLI, effects, segmentation, example, README, .gitignore.
- `pip install -e .` succeeded; MediaPipe and OpenCV import OK.
- `camfx list-devices` now instantaneous (sysfs-based, lazy imports).
- Real webcam accessible via viewers with elevated perms:
  - `sudo ffplay -f video4linux2 -i /dev/video0` displayed video.

## Issues observed
- v4l2loopback device creation and stability:
  - `/dev/video4` existed (label "OBS Virtual Camera") even without OBS installed (default label from packaging).
  - Target `/dev/video10` configured; sysfs shows it (name "camfx").
  - Querying `/dev/video10` caused kernel errors:
    - `dmesg` shows repeated RIP in `v4l2loopback` (vidioc_querycap / vidioc_g_input).
    - `v4l2-ctl` frequently killed; `ffplay` showed no output for `/dev/video10`.
- OpenCV preview window often did not appear (likely Wayland/HighGUI or blocked by long model init).
- Browsers/camera apps froze or showed no devices when v4l2loopback misbehaved.

## Likely root cause
- v4l2loopback module instability with the running kernel (6.18.0-rc4). The akmod-built module taints the kernel and crashes on standard V4L2 ioctls (QUERYCAP/G_INPUT), breaking enumeration/streaming in apps.

## Mitigations applied in camfx
- Non-blocking device listing (no device opens; reads `/sys/class/video4linux/*/name`).
- Lazy imports (avoid MediaPipe/OpenCV import cost on unrelated commands).
- Added `--no-virtual` to run preview-only without touching v4l2loopback.
- Virtual output format adjustments (BGR→RGB24 via pyvirtualcam) to match common viewers.

## Validation matrix (current)
- Webcam input: OK via ffplay with sudo; input index 0 maps to `/dev/video0`.
- camfx processing: unconfirmed visually via OpenCV window; expected OK (model initializes, no exceptions reported).
- Virtual device `/dev/video10`: created and named, but viewing/queries unstable due to module crashes.
- Browser/apps: Firefox froze; GNOME Camera showed no devices when loopback was unstable.

## Recommended next steps
1) Stabilize v4l2loopback on this kernel:
   - Rebuild from source against current headers:
     ```bash
     sudo dnf install -y kernel-devel kernel-headers gcc make
     git clone https://github.com/umlaeute/v4l2loopback.git
     cd v4l2loopback && make && sudo make install
     sudo modprobe -r v4l2loopback || true
     sudo modprobe v4l2loopback devices=2 video_nr=4,10 card_label=OBS,camfx exclusive_caps=1
     ```
   - If still unstable, test a stable Fedora kernel (non -rc) or use the distro’s stock kernel.
2) Verify camfx preview-only path:
   - `camfx blur --input 0 --strength 25 --preview --no-virtual`
   - If window still doesn’t show, use `qv4l2`/`ffplay` for input validation and consider adding a viewer-based preview path.
3) After loopback stability:
   - Drive `/dev/video10` from camfx and validate with `ffplay -f video4linux2 -i /dev/video10` (match size/format if needed).
4) Hardening:
   - Add a `camfx doctor` command to report module status, device perms, pixel formats, and common conflicts.
   - Improve logging around initialization and frame send.

## TL;DR
The codebase and CLI are functional, but the virtual camera path is blocked by v4l2loopback instability on kernel 6.18.0-rc4. Rebuilding the module (or using a stable kernel) should unblock `/dev/video10`. Meanwhile, preview-only mode and direct webcam viewing work for validating processing.


