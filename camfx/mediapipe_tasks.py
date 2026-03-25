"""MediaPipe Tasks backend (models + cached task instances).

This module implements the ML backbone for camfx using MediaPipe Tasks.
It intentionally avoids `mediapipe.solutions` which may not exist in many
modern mediapipe wheels (including 0.10.x where `mediapipe/__init__.py`
exports Tasks but not Solutions).

Models are downloaded on-demand into a cache directory.
"""

from __future__ import annotations

import hashlib
import logging
import os
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Optional

import cv2
import numpy as np

logger = logging.getLogger("camfx.mediapipe_tasks")


def _default_models_dir() -> Path:
	root = os.environ.get("XDG_CACHE_HOME") or os.path.join(Path.home(), ".cache")
	return Path(os.environ.get("CAMFX_MODELS_DIR") or (Path(root) / "camfx" / "models"))


@dataclass(frozen=True, slots=True)
class ModelSpec:
	name: str
	url: str
	sha256: str | None = None  # optional pin


SELFIE_SEGMENTER_LANDSCAPE = ModelSpec(
	name="selfie_segmenter_landscape.tflite",
	url="https://storage.googleapis.com/mediapipe-models/image_segmenter/selfie_segmenter_landscape/float16/latest/selfie_segmenter_landscape.tflite",
)

FACE_LANDMARKER = ModelSpec(
	name="face_landmarker.task",
	url="https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/latest/face_landmarker.task",
)


def _sha256_file(path: Path) -> str:
	h = hashlib.sha256()
	with open(path, "rb") as f:
		for chunk in iter(lambda: f.read(1024 * 1024), b""):
			h.update(chunk)
	return h.hexdigest()


def ensure_model(spec: ModelSpec) -> Path:
	"""Download the model if missing, return local path."""
	models_dir = _default_models_dir()
	models_dir.mkdir(parents=True, exist_ok=True)
	dst = models_dir / spec.name

	if dst.exists() and dst.stat().st_size > 0:
		if spec.sha256:
			actual = _sha256_file(dst)
			if actual.lower() != spec.sha256.lower():
				raise RuntimeError(f"Model hash mismatch for {dst} (expected {spec.sha256}, got {actual})")
		return dst

	tmp = dst.with_suffix(dst.suffix + ".tmp")
	logger.info("Downloading model %s", spec.url)
	try:
		with urllib.request.urlopen(spec.url, timeout=30) as resp:
			if getattr(resp, "status", 200) != 200:
				raise RuntimeError(f"HTTP {getattr(resp, 'status', None)} downloading model: {spec.url}")
			data = resp.read()
		with open(tmp, "wb") as f:
			f.write(data)
		if spec.sha256:
			actual = _sha256_file(tmp)
			if actual.lower() != spec.sha256.lower():
				tmp.unlink(missing_ok=True)  # type: ignore[arg-type]
				raise RuntimeError(f"Model hash mismatch for {spec.name} (expected {spec.sha256}, got {actual})")
		tmp.replace(dst)
		return dst
	finally:
		try:
			if tmp.exists():
				tmp.unlink()
		except Exception:
			pass


_SEGMENTER_LOCK = Lock()
_LANDMARKER_LOCK = Lock()
_segmenter = None
_landmarker = None


def _mp_import():
	# mediapipe package exports Tasks in modern builds.
	import mediapipe as mp  # type: ignore

	if not hasattr(mp, "tasks") or not hasattr(mp.tasks, "vision"):
		raise RuntimeError("This mediapipe build does not provide mp.tasks.vision (Tasks API missing).")
	return mp


def get_image_segmenter():
	global _segmenter
	if _segmenter is not None:
		return _segmenter
	with _SEGMENTER_LOCK:
		if _segmenter is not None:
			return _segmenter
		mp = _mp_import()
		model_path = str(ensure_model(SELFIE_SEGMENTER_LANDSCAPE))
		BaseOptions = mp.tasks.BaseOptions
		ImageSegmenter = mp.tasks.vision.ImageSegmenter
		ImageSegmenterOptions = mp.tasks.vision.ImageSegmenterOptions
		RunningMode = mp.tasks.vision.RunningMode

		options = ImageSegmenterOptions(
			base_options=BaseOptions(model_asset_path=model_path),
			running_mode=RunningMode.VIDEO,
			output_confidence_masks=True,
			output_category_mask=False,
		)
		_segmenter = ImageSegmenter.create_from_options(options)
		return _segmenter


def get_face_landmarker():
	global _landmarker
	if _landmarker is not None:
		return _landmarker
	with _LANDMARKER_LOCK:
		if _landmarker is not None:
			return _landmarker
		mp = _mp_import()
		model_path = str(ensure_model(FACE_LANDMARKER))
		BaseOptions = mp.tasks.BaseOptions
		FaceLandmarker = mp.tasks.vision.FaceLandmarker
		FaceLandmarkerOptions = mp.tasks.vision.FaceLandmarkerOptions
		RunningMode = mp.tasks.vision.RunningMode

		options = FaceLandmarkerOptions(
			base_options=BaseOptions(model_asset_path=model_path),
			running_mode=RunningMode.VIDEO,
			num_faces=1,
			output_face_blendshapes=False,
			output_facial_transformation_matrixes=False,
		)
		_landmarker = FaceLandmarker.create_from_options(options)
		return _landmarker


def person_mask_from_bgr(frame_bgr: np.ndarray, timestamp_ms: int) -> np.ndarray:
	"""Return float32 mask in [0,1] for person region."""
	mp = _mp_import()
	segmenter = get_image_segmenter()
	frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
	mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame_rgb)
	result = segmenter.segment_for_video(mp_image, int(timestamp_ms))
	# Selfie segmenter outputs 2 confidence masks: background(0), person(1)
	conf = getattr(result, "confidence_masks", None)
	if not conf or len(conf) < 2:
		h, w = frame_bgr.shape[:2]
		return np.zeros((h, w), dtype=np.float32)
	person = conf[1].numpy_view()  # HxW float32
	mask = np.clip(person.astype(np.float32), 0.0, 1.0)
	return cv2.GaussianBlur(mask, (21, 21), 0)


def face_landmarks_from_bgr(frame_bgr: np.ndarray, timestamp_ms: int):
	"""Return face_landmarks list (normalized landmarks) or None."""
	mp = _mp_import()
	landmarker = get_face_landmarker()
	frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
	mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame_rgb)
	result = landmarker.detect_for_video(mp_image, int(timestamp_ms))
	landmarks = getattr(result, "face_landmarks", None)
	if not landmarks:
		return None
	return landmarks[0]

