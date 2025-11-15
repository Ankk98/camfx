# FFmpeg Feasibility Test

## Quick Start

Run the comprehensive feasibility test:

```bash
# Basic test (uses /dev/video10, 1280x720@30fps)
python scripts/test_ffmpeg_v4l2_feasibility.py

# Custom device and resolution
python scripts/test_ffmpeg_v4l2_feasibility.py --device /dev/video11 --width 1920 --height 1080 --fps 30
```

## What It Tests

The test script validates:

1. **FFmpeg Installation** - Checks if FFmpeg is installed and version
2. **V4L2 Support** - Verifies FFmpeg supports v4l2 output
3. **v4l2loopback Module** - Checks if module is loaded, attempts to load if not
4. **Device Existence** - Verifies device file exists
5. **Device Permissions** - Checks if user can write to device
6. **Device Information** - Gets device capabilities using v4l2-ctl
7. **Format Conversion** - Tests RGB24 → YUV420P conversion
8. **Frame Streaming** - Actually streams test frames to device
9. **Performance** - Benchmarks conversion speed
10. **Application Visibility** - Checks if device appears in v4l2-ctl

## Prerequisites

The test will attempt to install/load missing components, but you may need:

```bash
# Install FFmpeg
sudo apt install ffmpeg          # Ubuntu/Debian
sudo dnf install ffmpeg           # Fedora

# Install v4l2loopback
sudo apt install v4l2loopback-dkms  # Ubuntu/Debian
sudo dnf install v4l2loopback       # Fedora

# Install v4l2-utils (optional, for device info)
sudo apt install v4l-utils        # Ubuntu/Debian
sudo dnf install v4l-utils       # Fedora
```

## Expected Output

If everything works, you'll see:

```
✓ FFmpeg Installation
✓ FFmpeg V4L2 Support
✓ v4l2loopback Module
✓ Device Existence
✓ Device Permissions
✓ Format Conversion
✓ Frame Streaming
✓ Performance
✓ Application Visibility

Results: 10/10 tests passed
✓ All tests passed! FFmpeg bridge is feasible.
```

## Troubleshooting

### "FFmpeg not found"
```bash
sudo apt install ffmpeg  # or equivalent for your distro
```

### "Permission denied"
```bash
# Add user to video group
sudo usermod -aG video $USER
# Log out and back in for changes to take effect
```

### "Device does not exist"
```bash
# Load v4l2loopback module manually
sudo modprobe v4l2loopback video_nr=10 exclusive_caps=1 card_label="camfx_test"
```

### "Module load failed"
```bash
# Install v4l2loopback
sudo apt install v4l2loopback-dkms
# Rebuild modules (may require reboot)
sudo dkms autoinstall
```

## Next Steps

If tests pass:
1. Review the feasibility study: `docs/ffmpeg-feasibility-study.md`
2. Implement FFmpeg output module: `camfx/output_v4l2_ffmpeg.py`
3. Integrate with camfx core

If tests fail:
1. Check error messages for specific issues
2. Review troubleshooting section above
3. Check system logs: `dmesg | grep v4l2loopback`
4. Verify kernel module compatibility

