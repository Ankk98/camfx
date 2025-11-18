"""Tests for camera capability helpers."""

from camfx.camera_devices import parse_v4l2_formats


SAMPLE_V4L2_OUTPUT = """
ioctl: VIDIOC_ENUM_FMT
    Type: Video Capture

    [0]: 'YUYV' (YUYV 4:2:2)
        Size: Discrete 1920x1080
            Interval: Discrete 0.016s (60.000 fps)
            Interval: Discrete 0.033s (30.000 fps)
        Size: Discrete 1280x720
            Interval: Discrete 0.008s (120.000 fps)
            Interval: Discrete 0.033s (30.000 fps)
        Size: Discrete 640x480
            Interval: Discrete 0.033s (30.000 fps)
"""


def test_parse_v4l2_formats_produces_sorted_modes():
	modes = parse_v4l2_formats(SAMPLE_V4L2_OUTPUT)
	assert modes[0]['width'] == 1920
	assert modes[0]['fps'] == [30, 60]
	assert {'width': 1280, 'height': 720, 'fps': [30, 120]} in modes
	assert {'width': 640, 'height': 480, 'fps': [30]} in modes


def test_parse_v4l2_formats_handles_empty_input():
	assert parse_v4l2_formats('') == []


