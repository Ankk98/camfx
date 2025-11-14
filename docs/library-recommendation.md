# Library Recommendation: Quick Reference

## TL;DR

**Use PyGObject** - It's the industry-standard Python bindings for GStreamer and provides direct access to PipeWire via GStreamer's `pipewiresink` element.

## The Answer

| Library | Recommendation | Reason |
|---------|---------------|--------|
| **PyGObject** | ✅ **USE THIS** | Industry standard, mature, direct GStreamer access |
| **gst-python** | ✅ Optional | Complements PyGObject (system package) |
| **gstreamer-python** (jackerSson) | ❌ Skip | Unnecessary abstraction layer |
| **pipewire_python** | ❌ Skip | Audio-only, no video support |

## Quick Start

### Install

```bash
# Python package
pip install PyGObject

# System packages (Fedora)
sudo dnf install python3-gobject gstreamer1 gstreamer1-plugins-base gstreamer1-plugins-good pipewire
```

### Use

```python
import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst

Gst.init(None)

# Create virtual camera pipeline
pipeline = Gst.parse_launch(
    'appsrc name=source ! '
    'video/x-raw,format=RGB ! '
    'videoconvert ! '
    'pipewiresink'
)
```

## Why PyGObject?

1. **Mature** - Production-ready, used by GNOME, OBS, etc.
2. **Direct** - No abstraction layers, full control
3. **Complete** - Supports GStreamer's `pipewiresink` for virtual cameras
4. **Well-documented** - Extensive docs and examples
5. **Maintained** - Active development (latest: Oct 2025)

## Why Not Others?

- **pipewire_python**: Audio-only, cannot create virtual cameras
- **gstreamer-python** (jackerSson): Adds unnecessary abstraction
- **gst-python**: Optional complement, not a replacement

## Full Analysis

See `docs/library-analysis.md` for detailed comparison and implementation examples.

