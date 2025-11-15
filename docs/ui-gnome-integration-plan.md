# UI and GNOME Integration Plan for camfx

## Quick Reference: Prioritized Deliverables

**🎯 Priority 1: Standalone GTK Application** (2-3 weeks)
- Full-featured desktop application
- Works on all desktop environments
- Live preview and effect management
- **Start here** - Fastest path to user value

**🎯 Priority 2: GNOME Shell Extension** (2-3 weeks)
- Deep GNOME desktop integration
- Quick settings panel in top bar
- Always accessible
- **Follows Priority 1** - Builds on app experience

---

## Executive Summary

This document outlines a comprehensive plan for creating user-friendly interfaces and GNOME desktop integrations for camfx, enabling users to easily preview and update effects without using the command line.

**Primary Focus:**
1. **Standalone GTK Application** - Full-featured desktop application for effect management
2. **GNOME Shell Extension** - Deep desktop integration with quick access from top bar

**Goals:**
- Provide intuitive GUI for effect management and preview
- Integrate seamlessly with GNOME desktop environment
- Enable real-time effect adjustment with live preview
- Support both standalone application and system integration

**Approach:**
- Leverage existing D-Bus service (`org.camfx.Control1`) for backend communication
- Use GTK4/PyGObject for native GNOME look and feel
- Prioritize standalone GTK app first (faster development, broader compatibility)
- Follow with GNOME Shell extension (deep integration, always accessible)
- Implement live preview using PipeWire input capabilities

---

## Current State Analysis

### Existing Infrastructure

**D-Bus Service:**
- Service: `org.camfx.Control1`
- Object Path: `/org/camfx/Control1`
- Methods:
  - `SetEffect(effect_type, config)` - Replace all effects
  - `AddEffect(effect_type, config)` - Add/update effect in chain
  - `RemoveEffect(index)` - Remove by index
  - `RemoveEffectByType(effect_type)` - Remove by type
  - `ClearChain()` - Clear all effects
  - `GetCurrentEffects()` - Get current effect chain
  - `UpdateEffectParameter(effect_type, parameter, value)` - Update single parameter
- Signals:
  - `EffectChanged(action, effect_type, config)` - Emitted on effect changes
  - `CameraStateChanged(is_active)` - Emitted on camera state changes

**Available Effects:**
- `blur` - Background blur (parameter: `strength`)
- `replace` - Background replacement (parameter: `background` image)
- `brightness` - Brightness/contrast adjustment (parameters: `brightness`, `contrast`, `face_only`)
- `beautify` - Face beautification (parameter: `smoothness`)
- `autoframe` - Auto-framing (parameters: `padding`, `min_zoom`, `max_zoom`)
- `gaze-correct` - Eye gaze correction (parameter: `strength`)

**CLI Capabilities:**
- Start virtual camera: `camfx start --effect <type> --dbus`
- Preview output: `camfx preview`
- Runtime control via D-Bus commands

**Dependencies:**
- PyGObject already in requirements (for GTK/GStreamer)
- dbus-python already in requirements
- OpenCV for preview window (already used)

---

## Integration Options Overview

> **Note:** The following options are evaluated, but **Standalone GTK Application** and **GNOME Shell Extension** are the prioritized implementations.

### Option 1: Standalone GTK Application ⭐ PRIORITY 1

**Pros:**
- Fastest to implement
- Full control over UI/UX
- Can be used on any desktop environment (not just GNOME)
- Easy to test and iterate
- Can be launched independently

**Cons:**
- Requires manual launch
- Not as deeply integrated as shell extension

**Implementation:**
- GTK4 application using PyGObject
- Real-time preview window
- Effect chain management UI
- Parameter adjustment controls
- System tray integration (optional)

### Option 2: GNOME Shell Extension ⭐ PRIORITY 2

**Pros:**
- Deep desktop integration
- Always accessible from top bar
- Native GNOME look and feel
- Can show quick settings panel
- Auto-starts with GNOME

**Cons:**
- GNOME-only (not usable on other DEs)
- More complex to develop and maintain
- Requires extension review/approval for GNOME Extensions website
- JavaScript-based (different from Python backend)

**Implementation:**
- JavaScript extension using GJS
- Communicates with camfx via D-Bus
- Quick settings panel in top bar
- Popup window for detailed controls

### Option 3: GNOME Control Center Panel (Not Prioritized)

**Pros:**
- Official system settings integration
- Discoverable by users
- Consistent with system UI
- High visibility

**Cons:**
- Requires upstream GNOME approval (very difficult)
- Or requires patching/distributing modified GNOME Settings
- Not practical for third-party application

**Recommendation:** Skip this option unless planning to upstream to GNOME.

### Option 4: System Tray Application (Future Enhancement)

**Pros:**
- Lightweight
- Always accessible
- Minimal resource usage
- Can show quick preview

**Cons:**
- Limited UI space
- May not be available on Wayland (depends on implementation)
- Less discoverable

**Implementation:**
- Standalone app with system tray icon
- Right-click menu for quick actions
- Popup window for full controls

---

## Implementation Plan (Prioritized)

### 🎯 Priority 1: Standalone GTK Application

**Status:** Primary focus - Start here  
**Timeline:** 2-3 weeks  
**Target:** Full-featured desktop application for all users

**Why First:**
- Fastest path to user value
- Works on all desktop environments (not just GNOME)
- Easier to develop and test
- Provides foundation for shell extension
- Can be used immediately by all users

**Features:**
1. **Main Window**
   - Live preview pane (showing processed output)
   - Effect chain list (ordered list of active effects)
   - Effect selection panel (add new effects)
   - Parameter adjustment controls (sliders, inputs)
   - Start/Stop virtual camera button
   - Camera status indicator

2. **Preview Functionality**
   - Real-time preview using PipeWire input (connect to camfx virtual camera)
   - Fallback to direct camera preview if virtual camera not available
   - FPS counter (optional)
   - Fullscreen preview option

3. **Effect Management**
   - Add effect button (opens effect selection dialog)
   - Remove effect button (per effect in chain)
   - Reorder effects (drag-and-drop or up/down buttons)
   - Update effect parameters (live updates via D-Bus)
   - Effect enable/disable toggle (per effect)

4. **Effect Parameter Controls**
   - **Blur**: Strength slider (3-51, odd numbers only)
   - **Replace**: Background image picker button
   - **Brightness**: Brightness slider (-100 to 100), Contrast slider (0.5 to 2.0), Face-only checkbox
   - **Beautify**: Smoothness slider (1-15)
   - **Autoframe**: Padding slider (0.0-1.0), Min zoom slider, Max zoom slider
   - **Gaze-correct**: Strength slider (0.0-1.0)

5. **System Integration**
   - Check if camfx daemon is running
   - Auto-start camfx if not running (optional)
   - Show connection status
   - Error handling and user-friendly messages

**UI Layout:**
```
┌─────────────────────────────────────────────────────────┐
│  camfx Control Panel                                    │
├──────────────────┬──────────────────────────────────────┤
│                  │  Effect Chain                       │
│                  │  ┌────────────────────────────────┐  │
│   Live Preview   │  │ 1. Blur (strength: 25)    [×] │  │
│                  │  │ 2. Brightness (+10)      [×] │  │
│   [640x480]      │  └────────────────────────────────┘  │
│                  │                                      │
│   [Fullscreen]   │  Add Effect: [▼] [Add]              │
│                  │                                      │
│   Status: Active │  Effect Parameters:                  │
│   Camera: /dev/  │  ┌────────────────────────────────┐  │
│   video0         │  │ Blur Strength: [====●====] 25 │  │
│                  │  └────────────────────────────────┘  │
│                  │                                      │
│                  │  [Start Virtual Camera]             │
│                  │  [Stop]                              │
└──────────────────┴──────────────────────────────────────┘
```

**Technical Implementation:**

**File Structure:**
```
camfx/
├── gui/
│   ├── __init__.py
│   ├── main_window.py          # Main GTK window
│   ├── preview_widget.py        # Preview pane widget
│   ├── effect_chain_widget.py  # Effect chain list widget
│   ├── effect_controls.py      # Parameter controls for each effect
│   ├── dbus_client.py          # D-Bus client wrapper
│   └── utils.py                # Helper functions
```

**Dependencies:**
- `PyGObject>=3.42.0` (already in requirements)
- `gi.repository.Gtk` (GTK4)
- `gi.repository.GdkPixbuf` (for image handling)
- `gi.repository.GLib` (for async operations)

**Key Components:**

1. **D-Bus Client Wrapper** (`gui/dbus_client.py`):
   ```python
   class CamfxDBusClient:
       """Wrapper for D-Bus communication with camfx service."""
       
       def __init__(self):
           self.bus = dbus.SessionBus()
           self.service = None
           self.control = None
           self._connect()
       
       def _connect(self):
           """Connect to camfx D-Bus service."""
           try:
               self.service = self.bus.get_object(
                   'org.camfx.Control1',
                   '/org/camfx/Control1'
               )
               self.control = dbus.Interface(
                   self.service,
                   'org.camfx.Control1'
               )
           except dbus.exceptions.DBusException:
               raise ConnectionError("camfx service not running")
       
       def get_current_effects(self) -> List[Dict]:
           """Get current effect chain."""
           return self.control.GetCurrentEffects()
       
       def add_effect(self, effect_type: str, config: Dict) -> bool:
           """Add effect to chain."""
           return self.control.AddEffect(effect_type, config)
       
       # ... other methods
   ```

2. **Preview Widget** (`gui/preview_widget.py`):
   ```python
   class PreviewWidget(Gtk.Widget):
       """Widget showing live preview from camfx virtual camera."""
       
       def __init__(self):
           super().__init__()
           self.pipewire_input = None
           self.preview_image = Gtk.Picture()
           # Use GStreamer to capture from PipeWire source
           # Update preview_image periodically
   ```

3. **Effect Chain Widget** (`gui/effect_chain_widget.py`):
   ```python
   class EffectChainWidget(Gtk.Box):
       """Widget showing and managing effect chain."""
       
       def __init__(self, dbus_client):
           super().__init__(orientation=Gtk.Orientation.VERTICAL)
           self.dbus_client = dbus_client
           self.effect_rows = []
           self._refresh_chain()
   ```

**Entry Point:**
- Add CLI command: `camfx gui` or `camfx-control-panel`
- Or standalone script: `camfx-gui`

**Testing:**
- Manual testing with running camfx instance
- Test all effect types and parameter adjustments
- Test error handling (service not running, invalid parameters)
- Test on different screen sizes

---

### 🎯 Priority 2: GNOME Shell Extension

**Status:** Secondary focus - Start after GTK app MVP  
**Timeline:** 2-3 weeks  
**Target:** Deep GNOME integration for power users

**Why Second:**
- Builds on GTK app experience
- Provides deep desktop integration
- Always accessible from top bar
- Complements standalone app
- GNOME-specific enhancement

**Features:**
1. **Quick Settings Panel**
   - Toggle virtual camera on/off
   - Quick effect selector (most common effects)
   - Effect strength slider (for current effect)
   - Status indicator

2. **Popup Window**
   - Full effect management (similar to standalone app)
   - Compact preview
   - Effect chain management

3. **Indicator in Top Bar**
   - Icon showing camfx status
   - Click to open quick settings
   - Visual indicator when effects are active

**Implementation:**

**File Structure:**
```
camfx-gnome-extension/
├── metadata.json
├── extension.js
├── prefs.js
├── stylesheet.css
└── schemas/
    └── org.camfx.gnome-extension.gschema.xml
```

**Key Components:**

1. **Extension Entry Point** (`extension.js`):
   ```javascript
   const Main = imports.ui.main;
   const QuickSettings = imports.ui.quickSettings;
   const PanelMenu = imports.ui.panelMenu;
   
   class CamfxIndicator extends PanelMenu.Button {
       _init() {
           super._init(0.0, 'camfx');
           // Create indicator
           // Connect to D-Bus
       }
   }
   ```

2. **D-Bus Integration** (GJS):
   ```javascript
   const { Gio } = imports.gi;
   
   const DBusProxy = Gio.DBusProxy.makeProxyWrapper(`
       <node>
           <interface name="org.camfx.Control1">
               <method name="GetCurrentEffects">
                   <arg type="a(ssa{sv})" direction="out"/>
               </method>
               <method name="AddEffect">
                   <arg type="s" direction="in"/>
                   <arg type="a{sv}" direction="in"/>
                   <arg type="b" direction="out"/>
               </method>
               <!-- ... other methods ... -->
           </interface>
       </node>
   `);
   ```

**Distribution:**
- Package as GNOME Shell extension
- Submit to extensions.gnome.org (optional)
- Include in camfx package installation

---

### Phase 2: Enhanced Standalone Application Features

**Timeline:** 1-2 weeks after Priority 1 & 2 complete

**Additional Features:**
1. **Presets System**
   - Save effect chain as preset
   - Load presets
   - Quick preset buttons (e.g., "Meeting", "Streaming", "Casual")
   - Preset management dialog

2. **Background Image Library**
   - Browse and select background images
   - Recent backgrounds list
   - Background preview thumbnails
   - Support for multiple image formats

3. **Advanced Preview**
   - Side-by-side comparison (original vs processed)
   - Before/after toggle
   - Zoom controls
   - Screenshot capture

4. **Settings Dialog**
   - Camera selection
   - Resolution/FPS settings
   - Lazy camera mode toggle
   - Auto-start on login
   - Theme preferences

5. **Keyboard Shortcuts**
   - Quick effect switching
   - Parameter adjustment (arrow keys)
   - Fullscreen toggle

6. **System Tray Integration**
   - Minimize to tray
   - Tray icon with status indicator
   - Quick menu (start/stop, current effect, open window)

---

### Future Considerations (Lower Priority)

**Status:** Future enhancements - Not prioritized

**Features:**
1. **GNOME Settings Integration** (if upstreamed)
   - Panel in GNOME Control Center
   - System-wide settings
   - Per-user preferences

2. **Desktop File Integration**
   - Right-click on camera apps → "Use camfx"
   - Auto-launch camfx when camera app starts

3. **Notification Integration**
   - Notify when camera starts/stops
   - Notify on effect changes
   - Quick action buttons in notifications

4. **Screen Recording Integration**
   - OBS Studio plugin
   - Simple Screen Recorder integration
   - GNOME Screen Recorder integration

---

## Technical Details

### Preview Implementation

**Option A: PipeWire Input (Recommended)**
- Connect to camfx virtual camera via PipeWire
- Use GStreamer pipeline: `pipewiresrc ! videoconvert ! appsink`
- Update GTK widget with frames
- Pros: Shows actual virtual camera output
- Cons: Requires camfx to be running

**Option B: Direct Camera Preview**
- Connect directly to camera
- Apply effects locally for preview
- Pros: Works even if camfx not running
- Cons: May differ from actual output, duplicates processing

**Option C: Shared Memory**
- camfx writes frames to shared memory
- GUI reads from shared memory
- Pros: Efficient, always in sync
- Cons: More complex, requires IPC

**Recommendation:** Use Option A (PipeWire input) with fallback to Option B.

### D-Bus Communication

**Connection Management:**
- Check service availability on startup
- Reconnect on service restart
- Show connection status in UI
- Handle service errors gracefully

**Async Operations:**
- Use GLib main loop for async D-Bus calls
- Show loading indicators during operations
- Handle timeouts appropriately

**Signal Handling:**
- Listen to `EffectChanged` signal for real-time updates
- Listen to `CameraStateChanged` for status updates
- Update UI automatically on signal reception

### Error Handling

**Common Errors:**
- camfx service not running → Show start button
- Invalid parameters → Show validation errors
- Camera in use → Show helpful message
- D-Bus connection lost → Attempt reconnection

**User Feedback:**
- Toast notifications for errors
- Status bar messages
- Error dialogs for critical issues

---

## UI/UX Design Principles

1. **Simplicity First**
   - Clear, uncluttered interface
   - Intuitive controls
   - Minimal learning curve

2. **Real-time Feedback**
   - Live preview updates immediately
   - Parameter changes apply instantly
   - Visual feedback for all actions

3. **Discoverability**
   - Tooltips for all controls
   - Help text for parameters
   - Example presets

4. **Accessibility**
   - Keyboard navigation
   - Screen reader support
   - High contrast mode support

5. **Performance**
   - Smooth preview (30+ FPS)
   - Responsive UI (no lag on parameter changes)
   - Efficient resource usage

---

## Dependencies and Requirements

### New Dependencies

**Python:**
- `PyGObject>=3.42.0` (already in requirements)
- No additional Python packages needed

**System:**
- GTK4 development libraries
- GStreamer development libraries (for preview)
- D-Bus (already required)

**Installation:**
```bash
# Fedora
sudo dnf install gtk4-devel gstreamer1-devel

# Ubuntu/Debian
sudo apt install libgtk-4-dev libgstreamer1.0-dev
```

### Build Requirements

- Meson build system (for GNOME Shell extension, optional)
- gettext for translations (future)

---

## Testing Strategy

### Unit Tests
- D-Bus client wrapper
- Effect parameter validation
- UI component logic

### Integration Tests
- D-Bus communication with running camfx
- Preview functionality
- Effect chain management

### Manual Testing
- UI responsiveness
- Visual appearance
- User workflow
- Error scenarios

### Test Scenarios
1. Start GUI with camfx running
2. Start GUI without camfx running
3. Add/remove effects
4. Adjust parameters
5. Reorder effects
6. Save/load presets
7. Preview functionality
8. Error handling

---

## Distribution and Packaging

### Standalone Application

**Entry Points:**
- `camfx gui` - Launch GUI
- `camfx-control-panel` - Alternative command
- Desktop file: `camfx-control-panel.desktop`

**Desktop File:**
```ini
[Desktop Entry]
Name=camfx Control Panel
Comment=Control camera effects and preview output
Exec=camfx gui
Icon=camfx
Terminal=false
Type=Application
Categories=AudioVideo;Video;
```

**Installation:**
- Include in package installation
- Add to system menu
- Optional: Add to autostart

### GNOME Shell Extension

**Packaging:**
- ZIP file with extension files
- Install to `~/.local/share/gnome-shell/extensions/camfx@camfx.org`
- Or system-wide: `/usr/share/gnome-shell/extensions/`

**Installation Script:**
```bash
# Install extension
./scripts/install-gnome-extension.sh
```

---

## Timeline and Milestones

### Priority 1: Standalone GTK Application (2-3 weeks)
- **Week 1:** Core UI implementation
  - Main window layout
  - D-Bus client wrapper
  - Basic preview functionality
- **Week 2:** Effect management
  - Effect chain widget
  - Parameter controls
  - Add/remove effects
- **Week 3:** Polish and testing
  - Error handling
  - UI refinements
  - Documentation
  - Initial release

### Priority 2: GNOME Shell Extension (2-3 weeks)
- **Week 1:** Extension structure and D-Bus integration
  - Extension scaffolding
  - D-Bus proxy setup
  - Basic indicator
- **Week 2:** UI implementation
  - Quick settings panel
  - Popup window
  - Effect controls
- **Week 3:** Testing and polish
  - Integration testing
  - UI refinements
  - Documentation
  - Extension packaging

### Enhanced Features (1-2 weeks, after priorities)
- Presets system
- Advanced preview features
- System tray integration
- Settings dialog

---

## Success Criteria

1. **Usability**
   - Users can control effects without CLI knowledge
   - Preview updates in real-time
   - Intuitive parameter adjustment

2. **Reliability**
   - Handles errors gracefully
   - Reconnects to service automatically
   - No crashes or freezes

3. **Performance**
   - Smooth preview (30+ FPS)
   - Responsive UI (<100ms response time)
   - Low resource usage

4. **Integration**
   - Works seamlessly with camfx daemon
   - Follows GNOME design guidelines
   - Accessible and keyboard-navigable

---

## Future Enhancements

1. **Web-based UI**
   - Local web server
   - Browser-based interface
   - Remote control capability

2. **Mobile App**
   - Control camfx from phone
   - Remote preview

3. **Voice Control**
   - "Enable blur" voice commands
   - Integration with voice assistants

4. **AI-powered Presets**
   - Auto-detect lighting conditions
   - Suggest optimal settings
   - Adaptive effect strength

---

## References

- [GTK4 Documentation](https://docs.gtk.org/gtk4/)
- [PyGObject Documentation](https://pygobject.readthedocs.io/)
- [GNOME Shell Extension Guide](https://gjs.guide/extensions/)
- [D-Bus Python Tutorial](https://dbus.freedesktop.org/doc/dbus-python/tutorial.html)
- [GStreamer Python Bindings](https://gstreamer.freedesktop.org/documentation/tutorials/python/index.html)

---

## Appendix: Example Code Snippets

### GTK4 Main Window Structure

```python
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, Gdk, GLib

class CamfxMainWindow(Gtk.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title="camfx Control Panel")
        
        # Main container
        self.main_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        self.set_child(self.main_box)
        
        # Preview pane (left)
        self.preview_widget = PreviewWidget()
        self.main_box.append(self.preview_widget)
        
        # Control pane (right)
        self.control_pane = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.main_box.append(self.control_pane)
        
        # Effect chain widget
        self.effect_chain = EffectChainWidget(self.dbus_client)
        self.control_pane.append(self.effect_chain)
        
        # Parameter controls
        self.param_controls = ParameterControlsWidget()
        self.control_pane.append(self.param_controls)
        
        # Action buttons
        self.action_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        self.start_button = Gtk.Button(label="Start Virtual Camera")
        self.start_button.connect("clicked", self.on_start_clicked)
        self.action_box.append(self.start_button)
        self.control_pane.append(self.action_box)
```

### D-Bus Client with Signal Handling

```python
class CamfxDBusClient:
    def __init__(self):
        self.bus = dbus.SessionBus()
        self.service = None
        self.control = None
        self.signal_handlers = []
        self._connect()
        self._setup_signals()
    
    def _setup_signals(self):
        """Set up signal handlers for effect changes."""
        self.service.connect_to_signal(
            'EffectChanged',
            self.on_effect_changed,
            dbus_interface='org.camfx.Control1'
        )
        self.service.connect_to_signal(
            'CameraStateChanged',
            self.on_camera_state_changed,
            dbus_interface='org.camfx.Control1'
        )
    
    def on_effect_changed(self, action, effect_type, config):
        """Callback for effect change signals."""
        # Update UI
        pass
    
    def on_camera_state_changed(self, is_active):
        """Callback for camera state change signals."""
        # Update status indicator
        pass
```

---

**Document Version:** 1.0  
**Last Updated:** 2025-01-15  
**Author:** camfx Development Team

