#!/usr/bin/env python3
"""
Debug script for MediaPipe Tasks ImageSegmenter (selfie segmenter).

It prints raw category/confidence mask stats and the resulting camfx mask
stats from camfx.mediapipe_tasks.person_mask_from_bgr().
"""

from __future__ import annotations

import argparse
import time
from typing import Any, Tuple

import cv2
import numpy as np


def _to_numpy(v: Any) -> np.ndarray:
	if hasattr(v, "numpy_view"):
		return v.numpy_view()
	if hasattr(v, "to_numpy"):
		return v.to_numpy()
	return np.array(v)


def _mask_stats(mask: np.ndarray) -> str:
	if mask is None:
		return "mask=None"
	if mask.size == 0:
		return "mask=empty"
	return f"min={float(mask.min()):0.4f} max={float(mask.max()):0.4f} mean={float(mask.mean()):0.4f}"


def main() -> int:
	parser = argparse.ArgumentParser(description="Test MediaPipe Tasks selfie segmenter")
	parser.add_argument("--source", default="0", help="OpenCV VideoCapture source (index or /dev/videoX)")
	parser.add_argument("--num-frames", type=int, default=30)
	parser.add_argument("--print-every", type=int, default=5)
	parser.add_argument("--timestamp-ms", type=str, default="frame", help="frame|time (frame => i*33ms, time => wall clock)")
	args = parser.parse_args()

	try:
		import mediapipe as mp  # type: ignore
	except Exception as e:
		print(f"Error: cannot import mediapipe: {e}")
		return 2

	if not hasattr(mp, "tasks") or not hasattr(mp.tasks, "vision"):
		print("Error: mediapipe.tasks.vision missing in this mediapipe build.")
		return 2

	from camfx.mediapipe_tasks import get_image_segmenter, person_mask_from_bgr

	source: str | int
	if str(args.source).isdigit():
		source = int(args.source)
	else:
		source = args.source

	cap = cv2.VideoCapture(source)
	if not cap.isOpened():
		print(f"Error: cannot open capture source={args.source}")
		return 1

	segmenter = get_image_segmenter()
	mp_image_format = mp.ImageFormat.SRGB

	fps_assumed_ms = 33
	start = time.time()

	for i in range(args.num_frames):
		ret, frame = cap.read()
		if not ret or frame is None:
			print(f"Frame {i}: read failed")
			continue

		# IMAGE mode doesn't require timestamps, but we keep the args for compatibility.
		if args.timestamp_ms == "time":
			ts_ms = int((time.time() - start) * 1000)
		else:
			ts_ms = i * fps_assumed_ms

		frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
		mp_image = mp.Image(image_format=mp_image_format, data=frame_rgb)
		if hasattr(segmenter, "segment"):
			result = segmenter.segment(mp_image)
		else:
			# Fallback for older API shapes.
			result = segmenter.segment_for_video(mp_image, int(ts_ms))

		cat = getattr(result, "category_mask", None)
		conf = getattr(result, "confidence_masks", None)

		if args.print_every and (i + 1) % args.print_every == 0:
			print(f"\nProgress {i+1}/{args.num_frames} ts_ms={ts_ms}")
			if cat:
				try:
					c0 = cat[0]
					c0_arr = _to_numpy(c0)
					print(f"category_mask[0]: shape={c0_arr.shape} unique={np.unique(c0_arr.astype(np.int32))[:10]}")
					print(f"category_mask[0]: {_mask_stats(c0_arr.astype(np.float32))}")
				except Exception as e:
					print(f"category_mask debug failed: {e}")
			else:
				print("category_mask: missing/empty")

			if conf:
				try:
					print(f"confidence_masks: len={len(conf)}")
					for ci, ch in enumerate(conf[:2]):
						ch_arr = _to_numpy(ch).astype(np.float32)
						print(f"  conf[{ci}]: {_mask_stats(ch_arr)}")
				except Exception as e:
					print(f"confidence_masks debug failed: {e}")
			else:
				print("confidence_masks: missing/empty")

			# camfx derived mask
			mask = person_mask_from_bgr(frame, int(ts_ms))
			print(f"camfx mask stats: {_mask_stats(mask)}")

	cap.release()
	print("\nDone.")
	return 0


if __name__ == "__main__":
	raise SystemExit(main())

