"""Effect metadata for CLI help and validation."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class EffectParam:
	flag: str
	help: str
	value_range: str | None = None
	default: str | None = None
	notes: str | None = None


@dataclass(frozen=True, slots=True)
class EffectSpec:
	key: str
	title: str
	description: str
	params: tuple[EffectParam, ...]
	requires_mediapipe_tasks: bool = False


EFFECT_SPECS: tuple[EffectSpec, ...] = (
	EffectSpec(
		key="blur",
		title="Background blur",
		description="Blur background using person segmentation mask.",
		requires_mediapipe_tasks=True,
		params=(
			EffectParam(
				flag="--strength",
				help="Gaussian blur kernel size (auto-adjusts even to odd).",
				value_range="int > 0",
				default="25",
			),
		),
	),
	EffectSpec(
		key="replace",
		title="Background replace",
		description="Replace background with an image using person segmentation mask.",
		requires_mediapipe_tasks=True,
		params=(
			EffectParam(
				flag="--image",
				help="Path to background image file.",
				value_range="path",
				default="(built-in default image if omitted)",
			),
		),
	),
	EffectSpec(
		key="brightness",
		title="Brightness/contrast",
		description="Adjust brightness/contrast globally (or face-only when mask available).",
		params=(
			EffectParam(flag="--brightness", help="Brightness offset.", value_range="-100..100", default="0"),
			EffectParam(flag="--contrast", help="Contrast multiplier.", value_range="0.5..2.0", default="1.0"),
			EffectParam(
				flag="--face-only",
				help="Apply adjustment only to masked region (requires segmentation mask).",
				value_range="bool",
				default="false",
				notes="When enabled, the mask comes from the segmentation backend.",
			),
		),
	),
	EffectSpec(
		key="beautify",
		title="Beautify",
		description="Skin smoothing based on face landmarks.",
		requires_mediapipe_tasks=True,
		params=(
			EffectParam(flag="--smoothness", help="Bilateral filter strength.", value_range="1..15", default="5"),
		),
	),
	EffectSpec(
		key="autoframe",
		title="Auto frame",
		description="Crop/zoom to keep the face centered.",
		requires_mediapipe_tasks=True,
		params=(
			EffectParam(flag="--padding", help="Padding around face.", value_range="0.0..1.0", default="0.3"),
			EffectParam(flag="--min-zoom", help="Minimum zoom.", value_range=">= 1.0", default="1.0"),
			EffectParam(flag="--max-zoom", help="Maximum zoom.", value_range=">= min-zoom", default="2.0"),
		),
	),
	EffectSpec(
		key="gaze-correct",
		title="Gaze correction",
		description="Warp eye regions to look closer to the camera (experimental).",
		requires_mediapipe_tasks=True,
		params=(
			EffectParam(flag="--strength", help="Correction strength.", value_range="0.0..1.0", default="0.5"),
		),
	),
)


EFFECT_KEYS = tuple(spec.key for spec in EFFECT_SPECS)


def get_effect_spec(key: str) -> EffectSpec | None:
	for spec in EFFECT_SPECS:
		if spec.key == key:
			return spec
	return None

