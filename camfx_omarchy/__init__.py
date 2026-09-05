"""camfx_omarchy — Omarchy-native plugin layer (Q1–Q26, v0.4.0).

This package is *optional*: ``pip install camfx[omarchy]`` on Omarchy only.
Core ``camfx`` never imports this module unless ``omarchy_detection.is_omarchy()``
or an explicit ``omarchy-camfx`` command is invoked.
"""

from importlib.metadata import version as _pkg_version

try:
	__version__ = _pkg_version("camfx")
except Exception:
	__version__ = "0.2.0a1"
