"""V4L2 loopback virtual camera output using FFmpeg.

This backend writes RGB frames into a long-running `ffmpeg` process which
converts RGB24 -> YUV420P and streams into a v4l2loopback /dev/videoX node.

The intention is to avoid PipeWire/GStreamer dependencies while keeping
client compatibility (universal V4L2 /dev/videoX interface).
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from typing import Optional
import shutil

logger = logging.getLogger("camfx.output_v4l2_ffmpeg")


@dataclass(frozen=True, slots=True)
class V4L2OutputConfig:
	device: str = "auto"  # "auto" resolves by card_label
	card_label: str = "camfx"  # used for auto-resolution
	pix_fmt: str = "yuv420p"  # output pixel format for v4l2
	ffmpeg_loglevel: str = "error"


def _resolve_v4l2_device(device: str, card_label: str) -> str:
	"""Resolve a usable /dev/videoX path.

	Resolution order:
	1) If `device` is an explicit /dev/videoX, use it.
	2) Scan sysfs for /sys/class/video4linux/*/name == card_label.
	3) If v4l2-ctl is available, parse `v4l2-ctl --list-devices`.
	"""
	if device and device != "auto":
		if device.startswith("/dev/video"):
			return device
		# Accept plain "videoN" as well.
		if device.startswith("video") and device[5:].isdigit():
			return f"/dev/{device}"
		return device

	# 2) sysfs scan
	try:
		sys_class = "/sys/class/video4linux"
		if os.path.isdir(sys_class):
			for entry in sorted(os.listdir(sys_class)):
				name_path = os.path.join(sys_class, entry, "name")
				try:
					with open(name_path, "r", encoding="utf-8") as f:
						name = f.read().strip()
					if name == card_label:
						dev_path = f"/dev/video{entry.replace('video', '')}"
						if os.path.exists(dev_path):
							return dev_path
				except OSError:
					continue
	except Exception:
		pass

	# 3) v4l2-ctl scan (optional)
	v4l2_ctl = shutil.which("v4l2-ctl")

	if v4l2_ctl:
		try:
			# Example format:
			#   camfx_test (platform:v4l2loopback-000):
			#       /dev/video0
			# ...
			out = subprocess.run(
				[v4l2_ctl, "--list-devices"],
				capture_output=True,
				text=True,
				timeout=5,
			)
			if out.returncode == 0:
				lines = out.stdout.splitlines()
				found_label = False
				for line in lines:
					if not found_label:
						if card_label in line:
							found_label = True
						continue
					stripped = line.strip()
					if stripped.startswith("/dev/video"):
						return stripped
					# Stop scanning once the block ends.
					if stripped and not stripped.startswith("/dev/video"):
						break
		except Exception:
			pass

	raise RuntimeError(
		"Could not resolve v4l2 device node. "
		f"Set `v4l2_device` explicitly (e.g. /dev/video0) or ensure v4l2loopback "
		f"is loaded with card_label='{card_label}'."
	)


class V4L2OutputFFmpeg:
	"""Write RGB frames to a v4l2loopback device via FFmpeg."""

	def __init__(
		self,
		width: int,
		height: int,
		fps: int,
		name: str = "camfx",
		device: str = "auto",
		card_label: Optional[str] = None,
	) -> None:
		self.width = int(width)
		self.height = int(height)
		self.fps = int(fps)
		self.name = name
		self.config = V4L2OutputConfig(
			device=device,
			card_label=card_label or name,
		)
		self.frame_time = 1.0 / max(self.fps, 1)
		self.last_frame_time = time.time()
		self._frames_sent = 0

		self.device = _resolve_v4l2_device(self.config.device, self.config.card_label)
		self._proc: Optional[subprocess.Popen[bytes]] = None
		self._start_ffmpeg()

	def _start_ffmpeg(self) -> None:
		"""Start the persistent ffmpeg pipeline."""
		ffmpeg = "ffmpeg"
		if not shutil.which(ffmpeg):
			raise RuntimeError("ffmpeg not found in PATH")

		# ffmpeg reads raw RGB24 frames from stdin and writes to v4l2 device.
		cmd = [
			ffmpeg,
			"-hide_banner",
			"-loglevel",
			self.config.ffmpeg_loglevel,
			"-f",
			"rawvideo",
			"-pixel_format",
			"rgb24",
			"-video_size",
			f"{self.width}x{self.height}",
			"-framerate",
			str(self.fps),
			"-i",
			"-",
			"-f",
			"v4l2",
			"-pix_fmt",
			self.config.pix_fmt,
			self.device,
		]

		logger.info(
			"Starting ffmpeg->v4l2: %sx%s@%sfps device=%s",
			self.width,
			self.height,
			self.fps,
			self.device,
		)
		self._proc = subprocess.Popen(
			cmd,
			stdin=subprocess.PIPE,
			stdout=subprocess.DEVNULL,
			stderr=subprocess.PIPE,
			bufsize=0,
		)

	def send(self, frame_rgb: bytes) -> None:
		"""Send one RGB frame (RGB24) into the v4l2 device."""
		if not self._proc or not self._proc.stdin:
			raise RuntimeError("V4L2 output not initialized (ffmpeg process missing)")
		expected = self.width * self.height * 3
		if len(frame_rgb) != expected:
			raise ValueError(f"Frame size mismatch: expected {expected} bytes, got {len(frame_rgb)}")

		try:
			self._proc.stdin.write(frame_rgb)
		except BrokenPipeError as e:
			# Grab any tail stderr for debugging.
			err = b""
			try:
				err = self._proc.stderr.read(4096) if self._proc.stderr else b""
			except Exception:
				pass
			raise RuntimeError(f"ffmpeg pipe broken (device={self.device}). stderr tail: {err[-200:]!r}") from e

		self._frames_sent += 1

	def sleep_until_next_frame(self) -> None:
		"""Maintain target frame rate."""
		current_time = time.time()
		elapsed = current_time - self.last_frame_time
		sleep_time = max(0.0, self.frame_time - elapsed)
		if sleep_time > 0:
			time.sleep(sleep_time)
		self.last_frame_time = time.time()

	def cleanup(self) -> None:
		"""Stop ffmpeg and release resources."""
		proc = self._proc
		self._proc = None
		if not proc:
			return

		try:
			if proc.stdin:
				proc.stdin.close()
		except Exception:
			pass

		try:
			proc.terminate()
		except Exception:
			pass

		try:
			proc.wait(timeout=2)
		except Exception:
			try:
				proc.kill()
			except Exception:
				pass

