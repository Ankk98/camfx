#!/usr/bin/env python3
"""
Quick integration-style test for MediaPipe Tasks FaceLandmarker.

This script checks whether face landmarks can be detected from a live
v4l2 camera feed (or any OpenCV VideoCapture source) and prints basic
stats (frames processed, frames with faces, last bounding box).

It uses camfx's MediaPipe Tasks backend, which downloads model assets into
~/.cache/camfx/models by default.
"""

from __future__ import annotations

import argparse
import time
from typing import Tuple, Optional

import cv2


def _parse_source(source: str):
	# OpenCV accepts either numeric indices or device paths.
	if source.isdigit():
		return int(source)
	return source


def _compute_bbox_from_landmarks(landmarks, w: int, h: int) -> Tuple[int, int, int, int]:
	xs = [float(lm.x) for lm in landmarks]
	ys = [float(lm.y) for lm in landmarks]
	x_min = int(max(0.0, min(xs)) * w)
	y_min = int(max(0.0, min(ys)) * h)
	x_max = int(min(1.0, max(xs)) * w)
	y_max = int(min(1.0, max(ys)) * h)
	return (x_min, y_min, max(1, x_max - x_min), max(1, y_max - y_min))


def main() -> int:
	parser = argparse.ArgumentParser(description="Test MediaPipe Tasks FaceLandmarker")
	parser.add_argument("--source", default="0", help="OpenCV VideoCapture source (index like 0 or /dev/videoX)")
	parser.add_argument("--num-frames", type=int, default=60, help="Number of frames to test")
	parser.add_argument("--min-success", type=int, default=1, help="Exit non-zero if fewer than this many frames detect faces")
	parser.add_argument("--print-every", type=int, default=10, help="Print progress every N frames")
	parser.add_argument("--sleep", type=float, default=0.0, help="Optional sleep between frames")
	args = parser.parse_args()

	# Import mediapipe tasks API (should exist even if mediapipe.solutions is missing).
	try:
		import mediapipe as mp  # type: ignore
	except Exception as e:
		print(f"Error: failed to import mediapipe: {e}")
		return 2

	if not hasattr(mp, "tasks") or not hasattr(mp.tasks, "vision"):
		print("Error: mediapipe.tasks.vision is missing in your mediapipe installation.")
		return 2

	try:
		from camfx.mediapipe_tasks import get_face_landmarker
	except Exception as e:
		print(f"Error: failed to import camfx mediapipe tasks backend: {e}")
		return 2

	source = _parse_source(args.source)
	cap = cv2.VideoCapture(source)
	if not cap.isOpened():
		print(f"Error: cannot open capture source={args.source} (parsed={source!r})")
		return 1

	# Try to read properties.
	w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
	h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
	if w <= 0 or h <= 0:
		# We'll infer from first frame.
		w = 0
		h = 0

	landmarker = get_face_landmarker()

	start = time.time()
	faces_detected = 0
	last_bbox: Optional[Tuple[int, int, int, int]] = None

	for i in range(args.num_frames):
		ret, frame = cap.read()
		if not ret or frame is None:
			if i == 0:
				print("Error: failed to read first frame from capture")
				break
			continue

		if w <= 0 or h <= 0:
			h, w = frame.shape[:2]

		ts_ms = int((time.time() - start) * 1000)
		frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
		mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame_rgb)
		result = landmarker.detect_for_video(mp_image, ts_ms)

		landmarks = getattr(result, "face_landmarks", None)
		if landmarks:
			# Only num_faces=1 is configured, so take first.
			bbox = _compute_bbox_from_landmarks(landmarks[0], w, h)
			last_bbox = bbox
			faces_detected += 1

		if args.print_every and (i + 1) % args.print_every == 0:
			print(
				f"Progress: {i+1}/{args.num_frames} "
				f"faces_detected_frames={faces_detected} "
				f"last_bbox={last_bbox}"
			)

		if args.sleep > 0:
			time.sleep(args.sleep)

	cap.release()

	print("\n=== FaceLandmarker result ===")
	print(f"source={args.source} num_frames={args.num_frames}")
	print(f"faces_detected_frames={faces_detected}")
	print(f"last_bbox={last_bbox}")

	if faces_detected >= args.min_success:
		print("OK: face detection appears to be working.")
		return 0
	else:
		print("FAIL: face detection did not trigger enough times.")
		print("Next: ensure good lighting / try different camera index / try another input resolution.")
		return 1


if __name__ == "__main__":
	raise SystemExit(main())

