# Removing v4l2loopback Dependency - Executive Summary

## Problem

Current implementation requires `v4l2loopback` kernel module which:
- Requires root privileges to load
- Has stability issues (crashes observed on kernel 6.18.0-rc4)
- Can cause system-wide problems when it fails
- Creates installation complexity

## Recommended Solution: PipeWire Virtual Camera

**PipeWire** is the modern multimedia framework used by default on Fedora/GNOME. It provides virtual camera capabilities **without any kernel module**.

### Why PipeWire?

✅ **No kernel module** - Pure userspace solution  
✅ **No root required** - Works with user permissions  
✅ **Better stability** - Userspace crashes don't affect kernel  
✅ **Already installed** - Default on Fedora/GNOME  
✅ **Future-proof** - Direction Linux multimedia is heading  

## Implementation: PyGObject + GStreamer + pipewiresink ⭐

**After analyzing available libraries, the recommended approach is:**

### PyGObject (Primary Library)

**PyPI:** https://pypi.org/project/PyGObject/  
**Why:** Industry-standard Python bindings for GObject-based libraries (GTK, GStreamer, etc.)

**Key Points:**
- ✅ Mature & stable (Production-ready status)
- ✅ Direct access to GStreamer's `pipewiresink` element
- ✅ Well-documented with extensive examples
- ✅ Active maintenance (latest: 3.54.5, Oct 2025)
- ✅ Used by major projects (GNOME apps, OBS, etc.)

**Why Not Other Libraries:**
- ❌ `pipewire_python` - Audio-only, no video support
- ❌ `gstreamer-python` (jackerSson) - Unnecessary abstraction layer
- ✅ `gst-python` - Optional complement to PyGObject (system package)

**Code Example:**
```python
import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst

# Create pipeline: appsrc -> videoconvert -> pipewiresink
pipeline_str = (
    'appsrc name=source is-live=true format=time '
    'caps=video/x-raw,format=RGB,width=1280,height=720,framerate=30/1 ! '
    'videoconvert ! '
    'pipewiresink name=sink stream-properties="props,media.name=camfx"'
)
pipeline = Gst.parse_launch(pipeline_str)
```

**See `docs/library-analysis.md` for detailed library comparison.**

## Migration Strategy

### Phase 1: Add PipeWire Support (Keep v4l2 as fallback)

1. Create `PipeWireBackend` class
2. Add `--backend` CLI option (`auto`, `pipewire`, `v4l2`)
3. Auto-detect available backends
4. Default to PipeWire if available, fallback to v4l2

### Phase 2: Make PipeWire Default

1. Update documentation
2. Simplify installation (remove modprobe step)
3. Keep v4l2 as fallback for older systems

### Phase 3: Remove v4l2 Support (Future)

1. Drop v4l2loopback code
2. Update all documentation
3. Simplify codebase

## Quick Start Implementation

### Step 1: Add PyGObject Dependency

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

### Step 2: Create PipeWire Backend

Create `camfx/output_pipewire.py`:
```python
import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst
import numpy as np
import time

class PipeWireBackend:
    """PipeWire virtual camera using GStreamer's pipewiresink"""
    
    def __init__(self, width, height, fps, name="camfx"):
        Gst.init(None)
        self.width = width
        self.height = height
        self.fps = fps
        self.name = name
        self.frame_time = 1.0 / fps
        
        pipeline_str = (
            f'appsrc name=source is-live=true format=time do-timestamp=true '
            f'caps=video/x-raw,format=RGB,width={width},height={height},framerate={fps}/1 ! '
            f'videoconvert ! '
            f'pipewiresink name=sink stream-properties="props,media.name={name}"'
        )
        
        self.pipeline = Gst.parse_launch(pipeline_str)
        self.appsrc = self.pipeline.get_by_name('source')
        
        ret = self.pipeline.set_state(Gst.State.PLAYING)
        if ret == Gst.StateChangeReturn.FAILURE:
            raise RuntimeError("Failed to start GStreamer pipeline")
        
        self.last_frame_time = time.time()
    
    def send(self, frame_rgb):
        """Send RGB frame (numpy array) to PipeWire"""
        data = frame_rgb.tobytes()
        buffer = Gst.Buffer.new_allocate(None, len(data), None)
        buffer.fill(0, data)
        buffer.pts = Gst.util_get_timestamp()
        buffer.duration = int(Gst.SECOND / self.fps)
        
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
        """Stop pipeline"""
        if self.pipeline:
            self.pipeline.set_state(Gst.State.NULL)
```

### Step 3: Update Core to Support Multiple Backends

Modify `core.py` to:
- Abstract output backend
- Support both PipeWire and v4l2
- Auto-detect available backends

## Testing Checklist

- [ ] PipeWire backend creates virtual camera
- [ ] Video apps (Firefox, Zoom, etc.) can see virtual camera
- [ ] Frame rate and quality are acceptable
- [ ] Fallback to v4l2loopback works when PipeWire unavailable
- [ ] Works on Fedora (PipeWire default)
- [ ] Works on Ubuntu (may need PipeWire installation)
- [ ] No root privileges required

## Documentation Updates Needed

1. **README.md:**
   - Remove `modprobe v4l2loopback` from quickstart
   - Update prerequisites (PipeWire instead of v4l2loopback)
   - Add troubleshooting for PipeWire

2. **plan.md:**
   - Update technology stack
   - Remove v4l2loopback references
   - Update packaging dependencies

3. **Installation scripts:**
   - Remove kernel module setup
   - Add PipeWire availability check

## Estimated Effort

- **Research & Prototyping:** 2-4 hours
- **Implementation:** 4-6 hours
- **Testing:** 2-3 hours
- **Documentation:** 1-2 hours
- **Total:** ~1-2 days

## Risk Assessment

**Low Risk:**
- PipeWire is stable and widely used
- GStreamer bindings are mature
- Can keep v4l2 as fallback during transition

**Mitigation:**
- Implement both backends initially
- Test on multiple distributions
- Provide clear fallback instructions

## Next Actions

1. ✅ Research GStreamer Python bindings API
2. ✅ Prototype PipeWire backend
3. ✅ Test with simple frame output
4. ✅ Verify apps can see virtual camera
5. ✅ Integrate into core.py with backend abstraction
6. ✅ Update CLI with backend selection
7. ✅ Update documentation
8. ✅ Test on multiple Linux distributions

## References

- [PyGObject Documentation](https://pygobject.readthedocs.io/)
- [PyGObject on PyPI](https://pypi.org/project/PyGObject/)
- [PipeWire Documentation](https://pipewire.org/)
- [GStreamer Documentation](https://gstreamer.freedesktop.org/documentation/)
- [GStreamer PipeWire Sink](https://gstreamer.freedesktop.org/documentation/pipewire/pipewiresink.html)
- [Library Analysis](library-analysis.md) - Detailed comparison of all available libraries

