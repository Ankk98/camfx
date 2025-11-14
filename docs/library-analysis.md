# Library Analysis: PipeWire & GStreamer Python Bindings

## Executive Summary

**Recommended Approach:** Use **PyGObject** with GStreamer's `pipewiresink` element to create virtual cameras without kernel modules.

**Primary Library:** `PyGObject` (Python bindings for GObject Introspection)  
**Complementary:** `gst-python` (optional, provides additional GStreamer overrides)  
**Not Recommended:** `pipewire_python` (audio-only, no video support)

---

## Library Comparison

### 1. PyGObject ⭐ **RECOMMENDED**

**PyPI:** https://pypi.org/project/PyGObject/  
**Documentation:** https://pygobject.readthedocs.io/  
**License:** LGPL-2.1+

#### Overview
Python bindings for GObject-based libraries using GObject Introspection. Provides access to GTK, GStreamer, GLib, GIO, and many other GNOME/GTK libraries.

#### Key Features
- ✅ **Mature & Stable** - Production-ready (Status: 5 - Production/Stable)
- ✅ **Comprehensive** - Supports GStreamer, PipeWire (via GStreamer), and many other libraries
- ✅ **Well-Documented** - Extensive documentation and examples
- ✅ **Active Maintenance** - Regular updates (latest: 3.54.5, Oct 2025)
- ✅ **Cross-Platform** - Linux, Windows, macOS
- ✅ **Python 3.9+** - Compatible with your requirements
- ✅ **Direct GStreamer Access** - Can use `pipewiresink` element directly

#### Installation
```bash
# Python package
pip install PyGObject

# System dependencies (Fedora)
sudo dnf install python3-gobject gstreamer1 gstreamer1-plugins-base gstreamer1-plugins-good
```

#### Usage Example
```python
import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst

# Initialize GStreamer
Gst.init(None)

# Create pipeline with pipewiresink
pipeline_str = (
    'appsrc name=source ! '
    'video/x-raw,format=RGB,width=1280,height=720,framerate=30/1 ! '
    'videoconvert ! '
    'pipewiresink name=sink'
)

pipeline = Gst.parse_launch(pipeline_str)
```

#### Pros
- Industry standard for GObject-based Python development
- Direct access to GStreamer's `pipewiresink` element
- No abstraction layers - direct control
- Excellent documentation and community support
- Used by major projects (GNOME apps, etc.)

#### Cons
- Requires system packages (GObject Introspection, GStreamer dev packages)
- Source-only distribution (needs C compiler)
- Slightly verbose API (but well-structured)

#### Verdict
**⭐ PRIMARY CHOICE** - This is the standard way to use GStreamer in Python. Direct, mature, and well-supported.

---

### 2. gst-python

**Repository:** https://github.com/GStreamer/gst-python  
**Status:** Merged into main GStreamer repository  
**License:** LGPL-2.1

#### Overview
Additional Python binding overrides that complement PyGObject's GStreamer bindings. Provides some convenience functions and additional functionality.

#### Key Features
- ✅ **Official** - Part of GStreamer project
- ✅ **Complements PyGObject** - Works alongside, not replacement
- ✅ **Additional Overrides** - Some convenience methods

#### Installation
Usually installed as part of GStreamer system packages:
```bash
# Fedora
sudo dnf install gstreamer1-python
```

#### Usage
Works automatically when installed - enhances PyGObject's GStreamer bindings.

#### Pros
- Official GStreamer project component
- Provides some additional convenience methods
- No separate installation needed (system package)

#### Cons
- Not a standalone solution - requires PyGObject
- Limited additional functionality
- May not be necessary for basic use cases

#### Verdict
**Optional Enhancement** - Install if available, but PyGObject alone is sufficient for most use cases.

---

### 3. gstreamer-python (by jackerSson)

**Repository:** https://github.com/jackersson/gstreamer-python  
**PyPI:** Not found (may not be published)

#### Overview
Abstraction layer over PyGObject's GStreamer API. Aims to simplify pipeline management and metadata handling.

#### Key Features
- ⚠️ **Abstraction Layer** - Wraps PyGObject
- ⚠️ **Simplified API** - May reduce verbosity
- ⚠️ **Third-Party** - Not official GStreamer project

#### Pros
- Potentially simpler API
- Pipeline management tools

#### Cons
- ❌ **Less Mature** - Third-party project
- ❌ **Additional Dependency** - Adds abstraction layer
- ❌ **Less Control** - Abstraction may hide needed features
- ❌ **Uncertain Maintenance** - Not part of official project
- ❌ **May Not Be on PyPI** - Installation complexity

#### Verdict
**❌ NOT RECOMMENDED** - Adds unnecessary abstraction. PyGObject is already well-designed and provides direct control.

---

### 4. pipewire_python

**PyPI:** https://pypi.org/project/pipewire_python/  
**Documentation:** https://pablodz.github.io/pipewire_python/

#### Overview
Python wrapper for controlling PipeWire, focusing on audio operations.

#### Key Features
- ✅ **Direct PipeWire Access** - Native PipeWire API
- ❌ **Audio-Only** - No video support currently
- ❌ **Limited Functionality** - Playback/recording only
- ⚠️ **Early Stage** - Less mature than GStreamer bindings

#### Installation
```bash
pip install pipewire_python
```

#### Pros
- Direct PipeWire API access
- Simpler for audio-only use cases

#### Cons
- ❌ **No Video Support** - Cannot create virtual cameras
- ❌ **Limited Scope** - Audio playback/recording only
- ❌ **Not Suitable** - For camfx's video requirements

#### Verdict
**❌ NOT SUITABLE** - Audio-only library. Cannot be used for virtual camera creation.

---

## Recommended Solution: PyGObject + GStreamer + pipewiresink

### Why This Approach?

1. **GStreamer's `pipewiresink` Element**
   - GStreamer has native PipeWire integration via the `pipewiresink` element
   - This element creates a PipeWire source that applications can access
   - No need for direct PipeWire Python bindings

2. **Mature & Proven**
   - GStreamer is battle-tested multimedia framework
   - PyGObject is the standard Python interface
   - Used by major applications (OBS, GNOME apps, etc.)

3. **Complete Solution**
   - Can handle video capture, processing, and output
   - PipeWire integration built-in
   - No kernel module required

### Architecture

```
[OpenCV Capture] → [MediaPipe Processing] → [GStreamer Pipeline] → [pipewiresink] → [PipeWire] → [Applications]
```

### Implementation Example

```python
import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst
import numpy as np
import cv2

class PipeWireOutput:
    def __init__(self, width, height, fps, name="camfx"):
        Gst.init(None)
        self.width = width
        self.height = height
        self.fps = fps
        
        # Create GStreamer pipeline
        pipeline_str = (
            f'appsrc name=source is-live=true format=time '
            f'caps=video/x-raw,format=RGB,width={width},height={height},framerate={fps}/1 ! '
            f'videoconvert ! '
            f'pipewiresink name=sink stream-properties="props,media.name={name}"'
        )
        
        self.pipeline = Gst.parse_launch(pipeline_str)
        self.appsrc = self.pipeline.get_by_name('source')
        
        # Configure appsrc
        self.appsrc.set_property('format', Gst.Format.TIME)
        self.appsrc.set_property('is-live', True)
        
        # Start pipeline
        self.pipeline.set_state(Gst.State.PLAYING)
        
    def send(self, frame_rgb):
        """Send RGB frame to PipeWire"""
        # Convert numpy array to GStreamer buffer
        height, width, channels = frame_rgb.shape
        size = width * height * channels
        
        buffer = Gst.Buffer.new_allocate(None, size, None)
        buffer.fill(0, frame_rgb.tobytes())
        
        # Set timestamp
        buffer.pts = Gst.util_get_timestamp()
        buffer.duration = Gst.SECOND // self.fps
        
        # Push buffer
        ret = self.appsrc.emit('push-buffer', buffer)
        if ret != Gst.FlowReturn.OK:
            print(f"Warning: push-buffer returned {ret}")
    
    def sleep_until_next_frame(self):
        """Frame timing handled by GStreamer"""
        pass
    
    def cleanup(self):
        """Stop pipeline"""
        self.pipeline.set_state(Gst.State.NULL)
```

### Dependencies

**requirements.txt:**
```
PyGObject>=3.42.0
```

**System packages (Fedora):**
```bash
sudo dnf install \
    python3-gobject \
    gstreamer1 \
    gstreamer1-plugins-base \
    gstreamer1-plugins-good \
    gstreamer1-plugins-bad-free \
    pipewire
```

**System packages (Ubuntu/Debian):**
```bash
sudo apt install \
    python3-gi \
    python3-gi-cairo \
    gir1.2-gstreamer-1.0 \
    gstreamer1.0-plugins-base \
    gstreamer1.0-plugins-good \
    pipewire
```

---

## Comparison Matrix

| Library | Video Support | PipeWire Support | Maturity | Maintenance | Recommendation |
|---------|--------------|------------------|----------|--------------|----------------|
| **PyGObject** | ✅ Yes (via GStreamer) | ✅ Yes (via pipewiresink) | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | **PRIMARY** |
| **gst-python** | ✅ Yes (complements PyGObject) | ✅ Yes | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | Optional |
| **gstreamer-python** | ✅ Yes | ✅ Yes | ⭐⭐ | ⭐⭐ | Not recommended |
| **pipewire_python** | ❌ No | ⚠️ Audio only | ⭐⭐ | ⭐⭐ | Not suitable |

---

## Migration Path

### Phase 1: Add PyGObject Backend
1. Install PyGObject and system dependencies
2. Create `PipeWireOutput` class using PyGObject
3. Test with simple frame output
4. Verify apps can see virtual camera

### Phase 2: Integrate with Core
1. Add backend abstraction to `core.py`
2. Support both v4l2loopback and PipeWire backends
3. Auto-detect available backends
4. Add `--backend` CLI option

### Phase 3: Make Default
1. Default to PipeWire if available
2. Fallback to v4l2loopback for older systems
3. Update documentation

---

## Testing Checklist

- [ ] PyGObject imports successfully
- [ ] GStreamer pipeline creates successfully
- [ ] `pipewiresink` element is available
- [ ] Virtual camera appears in `pw-cli list-sources`
- [ ] Firefox/Chrome can see virtual camera
- [ ] Zoom/Teams can see virtual camera
- [ ] Frame rate is acceptable (30 FPS)
- [ ] No kernel module required
- [ ] Works on Fedora (PipeWire default)
- [ ] Works on Ubuntu (with PipeWire installed)

---

## Code Example: Complete Integration

```python
# camfx/output_pipewire.py
import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst
import numpy as np
import time

class PipeWireBackend:
    """PipeWire virtual camera output using GStreamer"""
    
    def __init__(self, width, height, fps, name="camfx"):
        Gst.init(None)
        self.width = width
        self.height = height
        self.fps = fps
        self.name = name
        self.frame_time = 1.0 / fps
        
        # Create pipeline
        pipeline_str = (
            f'appsrc name=source is-live=true format=time do-timestamp=true '
            f'caps=video/x-raw,format=RGB,width={width},height={height},framerate={fps}/1 ! '
            f'videoconvert ! '
            f'pipewiresink name=sink stream-properties="props,media.name={name}"'
        )
        
        self.pipeline = Gst.parse_launch(pipeline_str)
        self.appsrc = self.pipeline.get_by_name('source')
        
        # Start pipeline
        ret = self.pipeline.set_state(Gst.State.PLAYING)
        if ret == Gst.StateChangeReturn.FAILURE:
            raise RuntimeError("Failed to start GStreamer pipeline")
        
        self.last_frame_time = time.time()
    
    def send(self, frame_rgb):
        """Send RGB frame (numpy array) to PipeWire"""
        if frame_rgb.shape[:2] != (self.height, self.width):
            raise ValueError(f"Frame size mismatch: expected ({self.height}, {self.width}), got {frame_rgb.shape[:2]}")
        
        # Convert to bytes
        data = frame_rgb.tobytes()
        size = len(data)
        
        # Create buffer
        buffer = Gst.Buffer.new_allocate(None, size, None)
        buffer.fill(0, data)
        
        # Set timestamp
        buffer.pts = Gst.util_get_timestamp()
        buffer.duration = int(Gst.SECOND / self.fps)
        
        # Push buffer
        ret = self.appsrc.emit('push-buffer', buffer)
        if ret != Gst.FlowReturn.OK:
            raise RuntimeError(f"Failed to push buffer: {ret}")
    
    def sleep_until_next_frame(self):
        """Maintain frame rate"""
        current_time = time.time()
        elapsed = current_time - self.last_frame_time
        sleep_time = max(0, self.frame_time - elapsed)
        if sleep_time > 0:
            time.sleep(sleep_time)
        self.last_frame_time = time.time()
    
    def cleanup(self):
        """Stop and cleanup pipeline"""
        if self.pipeline:
            self.pipeline.set_state(Gst.State.NULL)
            self.pipeline = None
```

---

## Conclusion

**Use PyGObject with GStreamer's `pipewiresink` element.**

This provides:
- ✅ No kernel module dependency
- ✅ Mature, well-supported libraries
- ✅ Direct PipeWire integration
- ✅ Full video support
- ✅ Production-ready solution

The combination of PyGObject + GStreamer + pipewiresink is the industry-standard approach for creating virtual cameras on modern Linux systems.

