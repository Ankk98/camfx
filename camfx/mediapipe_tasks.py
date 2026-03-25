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
_SEGMENTER_EMPTY_MASK_DEBUG_LAST = 0.0


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
			# IMAGE mode avoids timestamp/tracking edge-cases.
			running_mode=RunningMode.IMAGE,
			# Category mask avoids needing to guess which confidence channel
			# corresponds to "person" vs "background".
			output_confidence_masks=True,
			output_category_mask=True,
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
	# In IMAGE mode, we can use segment() (timestamp ignored).
	if hasattr(segmenter, "segment"):
		result = segmenter.segment(mp_image)
	else:
		# Fallback for older API shapes.
		result = segmenter.segment_for_video(mp_image, int(timestamp_ms))
	h, w = frame_bgr.shape[:2]
	global _SEGMENTER_EMPTY_MASK_DEBUG_LAST

	def _to_numpy(v):
		if hasattr(v, "numpy_view"):
			return v.numpy_view()
		if hasattr(v, "to_numpy"):
			return v.to_numpy()
		return np.array(v)

	# 1) Prefer category mask: selfie segmenter uses categories {0: background, 1: person}.
	cat = getattr(result, "category_mask", None)
	if cat:
		try:
			# category_mask is typically a list with one HxW mask image.
			cat0 = cat[0]
			raw_arr = _to_numpy(cat0)
			# Some outputs may be HxWx1; normalize to HxW.
			if hasattr(raw_arr, "ndim") and raw_arr.ndim == 3 and raw_arr.shape[-1] == 1:
				raw_arr = raw_arr[:, :, 0]
			raw_f = raw_arr.astype(np.float32)
			cat_arr = raw_f.astype(np.int32)
			if cat_arr.shape[0] != h or cat_arr.shape[1] != w:
				cat_arr = cv2.resize(cat_arr, (w, h), interpolation=cv2.INTER_NEAREST)
			if raw_f.shape[0] != h or raw_f.shape[1] != w:
				raw_f = cv2.resize(raw_f, (w, h), interpolation=cv2.INTER_NEAREST)
			labels = np.unique(cat_arr)

			# Heuristic: pick the category value at the image center as "person".
			center_label = int(cat_arr[h // 2, w // 2])
			person = (cat_arr == center_label).astype(np.float32)

			# Fallback if the chosen label covers (almost) everything or nothing.
			person_mean = float(person.mean())
			if (person_mean < 1e-4 or person_mean > 0.95) and len(labels) >= 2:
				other_labels = [int(x) for x in labels if int(x) != center_label]
				# Try the other label that isn't the center_label.
				other = other_labels[0]
				person = (cat_arr == other).astype(np.float32)

			# If still empty, return all-zeros (but log debug occasionally).
			if float(person.mean()) < 1e-6:
				# If category_mask was actually probability-like, use it directly.
				if float(raw_f.max()) <= 1.0 and float(raw_f.min()) >= 0.0:
					person_prob = np.clip(raw_f, 0.0, 1.0).astype(np.float32)
					if float(person_prob.mean()) >= 1e-6:
						return cv2.GaussianBlur(person_prob, (21, 21), 0)
				now = time.time()
				if now - _SEGMENTER_EMPTY_MASK_DEBUG_LAST >= 5.0:
					try:
						logger.error(
							"selfie segmenter produced empty person mask (all zeros). "
							"category_labels=%s center_label=%s cat_min=%0.4f cat_max=%0.4f person_mean=%0.4f",
							labels.tolist() if hasattr(labels, "tolist") else labels,
							center_label,
							float(cat_arr.min()),
							float(cat_arr.max()),
							float(person.mean()),
						)
					except Exception:
						logger.error("selfie segmenter produced empty person mask (all zeros). (debug extraction failed)")
					_SEGMENTER_EMPTY_MASK_DEBUG_LAST = now
				return np.zeros((h, w), dtype=np.float32)

			return cv2.GaussianBlur(person, (21, 21), 0)
		except Exception:
			pass

	# 2) Fallback to confidence masks.
	conf = getattr(result, "confidence_masks", None)
	if not conf or len(conf) < 1:
		return np.zeros((h, w), dtype=np.float32)

	def _to_float_array(v):
		return _to_numpy(v).astype(np.float32)

	def _squeeze_to_hw(arr: np.ndarray) -> np.ndarray:
		# Normalize common HxWx1 or 1xHxW layouts down to HxW.
		a = arr
		if hasattr(a, "ndim") and a.ndim == 3:
			if a.shape[-1] == 1:
				a = a[:, :, 0]
			elif a.shape[0] == 1:
				a = a[0, :, :]
		return a

	def _center_mean(arr2d: np.ndarray) -> float:
		cy0, cy1 = max(0, h // 2 - 5), min(h, h // 2 + 5)
		cx0, cx1 = max(0, w // 2 - 5), min(w, w // 2 + 5)
		return float(np.mean(arr2d[cy0:cy1, cx0:cx1]))

	try:
		# Some MediaPipe builds return only a single confidence map (often the "person"
		# probability). Handle len(conf)==1 as a single map case.
		if len(conf) == 1:
			c0 = _squeeze_to_hw(_to_float_array(conf[0]))
			if c0.ndim != 2:
				# If it's multi-channel in a single tensor, try to select the best center channel.
				if c0.ndim == 3 and (c0.shape[0] == 2 or c0.shape[-1] == 2):
					if c0.shape[0] == 2:
						ch0, ch1 = c0[0], c0[1]
					else:
						ch0, ch1 = c0[:, :, 0], c0[:, :, 1]
					person_conf = ch1 if _center_mean(ch1) >= _center_mean(ch0) else ch0
				else:
					return np.zeros((h, w), dtype=np.float32)
			else:
				person_conf = c0
			mask = np.clip(person_conf, 0.0, 1.0)
			if float(mask.mean()) < 1e-6:
				now = time.time()
				if now - _SEGMENTER_EMPTY_MASK_DEBUG_LAST >= 5.0:
					try:
						logger.error(
							"selfie segmenter confidence_masks(len=1) produced empty person mask. "
							"mask_min=%0.4f mask_max=%0.4f mask_mean=%0.6f",
							float(mask.min()),
							float(mask.max()),
							float(mask.mean()),
						)
					except Exception:
						logger.error("selfie segmenter confidence_masks(len=1) produced empty person mask. (debug extraction failed)")
				_SEGMENTER_EMPTY_MASK_DEBUG_LAST = now
			return cv2.GaussianBlur(mask, (21, 21), 0)

		# Standard path: two confidence maps (e.g. background/person).
		c0 = _squeeze_to_hw(_to_float_array(conf[0]))
		c1 = _squeeze_to_hw(_to_float_array(conf[1]))
		if c0.shape != (h, w):
			c0 = cv2.resize(c0, (w, h), interpolation=cv2.INTER_NEAREST)
		if c1.shape != (h, w):
			c1 = cv2.resize(c1, (w, h), interpolation=cv2.INTER_NEAREST)

		center_mean0 = _center_mean(c0)
		center_mean1 = _center_mean(c1)
		person_conf = c1 if center_mean1 >= center_mean0 else c0

		mask = np.clip(person_conf, 0.0, 1.0)
		if float(mask.mean()) < 1e-6:
			now = time.time()
			if now - _SEGMENTER_EMPTY_MASK_DEBUG_LAST >= 5.0:
				try:
					logger.error(
						"selfie segmenter confidence masks produced empty person mask. "
						"center_mean0=%0.6f center_mean1=%0.6f c0_min=%0.4f c0_max=%0.4f c1_min=%0.4f c1_max=%0.4f",
						center_mean0,
						center_mean1,
						float(c0.min()),
						float(c0.max()),
						float(c1.min()),
						float(c1.max()),
					)
				except Exception:
					logger.error("selfie segmenter confidence masks produced empty person mask. (debug extraction failed)")
				_SEGMENTER_EMPTY_MASK_DEBUG_LAST = now
		return cv2.GaussianBlur(mask, (21, 21), 0)
	except Exception as e:
		logger.error("selfie segmenter confidence mask extraction failed: %s", e, exc_info=True)
		return np.zeros((h, w), dtype=np.float32)


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

