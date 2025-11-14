# Alternatives to v4l2loopback Kernel Module

## Problem Statement

The current implementation relies on `v4l2loopback`, a kernel module that:
- Requires root/sudo privileges to load (`modprobe`)
- Has stability issues on newer kernels (as observed in MVP findings)
- Can cause system-wide issues when it crashes
- Requires kernel module compilation/installation
- Creates `/dev/video*` device nodes that may conflict with other devices

## Recommended Solution: PipeWire Virtual Camera

### Overview

**PipeWire** is the modern multimedia framework used by default on Fedora, GNOME, and many modern Linux distributions. It provides a userspace API for creating virtual camera sources without requiring any kernel modules.

### Advantages

1. **No kernel module required** - Pure userspace solution
2. **No root privileges needed** - Works with user permissions
3. **Better stability** - Userspace crashes don't affect the kernel
4. **Native integration** - Already the default on Fedora/GNOME
5. **Better performance** - Lower latency, better resource management
6. **Future-proof** - PipeWire is the direction Linux multimedia is heading

### Implementation Approach

#### Option 1: Use PipeWire Python Bindings (Recommended)

**Library:** `python-pipewire` or direct `libpipewire` bindings

**Implementation:**
```python
# New backend: camfx/output_pipewire.py
import pipewire as pw
import numpy as np
import cv2

class PipeWireOutput:
    def __init__(self, width, height, fps, name="camfx"):
        self.width = width
        self.height = height
        self.fps = fps
        self.name = name
        
        # Initialize PipeWire context
        self.context = pw.Context()
        self.core = self.context.connect()
        
        # Create virtual source
        props = {
            'media.class': 'Video/Source',
            'media.role': 'Camera',
            'pipewire.node.name': self.name,
            'pipewire.node.description': 'camfx Virtual Camera',
        }
        
        self.stream = self.core.create_stream(
            name=self.name,
            props=props,
            format=pw.VideoFormat(width, height, fps)
        )
        
    def send(self, frame_rgb):
        # Convert numpy array to PipeWire buffer
        # Send frame to PipeWire stream
        self.stream.push_frame(frame_rgb)
```

**Dependencies:**
- `python-pipewire` (if available) or
- `libpipewire` with Python bindings via `ctypes`/`cffi`

**Package Requirements:**
- `pipewire` (system package, usually pre-installed on Fedora)
- `pipewire-pulse` (for audio, if needed)

#### Option 2: Use GStreamer with PipeWire Sink

**Library:** `gstreamer-python` (Python bindings for GStreamer)

GStreamer can output directly to PipeWire, which many applications can then access.

**Implementation:**
```python
import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst

class GStreamerPipeWireOutput:
    def __init__(self, width, height, fps):
        Gst.init(None)
        self.width = width
        self.height = height
        self.fps = fps
        
        # Create GStreamer pipeline with PipeWire sink
        pipeline_str = (
            f'appsrc name=source is-live=true format=time '
            f'caps=video/x-raw,format=RGB,width={width},height={height},framerate={fps}/1 ! '
            f'videoconvert ! '
            f'pipewiresink name=sink'
        )
        
        self.pipeline = Gst.parse_launch(pipeline_str)
        self.appsrc = self.pipeline.get_by_name('source')
        self.pipeline.set_state(Gst.State.PLAYING)
        
    def send(self, frame_rgb):
        # Convert numpy to GStreamer buffer
        buffer = self._numpy_to_gst_buffer(frame_rgb)
        self.appsrc.emit('push-buffer', buffer)
```

**Dependencies:**
- `gstreamer-python` (Python package)
- `gstreamer1` (system package)
- `gstreamer1-plugins-base` (system package)
- `pipewire` (system package)

#### Option 3: Use OBS Virtual Camera Protocol (if available)

Some systems have OBS Virtual Camera that uses PipeWire. However, this may still use v4l2loopback under the hood on some systems.

### Migration Path

1. **Phase 1: Add PipeWire backend as alternative**
   - Keep v4l2loopback support for backward compatibility
   - Add `--backend pipewire` CLI option
   - Auto-detect available backends

2. **Phase 2: Make PipeWire the default**
   - Detect if PipeWire is available
   - Fall back to v4l2loopback if not available
   - Update documentation

3. **Phase 3: Remove v4l2loopback dependency**
   - Drop v4l2loopback support entirely
   - Update all documentation
   - Simplify installation instructions

### Code Changes Required

#### 1. Update `core.py`

```python
# Add backend abstraction
class OutputBackend(ABC):
    @abstractmethod
    def send(self, frame_rgb: np.ndarray) -> None:
        pass
    
    @abstractmethod
    def sleep_until_next_frame(self) -> None:
        pass

class V4L2LoopbackBackend(OutputBackend):
    def __init__(self, width, height, fps, device):
        import pyvirtualcam
        self.cam = pyvirtualcam.Camera(
            width=width, height=height, fps=fps, device=device
        )
    
    def send(self, frame_rgb):
        self.cam.send(frame_rgb)
    
    def sleep_until_next_frame(self):
        self.cam.sleep_until_next_frame()

class PipeWireBackend(OutputBackend):
    # Implementation using PipeWire
    pass
```

#### 2. Update CLI

```python
@click.option('--backend', type=click.Choice(['auto', 'pipewire', 'v4l2']), 
              default='auto', help='Output backend (auto-detect if not specified)')
```

#### 3. Update Dependencies

**requirements.txt:**
```
# Keep existing
mediapipe==0.10.0
opencv-python==4.8.0
click==8.1.7
numpy==1.24.0

# Add PipeWire support (choose one):
# Option A: If python-pipewire exists
python-pipewire>=0.1.0

# Option B: Use GStreamer
gstreamer-python>=1.20.0

# Option C: Keep pyvirtualcam for v4l2 fallback
pyvirtualcam==0.11.0  # Optional, for v4l2loopback fallback
```

**System dependencies (for package managers):**
- `pipewire` (usually pre-installed)
- `gstreamer1` and `gstreamer1-plugins-base` (if using GStreamer approach)

### Testing PipeWire Availability

```python
def detect_pipewire_available():
    """Check if PipeWire is available on the system."""
    import shutil
    # Check if pipewire process is running
    if shutil.which('pipewire'):
        # Try to connect to PipeWire
        try:
            # Attempt connection test
            return True
        except:
            return False
    return False
```

### Documentation Updates

#### README.md Changes

**Prerequisites:**
```markdown
Prerequisites
-------------
- Linux with PipeWire (default on Fedora, GNOME, modern distributions)
  OR v4l2loopback kernel module (legacy/fallback)
- Python 3.9+
```

**Quickstart:**
```markdown
Quickstart
----------
```bash
# 1) Create and activate virtual environment (optional but recommended)
python3 -m venv .venv
source .venv/bin/activate

# 2) Install package in editable mode
pip install -U pip wheel
pip install -e .

# 3) Run with background blur (uses PipeWire by default)
camfx blur --strength 25 --preview

# 4) Or use v4l2loopback backend (if PipeWire unavailable)
camfx blur --strength 25 --backend v4l2 --vdevice /dev/video10
```
```

**Troubleshooting:**
```markdown
Troubleshooting
---------------
- **PipeWire not detected**: Ensure PipeWire is installed and running:
  ```bash
  systemctl --user status pipewire
  ```
  On Fedora/GNOME, PipeWire is usually pre-installed.

- **Fallback to v4l2loopback**: If PipeWire is unavailable, use:
  ```bash
  sudo modprobe v4l2loopback devices=1 video_nr=10
  camfx blur --backend v4l2 --vdevice /dev/video10
  ```
```

## Alternative Solutions (Less Recommended)

### Option B: Use OBS Studio's Virtual Camera

**Approach:** Output to OBS Virtual Camera via its plugin API or network protocol.

**Pros:**
- OBS is widely used and stable
- Good integration with video apps

**Cons:**
- Requires OBS to be installed and running
- Adds another dependency
- May still use v4l2loopback on some systems

### Option C: Direct Application Integration

**Approach:** Create plugins/extensions for specific apps (Zoom, Teams, etc.)

**Pros:**
- Direct integration
- No virtual camera needed

**Cons:**
- Requires separate plugin for each app
- High maintenance burden
- Not scalable

### Option D: Use FFmpeg to Stream to V4L2 Device

**Approach:** Use FFmpeg to write to v4l2 device without pyvirtualcam

**Pros:**
- FFmpeg is well-tested
- More control over format

**Cons:**
- Still requires v4l2loopback kernel module
- Doesn't solve the root problem

## Recommendation

**Use PipeWire Virtual Camera (Option 1 or 2)** because:

1. **Native to modern Linux** - Already installed on Fedora/GNOME
2. **No kernel module** - Pure userspace solution
3. **Better stability** - Won't crash the kernel
4. **Future-proof** - PipeWire is the direction Linux is heading
5. **Better performance** - Lower latency, better resource management
6. **No root required** - Works with user permissions

**Implementation Priority:**
1. Start with GStreamer approach (Option 2) - more mature Python bindings
2. If `python-pipewire` becomes available, migrate to direct PipeWire API (Option 1)
3. Keep v4l2loopback as fallback for older systems

## Next Steps

1. **Research available libraries:**
   - Check if `python-pipewire` package exists
   - Evaluate `gstreamer-python` maturity and API
   - Test PipeWire availability on target systems

2. **Prototype implementation:**
   - Create `PipeWireBackend` class
   - Test with simple frame output
   - Verify apps can see the virtual camera

3. **Integration:**
   - Add backend selection to CLI
   - Update core.py to support multiple backends
   - Add auto-detection logic

4. **Testing:**
   - Test on Fedora (PipeWire default)
   - Test on Ubuntu (may need PipeWire installation)
   - Test fallback to v4l2loopback

5. **Documentation:**
   - Update README with new prerequisites
   - Update installation instructions
   - Add troubleshooting section

