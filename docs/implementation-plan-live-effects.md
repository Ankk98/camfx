# Implementation Plan: Live Effects, On-Demand Webcam, and Effect Chaining

## Overview

This document outlines the plan for implementing three key features:
1. **Live effect switching** - Change effects during runtime without restarting
2. **On-demand webcam usage** - Only use webcam when virtual camera source is actively being consumed
3. **Effect chaining** - Apply multiple effects in sequence

---

## Current Architecture Analysis

### Current State

**`VideoEnhancer` class (`core.py`):**
- Opens camera immediately in `__init__`
- Creates a single effect at initialization
- Runs a blocking loop that processes frames continuously
- No mechanism to change effects or detect source usage

**Effect System (`effects.py`):**
- Each effect is a separate class with an `apply()` method
- Effects take `(frame, mask, **kwargs)` as input
- No support for chaining multiple effects

**PipeWire Output (`output_pipewire.py`):**
- Creates GStreamer pipeline immediately
- Sends frames continuously once started
- No mechanism to detect when source is being consumed

### Limitations

1. **No runtime control**: Effects are set at startup and cannot be changed
2. **Always-on webcam**: Camera is opened and stays open even when not in use
3. **Single effect**: Only one effect can be applied at a time
4. **Blocking design**: Main loop blocks, making it hard to add interactive controls

---

## Design Goals

1. **Non-blocking architecture**: Support runtime changes without restart
2. **Resource efficiency**: Only use webcam when virtual camera is actively consumed
3. **Flexible effects**: Support single effects and effect chains
4. **Backward compatibility**: Existing CLI commands should still work
5. **Multiple consumers**: Support multiple applications reading from virtual camera simultaneously
6. **Desktop integration**: D-Bus interface for GUI and system integration

---

## Implementation Plan

### Phase 1: Architecture Refactoring

#### 1.1 Separate Control Thread from Processing Loop

**Current Problem:**
- Single blocking loop handles everything
- No way to inject commands during runtime

**Solution:**
- Create a control interface (D-Bus, Unix socket, or file-based)
- Separate processing thread from control thread
- Use thread-safe queues for effect changes

**Changes Needed:**

**New file: `camfx/control.py`**
```python
import threading
import queue
from typing import Optional, List, Dict, Any
from .effects import BackgroundBlur, BackgroundReplace, BrightnessAdjustment, ...

class EffectChain:
    """Manages a chain of effects to apply in sequence."""
    def __init__(self):
        self.effects: List[tuple] = []  # List of (effect_instance, config_dict)
    
    def add_effect(self, effect_type: str, config: Dict[str, Any]):
        """Add an effect to the chain."""
        effect = self._create_effect(effect_type)
        self.effects.append((effect, config))
    
    def remove_effect(self, index: int):
        """Remove an effect from the chain."""
        if 0 <= index < len(self.effects):
            del self.effects[index]
    
    def clear(self):
        """Clear all effects."""
        self.effects = []
    
    def apply(self, frame, mask, **kwargs):
        """Apply all effects in sequence."""
        result = frame
        for effect, config in self.effects:
            # Merge kwargs with effect-specific config
            effect_kwargs = {**config, **kwargs}
            result = effect.apply(result, mask, **effect_kwargs)
        return result

class EffectController:
    """Thread-safe controller for managing effects."""
    def __init__(self):
        self.chain = EffectChain()
        self.lock = threading.Lock()
        self.change_queue = queue.Queue()
    
    def set_effect(self, effect_type: str, config: Dict[str, Any]):
        """Replace all effects with a single effect."""
        with self.lock:
            self.chain.clear()
            self.chain.add_effect(effect_type, config)
    
    def add_effect(self, effect_type: str, config: Dict[str, Any]):
        """Add an effect to the chain."""
        with self.lock:
            self.chain.add_effect(effect_type, config)
    
    def get_chain(self) -> EffectChain:
        """Get current effect chain (thread-safe copy)."""
        with self.lock:
            # Return a copy to avoid race conditions
            chain_copy = EffectChain()
            chain_copy.effects = self.chain.effects.copy()
            return chain_copy
```

#### 1.2 Add PipeWire Source Usage Detection (Using libpipewire)

**Current Problem:**
- No way to know if virtual camera is being used
- Webcam stays open even when no app is consuming the source
- Need to support multiple simultaneous consumers

**Solution:**
- Use libpipewire Python bindings to monitor source node state
- Subscribe to PipeWire events for real-time updates
- Track active client connections (support multiple consumers)
- Start/stop webcam capture based on usage

**Changes Needed:**

**Dependencies:**
- Add `python-pipewire` or use `pygobject` with PipeWire GObject introspection
- Alternative: Use `pypipewire` package if available
- Or use `gi.repository.PipeWire` via PyGObject

**New file: `camfx/pipewire_monitor.py`**
```python
import threading
from typing import Optional, Callable, Set
import gi

gi.require_version('PipeWire', '0.3')
from gi.repository import PipeWire, GLib

class PipeWireSourceMonitor:
    """Monitor PipeWire source usage using libpipewire to detect when it's being consumed.
    
    Supports multiple simultaneous consumers - camera stays active as long as
    at least one client is connected.
    """
    
    def __init__(self, source_name: str = "camfx"):
        self.source_name = source_name
        self.active_clients: Set[int] = set()  # Track client IDs
        self.is_used = False
        self.callback: Optional[Callable[[bool], None]] = None
        self.monitoring = False
        
        # PipeWire context and core
        self.context: Optional[PipeWire.Context] = None
        self.core: Optional[PipeWire.Core] = None
        self.registry: Optional[PipeWire.Registry] = None
        self.source_node_id: Optional[int] = None
        
        # GLib main loop for event handling
        self.main_loop: Optional[GLib.MainLoop] = None
        self.loop_thread: Optional[threading.Thread] = None
    
    def _on_registry_global(self, registry, id, permissions, type, version, props):
        """Callback when a new global object is registered."""
        if type == PipeWire.types.DICT_ENTRY_SPA_TYPE_INFO_Node:
            # Check if this is our source node
            name = props.get('media.name', '')
            if name == self.source_name:
                self.source_node_id = id
                print(f"Found source node: {self.source_name} (id: {id})")
                # Monitor links for this node
                self._update_usage_state()
    
    def _on_registry_global_remove(self, registry, id):
        """Callback when a global object is removed."""
        if id == self.source_node_id:
            self.source_node_id = None
            self.active_clients.clear()
            self._update_usage_state()
    
    def _on_link_state_changed(self, link, state):
        """Callback when a link state changes."""
        # Check if this link is connected to our source node
        if self.source_node_id is None:
            return
        
        # Get link properties
        props = link.get_properties()
        output_node_id = props.get('link.output.node', 0)
        
        if output_node_id == self.source_node_id:
            input_node_id = props.get('link.input.node', 0)
            
            if state == PipeWire.LinkState.ACTIVE:
                # Link is active, add client
                if input_node_id not in self.active_clients:
                    self.active_clients.add(input_node_id)
                    print(f"Client connected (node {input_node_id}). Active clients: {len(self.active_clients)}")
                    self._update_usage_state()
            elif state in [PipeWire.LinkState.UNLINKED, PipeWire.LinkState.ERROR]:
                # Link removed, remove client
                if input_node_id in self.active_clients:
                    self.active_clients.remove(input_node_id)
                    print(f"Client disconnected (node {input_node_id}). Active clients: {len(self.active_clients)}")
                    self._update_usage_state()
    
    def _update_usage_state(self):
        """Update usage state based on active clients."""
        was_used = self.is_used
        self.is_used = len(self.active_clients) > 0
        
        if was_used != self.is_used:
            if self.callback:
                self.callback(self.is_used)
    
    def _setup_pipewire_connection(self):
        """Set up PipeWire connection and event handlers."""
        try:
            # Create PipeWire context
            self.context = PipeWire.Context.new()
            self.core = self.context.connect(None)
            
            if self.core is None:
                raise RuntimeError("Failed to connect to PipeWire")
            
            # Get registry to monitor nodes and links
            self.registry = self.core.get_registry()
            
            # Connect to registry events
            self.registry.connect('global', self._on_registry_global)
            self.registry.connect('global-remove', self._on_registry_global_remove)
            
            # Update registry to get current state
            self.core.sync(PipeWire.types.PW_ID_CORE, 0)
            
            print("PipeWire connection established")
            
        except Exception as e:
            print(f"Failed to set up PipeWire connection: {e}")
            raise
    
    def _main_loop_thread(self):
        """Run GLib main loop in separate thread."""
        try:
            self.main_loop = GLib.MainLoop.new(None, False)
            self.main_loop.run()
        except Exception as e:
            print(f"Error in main loop: {e}")
    
    def start_monitoring(self, callback: Callable[[bool], None]):
        """Start monitoring source usage and call callback when state changes."""
        self.callback = callback
        
        try:
            # Set up PipeWire connection
            self._setup_pipewire_connection()
            
            # Start GLib main loop in separate thread
            self.monitoring = True
            self.loop_thread = threading.Thread(target=self._main_loop_thread, daemon=True)
            self.loop_thread.start()
            
            # Give it a moment to initialize
            import time
            time.sleep(0.5)
            
            # Initial state check
            self._update_usage_state()
            
        except Exception as e:
            print(f"Failed to start PipeWire monitoring: {e}")
            print("Falling back to always-on camera mode")
            self.monitoring = False
            # Call callback with False to indicate monitoring failed
            if self.callback:
                self.callback(False)
    
    def stop_monitoring(self):
        """Stop monitoring."""
        self.monitoring = False
        
        if self.main_loop:
            self.main_loop.quit()
        
        if self.loop_thread:
            self.loop_thread.join(timeout=2.0)
        
        # Clean up PipeWire connection
        if self.core:
            self.core.disconnect()
        if self.context:
            self.context.destroy()
        
        self.active_clients.clear()
        self.source_node_id = None
```

**Note on Multiple Consumers:**
- PipeWire natively supports multiple consumers reading from the same source
- Our GStreamer pipeline with `pipewiresink` creates a single source node
- Multiple applications can connect to this source simultaneously
- Camera should stay active as long as **any** client is connected
- The monitor tracks all active client connections

#### 1.3 Refactor VideoEnhancer for Lazy Camera Initialization

**Changes Needed:**

**Modify `camfx/core.py`:**
```python
class VideoEnhancer:
    def __init__(self, input_device: int = 0, effect_type: str = 'blur', 
                 config: dict | None = None, enable_lazy_camera: bool = True):
        self.input_device = input_device
        self.config = config or {}
        self.enable_lazy_camera = enable_lazy_camera
        
        # Camera is not opened immediately if lazy mode is enabled
        self.cap: Optional[cv2.VideoCapture] = None
        self.camera_active = False
        
        # Initialize effect controller
        from .control import EffectController
        self.effect_controller = EffectController()
        
        # Set initial effect
        if effect_type:
            initial_config = self._get_effect_config(effect_type, config)
            self.effect_controller.set_effect(effect_type, initial_config)
        
        # Initialize PipeWire output (always, even if camera not active)
        self.virtual_cam = None
        if self.config.get('enable_virtual', True):
            # ... existing PipeWire initialization ...
            pass
        
        # Initialize source monitor
        if enable_lazy_camera:
            from .pipewire_monitor import PipeWireSourceMonitor
            camera_name = self.config.get('camera_name', 'camfx')
            self.source_monitor = PipeWireSourceMonitor(camera_name)
            self.source_monitor.start_monitoring(self._on_source_usage_changed)
    
    def _on_source_usage_changed(self, is_used: bool):
        """Callback when source usage changes."""
        if is_used and not self.camera_active:
            self._start_camera()
        elif not is_used and self.camera_active:
            self._stop_camera()
    
    def _start_camera(self):
        """Start camera capture."""
        if self.cap is not None:
            return  # Already started
        
        print(f"Starting camera (source is in use)...")
        self.cap = cv2.VideoCapture(self.input_device)
        if not self.cap.isOpened():
            print(f"Warning: Failed to open camera {self.input_device}")
            return
        
        # Set resolution if specified
        if 'width' in self.config:
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, int(self.config['width']))
        if 'height' in self.config:
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, int(self.config['height']))
        
        self.camera_active = True
        print("Camera started")
    
    def _stop_camera(self):
        """Stop camera capture."""
        if self.cap is None:
            return
        
        print("Stopping camera (source not in use)...")
        self.cap.release()
        self.cap = None
        self.camera_active = False
        print("Camera stopped")
    
    def set_effect(self, effect_type: str, config: dict):
        """Change effect at runtime."""
        effect_config = self._get_effect_config(effect_type, config)
        self.effect_controller.set_effect(effect_type, effect_config)
        print(f"Effect changed to: {effect_type}")
    
    def add_effect(self, effect_type: str, config: dict):
        """Add effect to chain at runtime."""
        effect_config = self._get_effect_config(effect_type, config)
        self.effect_controller.add_effect(effect_type, effect_config)
        print(f"Effect added to chain: {effect_type}")
    
    def run(self, preview: bool = False, **kwargs):
        """Main processing loop with lazy camera support."""
        try:
            if preview:
                cv2.namedWindow('camfx preview', cv2.WINDOW_NORMAL)
                print("Preview window created. Press 'q' to quit.")
            
            # If lazy camera is disabled, start camera immediately
            if not self.enable_lazy_camera:
                self._start_camera()
            
            frame_count = 0
            while True:
                # Check if camera should be active
                if self.enable_lazy_camera and not self.camera_active:
                    # Send a black frame or last frame when camera is off
                    if self.virtual_cam is not None:
                        # Send black frame
                        black_frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)
                        frame_rgb = cv2.cvtColor(black_frame, cv2.COLOR_BGR2RGB)
                        self.virtual_cam.send(frame_rgb.tobytes())
                        self.virtual_cam.sleep_until_next_frame()
                    
                    if preview:
                        # Show message in preview
                        display_frame = np.zeros((480, 640, 3), dtype=np.uint8)
                        cv2.putText(display_frame, "Camera inactive (source not in use)", 
                                   (10, 240), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
                        cv2.imshow('camfx preview', display_frame)
                        key = cv2.waitKey(1) & 0xFF
                        if key == ord('q'):
                            break
                    
                    time.sleep(0.1)  # Small delay when inactive
                    continue
                
                # Camera is active, process frames
                ret, frame = self.cap.read()
                if not ret:
                    print("Failed to read frame from camera")
                    time.sleep(0.1)
                    continue
                
                # Get effect chain
                chain = self.effect_controller.get_chain()
                
                # Get mask if needed
                needs_mask = any(
                    effect.__class__.__name__ in ['BackgroundBlur', 'BackgroundReplace'] 
                    for effect, _ in chain.effects
                )
                mask = None
                if needs_mask:
                    if self.segmenter is None:
                        from .segmentation import PersonSegmenter
                        self.segmenter = PersonSegmenter()
                    mask = self.segmenter.get_mask(frame)
                
                # Apply effect chain
                processed = chain.apply(frame, mask, **kwargs)
                
                # Send to virtual camera
                if self.virtual_cam is not None:
                    frame_rgb = cv2.cvtColor(processed, cv2.COLOR_BGR2RGB)
                    self.virtual_cam.send(frame_rgb.tobytes())
                    self.virtual_cam.sleep_until_next_frame()
                
                # Show preview
                if preview:
                    cv2.imshow('camfx preview', processed)
                    key = cv2.waitKey(1) & 0xFF
                    if key == ord('q'):
                        break
                
                frame_count += 1
                if frame_count == 1:
                    print(f"Processing frames... (Press 'q' in preview window to quit)")
        
        finally:
            self._stop_camera()
            if self.source_monitor:
                self.source_monitor.stop_monitoring()
            if self.virtual_cam is not None:
                self.virtual_cam.cleanup()
            try:
                cv2.destroyAllWindows()
            except Exception:
                pass
```

---

### Phase 2: D-Bus Control Interface

#### 2.1 D-Bus Service Implementation

**Why D-Bus:**
- Better integration with desktop environments
- Enables future GUI development
- More robust than file-based approach
- Standard Linux IPC mechanism
- Supports signals for state changes

**Implementation:**
- Expose D-Bus service on session bus
- Service name: `org.camfx.Control1`
- Object path: `/org/camfx/Control1`
- Interface: `org.camfx.Control1`

**Dependencies:**
- `dbus-python` or `python-dbus` package
- Or use `pydbus` (modern, async-friendly)

**New file: `camfx/dbus_control.py`**
```python
import dbus
import dbus.service
import dbus.mainloop.glib
from typing import Dict, Any, List, Optional
from gi.repository import GLib
import threading

# D-Bus service details
SERVICE_NAME = 'org.camfx.Control1'
OBJECT_PATH = '/org/camfx/Control1'
INTERFACE_NAME = 'org.camfx.Control1'

class CamfxControlService(dbus.service.Object):
    """D-Bus service for controlling camfx effects at runtime."""
    
    def __init__(self, effect_controller):
        """Initialize D-Bus service.
        
        Args:
            effect_controller: EffectController instance to control
        """
        # Set up D-Bus main loop
        dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
        
        # Get session bus
        bus = dbus.SessionBus()
        bus_name = dbus.service.BusName(SERVICE_NAME, bus=bus)
        
        # Initialize service object
        dbus.service.Object.__init__(self, bus_name, OBJECT_PATH)
        
        self.effect_controller = effect_controller
        self.main_loop: Optional[GLib.MainLoop] = None
        self.loop_thread: Optional[threading.Thread] = None
    
    @dbus.service.method(INTERFACE_NAME, in_signature='sa{sv}', out_signature='b')
    def SetEffect(self, effect_type: str, config: Dict[str, Any]) -> bool:
        """Replace all effects with a single effect.
        
        Args:
            effect_type: Type of effect ('blur', 'replace', 'brightness', etc.)
            config: Effect configuration dictionary
        
        Returns:
            True if successful, False otherwise
        """
        try:
            self.effect_controller.set_effect(effect_type, config)
            self.EffectChanged('set', effect_type, config)
            return True
        except Exception as e:
            print(f"Error setting effect: {e}")
            return False
    
    @dbus.service.method(INTERFACE_NAME, in_signature='sa{sv}', out_signature='b')
    def AddEffect(self, effect_type: str, config: Dict[str, Any]) -> bool:
        """Add an effect to the chain.
        
        Args:
            effect_type: Type of effect to add
            config: Effect configuration dictionary
        
        Returns:
            True if successful, False otherwise
        """
        try:
            self.effect_controller.add_effect(effect_type, config)
            self.EffectChanged('add', effect_type, config)
            return True
        except Exception as e:
            print(f"Error adding effect: {e}")
            return False
    
    @dbus.service.method(INTERFACE_NAME, in_signature='i', out_signature='b')
    def RemoveEffect(self, index: int) -> bool:
        """Remove an effect from the chain by index.
        
        Args:
            index: Index of effect to remove (0-based)
        
        Returns:
            True if successful, False otherwise
        """
        try:
            self.effect_controller.remove_effect(index)
            self.EffectChanged('remove', index, {})
            return True
        except Exception as e:
            print(f"Error removing effect: {e}")
            return False
    
    @dbus.service.method(INTERFACE_NAME, out_signature='b')
    def ClearChain(self) -> bool:
        """Clear all effects from the chain.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            self.effect_controller.clear_chain()
            self.EffectChanged('clear', '', {})
            return True
        except Exception as e:
            print(f"Error clearing chain: {e}")
            return False
    
    @dbus.service.method(INTERFACE_NAME, out_signature='a(ssa{sv})')
    def GetCurrentEffects(self) -> List[tuple]:
        """Get current effect chain.
        
        Returns:
            List of tuples: (effect_type, config_dict) for each effect in chain
        """
        try:
            chain = self.effect_controller.get_chain()
            return [(effect_type, config) for effect_type, config in chain.effects]
        except Exception as e:
            print(f"Error getting effects: {e}")
            return []
    
    @dbus.service.method(INTERFACE_NAME, in_signature='sa{sv}', out_signature='b')
    def UpdateEffectParameter(self, effect_type: str, parameter: str, value: Any) -> bool:
        """Update a parameter of an effect in the chain.
        
        Args:
            effect_type: Type of effect to update
            parameter: Parameter name (e.g., 'strength', 'brightness')
            value: New parameter value
        
        Returns:
            True if successful, False otherwise
        """
        try:
            self.effect_controller.update_effect_parameter(effect_type, parameter, value)
            self.EffectChanged('update', effect_type, {parameter: value})
            return True
        except Exception as e:
            print(f"Error updating parameter: {e}")
            return False
    
    @dbus.service.signal(INTERFACE_NAME, signature='ssa{sv}')
    def EffectChanged(self, action: str, effect_type: str, config: Dict[str, Any]):
        """Signal emitted when effect chain changes.
        
        Args:
            action: Action taken ('set', 'add', 'remove', 'clear', 'update')
            effect_type: Type of effect affected
            config: Configuration dictionary
        """
        pass
    
    @dbus.service.signal(INTERFACE_NAME, signature='b')
    def CameraStateChanged(self, is_active: bool):
        """Signal emitted when camera state changes.
        
        Args:
            is_active: True if camera is now active, False if inactive
        """
        pass
    
    def start(self):
        """Start the D-Bus service main loop."""
        self.main_loop = GLib.MainLoop.new(None, False)
        self.loop_thread = threading.Thread(target=self._run_loop, daemon=True)
        self.loop_thread.start()
        print(f"D-Bus service started: {SERVICE_NAME} on {OBJECT_PATH}")
    
    def _run_loop(self):
        """Run GLib main loop in separate thread."""
        if self.main_loop:
            self.main_loop.run()
    
    def stop(self):
        """Stop the D-Bus service."""
        if self.main_loop:
            self.main_loop.quit()
        if self.loop_thread:
            self.loop_thread.join(timeout=2.0)
```

**D-Bus Interface Definition (for documentation):**
```xml
<!DOCTYPE node PUBLIC "-//freedesktop//DTD D-Bus Object Introspection 1.0//EN"
"http://www.freedesktop.org/standards/dbus/1.0/introspect.dtd">
<node>
  <interface name="org.camfx.Control1">
    <method name="SetEffect">
      <arg name="effect_type" type="s" direction="in"/>
      <arg name="config" type="a{sv}" direction="in"/>
      <arg name="success" type="b" direction="out"/>
    </method>
    <method name="AddEffect">
      <arg name="effect_type" type="s" direction="in"/>
      <arg name="config" type="a{sv}" direction="in"/>
      <arg name="success" type="b" direction="out"/>
    </method>
    <method name="RemoveEffect">
      <arg name="index" type="i" direction="in"/>
      <arg name="success" type="b" direction="out"/>
    </method>
    <method name="ClearChain">
      <arg name="success" type="b" direction="out"/>
    </method>
    <method name="GetCurrentEffects">
      <arg name="effects" type="a(ssa{sv})" direction="out"/>
    </method>
    <method name="UpdateEffectParameter">
      <arg name="effect_type" type="s" direction="in"/>
      <arg name="parameter" type="s" direction="in"/>
      <arg name="value" type="v" direction="in"/>
      <arg name="success" type="b" direction="out"/>
    </method>
    <signal name="EffectChanged">
      <arg name="action" type="s"/>
      <arg name="effect_type" type="s"/>
      <arg name="config" type="a{sv}"/>
    </signal>
    <signal name="CameraStateChanged">
      <arg name="is_active" type="b"/>
    </signal>
  </interface>
</node>
```

**Usage Examples:**

**From Python:**
```python
import dbus

bus = dbus.SessionBus()
service = bus.get_object('org.camfx.Control1', '/org/camfx/Control1')
control = dbus.Interface(service, 'org.camfx.Control1')

# Set effect
control.SetEffect('blur', {'strength': 35})

# Add effect to chain
control.AddEffect('brightness', {'brightness': 10})

# Get current effects
effects = control.GetCurrentEffects()
```

**From command line (using `dbus-send`):**
```bash
# Set blur effect
dbus-send --session --type=method_call \
  --dest=org.camfx.Control1 \
  /org/camfx/Control1 \
  org.camfx.Control1.SetEffect \
  string:'blur' \
  dict:string:int32:'strength',int32:35

# Get current effects
dbus-send --session --type=method_call \
  --dest=org.camfx.Control1 \
  /org/camfx/Control1 \
  org.camfx.Control1.GetCurrentEffects
```

**From shell script:**
```bash
#!/bin/bash
# Change effect via D-Bus
dbus-send --session --type=method_call \
  --dest=org.camfx.Control1 \
  /org/camfx/Control1 \
  org.camfx.Control1.SetEffect \
  string:'replace' \
  dict:string:string:'image',string:'/path/to/bg.jpg'
```

---

### Phase 3: CLI Updates

#### 3.1 Add Control Commands (D-Bus Interface)

**Modify `camfx/cli.py`:**

```python
import dbus

@cli.command('set-effect')
@click.option('--effect', required=True, type=click.Choice(['blur', 'replace', 'brightness', ...]))
@click.option('--strength', type=int, help='For blur effect')
@click.option('--image', type=str, help='For replace effect')
def set_effect(effect, **kwargs):
    """Change effect at runtime via D-Bus."""
    try:
        bus = dbus.SessionBus()
        service = bus.get_object('org.camfx.Control1', '/org/camfx/Control1')
        control = dbus.Interface(service, 'org.camfx.Control1')
        
        # Build config dict
        config = {}
        if 'strength' in kwargs and kwargs['strength'] is not None:
            config['strength'] = kwargs['strength']
        if 'image' in kwargs and kwargs['image'] is not None:
            config['image'] = kwargs['image']
        # Add other effect-specific parameters...
        
        success = control.SetEffect(effect, config)
        if success:
            print(f"Effect changed to: {effect}")
        else:
            print(f"Failed to change effect to: {effect}")
    except dbus.exceptions.DBusException as e:
        print(f"Error connecting to camfx D-Bus service: {e}")
        print("Make sure camfx is running with D-Bus support enabled")
    except Exception as e:
        print(f"Error: {e}")

@cli.command('add-effect')
@click.option('--effect', required=True, type=click.Choice([...]))
def add_effect(effect, **kwargs):
    """Add effect to chain at runtime."""
    # Similar implementation

@cli.command('chain')
@click.option('--effects', required=True, help='Comma-separated list: blur,replace,brightness')
def chain(effects, **kwargs):
    """Start with a chain of effects."""
    effect_list = [e.strip() for e in effects.split(',')]
    # Initialize with chain
```

#### 3.2 Update Existing Commands

**Modify existing commands to support chaining:**

```python
@cli.command('blur')
@click.option('--chain', is_flag=True, help='Allow adding more effects')
@click.option('--add', is_flag=True, help='Add to existing chain instead of replacing')
def blur(..., chain, add):
    """Apply background blur effect."""
    # If --chain or --add, use add_effect instead of set_effect
```

---

### Phase 4: Effect Chaining Implementation

#### 4.1 Update Effect Interface

**Modify `camfx/effects.py`:**

- Ensure all effects can work with intermediate results (not just raw frames)
- Some effects may need masks, others may not
- Chain should handle mask propagation

**Effect Chain Processing:**
```python
def apply_chain(self, frame, initial_mask, **kwargs):
    """Apply all effects in sequence."""
    result = frame
    current_mask = initial_mask
    
    for effect, config in self.effects:
        # Determine if this effect needs a mask
        needs_mask = effect.__class__.__name__ in ['BackgroundBlur', 'BackgroundReplace']
        
        # Merge config with kwargs
        effect_kwargs = {**config, **kwargs}
        
        # Apply effect
        if needs_mask and current_mask is not None:
            result = effect.apply(result, current_mask, **effect_kwargs)
        else:
            result = effect.apply(result, None, **effect_kwargs)
        
        # Some effects might modify the mask (future enhancement)
        # For now, mask stays the same
    
    return result
```

#### 4.2 Example Effect Chains

**Common chains:**
- `blur` + `brightness` (blur background, adjust face brightness)
- `replace` + `beautify` (replace background, beautify face)
- `autoframe` + `blur` (auto-frame then blur background)
- `beautify` + `brightness` (beautify then adjust brightness)

---

## Implementation Steps

### Step 1: Core Refactoring (Week 1)
1. ✅ Create `EffectChain` and `EffectController` classes
2. ✅ Refactor `VideoEnhancer` to use effect controller
3. ✅ Add lazy camera initialization
4. ✅ Test basic functionality

### Step 2: PipeWire Monitoring (Week 1-2)
1. ✅ Implement `PipeWireSourceMonitor` using libpipewire
2. ✅ Integrate with `VideoEnhancer`
3. ✅ Test camera start/stop based on usage
4. ✅ Test multiple simultaneous consumers
5. ✅ Handle edge cases (monitoring failures, etc.)

### Step 3: D-Bus Control Interface (Week 2)
1. ✅ Implement D-Bus service
2. ✅ Add CLI commands for runtime control via D-Bus
3. ✅ Test effect switching during runtime
4. ✅ Document D-Bus interface
5. ✅ Test with external clients (future GUI)

### Step 4: Effect Chaining (Week 2-3)
1. ✅ Update effect chain processing
2. ✅ Test various effect combinations
3. ✅ Add CLI support for chains
4. ✅ Document common chains

### Step 5: Testing & Polish (Week 3)
1. ✅ Test all features together
2. ✅ Performance testing
3. ✅ Documentation updates
4. ✅ Backward compatibility verification

---

## Testing Strategy

### Unit Tests
- `EffectChain.apply()` with various effect combinations
- `PipeWireSourceMonitor` usage detection
- `EffectController` thread safety

### Integration Tests
- Start camfx, connect app, verify camera starts
- Disconnect app, verify camera stops
- Change effect via control file, verify effect changes
- Chain multiple effects, verify output

### Manual Testing
- Use in real meeting scenario
- Test with different applications (Zoom, Teams, browser)
- Test effect switching during active call
- Test resource usage (CPU, memory) when camera inactive

---

## Backward Compatibility

### Existing CLI Commands
- All existing commands (`blur`, `replace`, etc.) should continue to work
- Default behavior: lazy camera disabled (immediate start) for compatibility
- Add `--lazy-camera` flag to enable on-demand camera

### Configuration
- Existing config options remain valid
- New options are optional with sensible defaults

---

## Performance Considerations

### Camera Start/Stop Overhead
- Camera initialization takes ~100-500ms
- Consider keeping camera "warm" for a few seconds after last use
- Add configurable timeout before stopping

### Effect Chain Performance
- Each effect adds processing time
- Consider caching masks when multiple effects need them
- Profile and optimize hot paths

### Monitoring Overhead
- libpipewire event-based monitoring is efficient (no polling)
- Minimal overhead when no state changes occur
- Real-time updates when clients connect/disconnect

---

## Future Enhancements

1. **GUI Control Panel**: Create a simple GUI using D-Bus interface
2. **Effect Presets**: Save and load effect chain presets
3. **Hotkeys**: Support keyboard shortcuts for common effect changes
4. **Effect Parameters**: Allow runtime parameter adjustment (e.g., blur strength)
5. **Performance Monitoring**: Add FPS counter and resource usage display
6. **Multiple Source Instances**: Support running multiple camfx instances with different names

---

## Risks & Mitigations

### Risk 1: PipeWire Monitoring Unreliable
- **Mitigation**: Fall back to always-on camera if libpipewire connection fails
- **Mitigation**: Add manual override flag `--force-camera-on`
- **Mitigation**: Graceful degradation if PipeWire bindings unavailable

### Risk 4: Multiple Consumers Not Detected Properly
- **Mitigation**: Track all active client connections, not just count
- **Mitigation**: Test with multiple applications simultaneously
- **Mitigation**: Add logging for connection/disconnection events

### Risk 2: Effect Switching Causes Glitches
- **Mitigation**: Smooth transitions between effects
- **Mitigation**: Queue effect changes, apply between frames

### Risk 3: Complex Effect Chains Too Slow
- **Mitigation**: Profile and optimize
- **Mitigation**: Warn user if chain is too slow
- **Mitigation**: Allow disabling effects in chain

---

## Documentation Updates

1. **README.md**: Add sections on live effect switching and effect chaining
2. **CLI Reference**: Document new commands and flags
3. **Control File Format**: Document JSON schema
4. **Examples**: Add examples of effect chains and runtime control

---

## Success Criteria

1. ✅ Can change effects during active meeting without restart
2. ✅ Camera only active when virtual source is in use
3. ✅ Can chain multiple effects together
4. ✅ Backward compatible with existing CLI usage
5. ✅ Performance acceptable (< 5% CPU when camera inactive)
6. ✅ No regressions in existing functionality
7. ✅ Multiple applications can use virtual camera simultaneously
8. ✅ D-Bus interface works for runtime control
9. ✅ libpipewire monitoring provides real-time updates

