"""Helpers for enumerating camera devices and their supported modes."""

from __future__ import annotations

import glob
import logging
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from typing import Dict, List, Sequence

import cv2

logger = logging.getLogger('camfx.camera_devices')

# Common resolutions/fps pairs we try when probing via OpenCV
DEFAULT_RESOLUTIONS: Sequence[tuple[int, int]] = (
	(1920, 1080),
	(1280, 720),
	(1024, 576),
	(960, 540),
	(854, 480),
	(640, 480),
	(640, 360),
	(426, 240),
)

DEFAULT_FPS: Sequence[int] = (60, 30, 24, 15)


@dataclass(frozen=True, slots=True)
class CameraDevice:
	"""Represents a physical camera device."""
	
	id: str
	label: str


def list_camera_devices() -> List[CameraDevice]:
	"""List available V4L2 camera device nodes."""
	devices: List[CameraDevice] = []
	for path in sorted(glob.glob('/dev/video*')):
		name = _read_device_name(path)
		label = f"{name} ({path})" if name else path
		devices.append(CameraDevice(id=path, label=label))
	return devices


def parse_v4l2_formats(raw_output: str) -> List[Dict[str, object]]:
	"""Parse `v4l2-ctl --list-formats-ext` output into structured modes."""
	size_pattern = re.compile(r'Size:\s+Discrete\s+(\d+)x(\d+)', re.IGNORECASE)
	fps_pattern = re.compile(r'\(([\d\.]+)\s+fps\)', re.IGNORECASE)
	modes: Dict[tuple[int, int], set[int]] = {}
	current_size: tuple[int, int] | None = None
	
	for line in raw_output.splitlines():
		line = line.strip()
		if not line:
			continue
		
		size_match = size_pattern.search(line)
		if size_match:
			current_size = (int(size_match.group(1)), int(size_match.group(2)))
			modes.setdefault(current_size, set())
			continue
		
		if current_size and line.lower().startswith('interval:'):
			fps_match = fps_pattern.search(line)
			if fps_match:
				try:
					fps_value = int(round(float(fps_match.group(1))))
				except ValueError:
					continue
				if fps_value > 0:
					modes[current_size].add(fps_value)
			continue
	
	return _modes_dict_to_list(modes)


def probe_camera_modes(device_path: str,
                       sample_resolutions: Sequence[tuple[int, int]] | None = None,
                       fps_targets: Sequence[int] | None = None) -> List[Dict[str, object]]:
	"""Detect supported (resolution, fps) combos for a camera device."""
	candidate_resolutions = sample_resolutions or DEFAULT_RESOLUTIONS
	candidate_fps = fps_targets or DEFAULT_FPS
	
	# Prefer v4l2-ctl output when available for more accurate results
	mode_list = _probe_with_v4l2ctl(device_path)
	if mode_list:
		return mode_list
	
	mode_list = _probe_with_opencv(device_path, candidate_resolutions, candidate_fps)
	if mode_list:
		return mode_list
	
	# Fallback to conservative default to keep UI usable
	return [{'width': 640, 'height': 480, 'fps': [30]}]


def _probe_with_v4l2ctl(device_path: str) -> List[Dict[str, object]]:
	if shutil.which('v4l2-ctl') is None:
		return []
	
	try:
		result = subprocess.run(
			['v4l2-ctl', '--device', device_path, '--list-formats-ext'],
			capture_output=True,
			text=True,
			timeout=5
		)
		if result.returncode != 0:
			logger.debug("v4l2-ctl returned code %s for %s", result.returncode, device_path)
			return []
		modes = parse_v4l2_formats(result.stdout)
		if modes:
			logger.debug("Detected %d modes for %s via v4l2-ctl", len(modes), device_path)
		return modes
	except (subprocess.SubprocessError, OSError) as exc:
		logger.debug("Failed to run v4l2-ctl for %s: %s", device_path, exc)
		return []


def _probe_with_opencv(device_path: str,
                       resolutions: Sequence[tuple[int, int]],
                       fps_targets: Sequence[int]) -> List[Dict[str, object]]:
	cap = cv2.VideoCapture(device_path)
	if not cap or not cap.isOpened():
		index = _device_path_to_index(device_path)
		if index is not None:
			cap = cv2.VideoCapture(index)
	if not cap or not cap.isOpened():
		logger.warning("Unable to open camera %s for probing", device_path)
		return []
	
	try:
		modes: Dict[tuple[int, int], set[int]] = {}
		for width, height in resolutions:
			if not _set_resolution(cap, width, height):
				continue
			
			fps_values = _probe_fps(cap, fps_targets)
			if not fps_values:
				default_fps = int(round(cap.get(cv2.CAP_PROP_FPS) or 0))
				if default_fps > 0:
					fps_values = [default_fps]
			
			if fps_values:
				modes.setdefault((width, height), set()).update(fps_values)
		
		if not modes:
			actual_width = int(round(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0))
			actual_height = int(round(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0))
			actual_fps = int(round(cap.get(cv2.CAP_PROP_FPS) or 0)) or 30
			if actual_width > 0 and actual_height > 0:
				modes[(actual_width, actual_height)] = {actual_fps}
		
		return _modes_dict_to_list(modes)
	finally:
		cap.release()


def _modes_dict_to_list(modes: Dict[tuple[int, int], set[int]]) -> List[Dict[str, object]]:
	mode_list: List[Dict[str, object]] = []
	for (width, height), fps_values in modes.items():
		if not fps_values:
			continue
		mode_list.append({
			'width': width,
			'height': height,
			'fps': sorted({int(abs(fps)) for fps in fps_values if fps > 0})
		})
	
	mode_list.sort(key=lambda item: (-item['width'], -item['height']))
	return mode_list


def _set_resolution(cap: cv2.VideoCapture, width: int, height: int) -> bool:
	cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
	cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
	actual_w = int(round(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0))
	actual_h = int(round(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0))
	if actual_w <= 0 or actual_h <= 0:
		return False
	return abs(actual_w - width) <= 8 and abs(actual_h - height) <= 8


def _probe_fps(cap: cv2.VideoCapture, fps_targets: Sequence[int]) -> List[int]:
	supported: List[int] = []
	for fps in fps_targets:
		cap.set(cv2.CAP_PROP_FPS, fps)
		actual = cap.get(cv2.CAP_PROP_FPS) or 0
		actual_int = int(round(actual))
		if actual_int <= 0:
			continue
		if abs(actual - fps) <= 1.0:
			supported.append(actual_int)
	return sorted({fps for fps in supported if fps > 0})


def _device_path_to_index(device_path: str) -> int | None:
	try:
		basename = os.path.basename(device_path)
		if basename.startswith('video'):
			return int(basename.replace('video', ''))
		if basename.isdigit():
			return int(basename)
	except ValueError:
		return None
	return None


def _read_device_name(device_path: str) -> str:
	basename = os.path.basename(device_path)
	name_path = f"/sys/class/video4linux/{basename}/name"
	try:
		with open(name_path, 'r', encoding='utf-8') as handle:
			return handle.read().strip()
	except OSError:
		return ''


