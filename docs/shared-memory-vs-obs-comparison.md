# Shared Memory vs OBS Backend: Decision Guide

## Your Current Situation

- **camfx**: Lightweight Python app for camera effects (blur, background replacement)
- **Goal**: Virtual camera for Firefox/Google Meet
- **Issues**: v4l2loopback and PipeWire have problems
- **Current**: Using PipeWire directly (works technically, but not visible to most apps)

---

## Option 1: Shared Memory + Helper Daemon

### How It Works
1. **camfx process**: Writes processed frames to shared memory
2. **Helper daemon** (separate process): Reads from shared memory, writes to v4l2loopback device
3. **Applications**: Read from `/dev/videoX` (created by v4l2loopback)

### Architecture
```
camfx (Python) 
  → Shared Memory Queue
    → Helper Daemon (C/Python)
      → v4l2loopback kernel module
        → /dev/videoX
          → Firefox/Google Meet
```

### Pros ✅
- **Lightweight**: No heavy dependencies
- **Separation of concerns**: Your app vs. device management
- **Better error handling**: Helper can restart without affecting camfx
- **Easier debugging**: Can inspect shared memory independently
- **Full control**: Customize exactly for your needs
- **Minimal changes**: Just replace PipeWire output with shared memory write
- **Can support multiple backends**: v4l2loopback, akvcam, etc.

### Cons ❌
- **Still needs kernel module**: v4l2loopback (but managed by helper)
- **Two processes**: Slightly more complex architecture
- **Need to write helper**: ~200-300 lines of C or Python
- **Shared memory management**: Need to handle cleanup, locking

### Implementation Complexity
- **Shared memory code**: ~100 lines (Python `mmap` or `multiprocessing.shared_memory`)
- **Helper daemon**: ~200-300 lines (C with v4l2 ioctls, or Python with `v4l2-python3`)
- **Total**: ~300-400 lines of new code

### Code Sketch
```python
# camfx/output_sharedmem.py
import mmap
import struct
from multiprocessing import shared_memory

class SharedMemoryOutput:
    def __init__(self, width, height, fps):
        # Create shared memory
        self.shm = shared_memory.SharedMemory(create=True, size=frame_size * 3)
        self.header = struct.pack('IIIQQ', width, height, fps, write_idx, read_idx)
        # Write header to shm
        
    def send(self, frame_data):
        # Write frame to shared memory
        # Update write index
        pass
```

```python
# camfx/helper_daemon.py (or C equivalent)
import v4l2
# Read from shared memory
# Write to /dev/videoX via v4l2loopback
```

---

## Option 2: Use OBS as Backend

### How It Works
1. **camfx**: Outputs to OBS via plugin or OBS Virtual Camera API
2. **OBS**: Handles virtual camera creation (uses v4l2loopback on Linux)
3. **Applications**: Read from OBS's virtual camera

### Architecture
```
camfx (Python)
  → OBS Plugin/API
    → OBS Virtual Camera Output
      → v4l2loopback (OBS manages this)
        → /dev/videoX
          → Firefox/Google Meet
```

### Pros ✅
- **Well-tested**: OBS virtual camera is mature
- **Cross-platform**: OBS handles platform differences
- **No helper daemon**: OBS manages everything
- **Rich features**: OBS has many options (scenes, filters, etc.)

### Cons ❌
- **Heavy dependency**: OBS is ~50MB+ and complex
- **OBS on Linux**: Still uses v4l2loopback under the hood (doesn't solve your problem)
- **Integration complexity**: Need OBS plugin or use OBS as library
- **Overkill**: OBS is designed for streaming/recording, not just virtual camera
- **User experience**: Users need to install and run OBS separately
- **Less control**: Dependent on OBS's implementation and updates

### Implementation Complexity
- **OBS Plugin**: ~500-1000 lines (C/C++ with OBS SDK)
- **OR OBS as library**: Complex, OBS isn't really designed as a library
- **Total**: Much more complex than shared memory approach

### Integration Options

#### Option 2a: OBS Plugin
- Write an OBS source plugin that reads from camfx
- Requires C/C++ and OBS SDK knowledge
- Complex build system

#### Option 2b: OBS Virtual Camera Input
- Use OBS's virtual camera as input source
- But OBS doesn't have a simple "feed me frames" API
- Would need to use OBS's scene system

#### Option 2c: OBS NDI Output
- Output via NDI, OBS receives NDI
- Adds network dependency
- More complexity

---

## Recommendation: **Shared Memory + Helper Daemon** ✅

### Why?

1. **Solves your actual problem**: The issue isn't the approach, it's that v4l2loopback needs proper management. A helper daemon can handle this better.

2. **Fits your project**: camfx is lightweight and focused. OBS is overkill.

3. **Better architecture**: Separation of concerns makes debugging easier.

4. **More maintainable**: Less code, fewer dependencies, easier to understand.

5. **Flexible**: Can easily add support for akvcam or other backends later.

### Implementation Plan

#### Phase 1: Shared Memory Output (Replace PipeWire)
```python
# Replace output_pipewire.py with output_sharedmem.py
# ~100 lines, uses multiprocessing.shared_memory
```

#### Phase 2: Helper Daemon
```python
# New file: camfx/helper_daemon.py
# ~200-300 lines, uses v4l2-python3 or pyv4l2
# Reads from shared memory, writes to v4l2loopback
```

#### Phase 3: Integration
- Helper daemon can be started automatically by camfx
- Or run as separate systemd user service
- Handles v4l2loopback device creation/cleanup

### Why Not OBS?

1. **Doesn't solve the problem**: OBS on Linux still uses v4l2loopback, so you'd still have the same kernel module issues.

2. **Too heavy**: OBS is designed for streaming/recording, not just virtual camera.

3. **Complex integration**: Would require C/C++ plugin development.

4. **User experience**: Users would need to install and configure OBS separately.

---

## Alternative: Fix v4l2loopback Issues First

Before implementing shared memory, consider:

1. **What exactly failed with v4l2loopback?**
   - Module won't load?
   - Device creation fails?
   - Permission issues?
   - Applications can't see device?

2. **Can we fix it?**
   - Better error messages
   - Automatic module loading
   - Permission handling
   - Device management

If v4l2loopback can be made to work reliably, you might not need shared memory at all - just write directly to v4l2loopback from camfx.

---

## Decision Matrix

| Factor | Shared Memory | OBS Backend |
|--------|--------------|-------------|
| **Complexity** | Medium (300-400 lines) | High (500-1000+ lines) |
| **Dependencies** | Minimal (v4l2-python3) | Heavy (OBS + SDK) |
| **Maintenance** | Low (simple code) | High (OBS updates) |
| **User Experience** | Good (transparent) | Poor (need OBS) |
| **Solves Problem** | ✅ Yes (better management) | ❌ No (still uses v4l2loopback) |
| **Fits Project** | ✅ Yes (lightweight) | ❌ No (overkill) |
| **Flexibility** | ✅ High | ❌ Low (OBS constraints) |

---

## Final Recommendation

**Use Shared Memory + Helper Daemon** because:
1. It's the right level of complexity for your project
2. It actually solves the problem (better v4l2loopback management)
3. It's more maintainable and flexible
4. It doesn't add heavy dependencies

**Next Steps**:
1. Investigate why v4l2loopback failed (check logs, kernel messages)
2. Implement shared memory output (replace PipeWire)
3. Create helper daemon that manages v4l2loopback properly
4. Test with Firefox/Google Meet

If you want, I can help implement the shared memory + helper daemon approach!

