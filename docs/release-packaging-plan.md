# Release and Packaging Plan for camfx

## Overview

This document outlines the plan for creating distributable packages of camfx, starting with RPM packages for Fedora/RHEL (dnf) in Phase 1. The goal is to enable users to install camfx via `dnf install camfx` and have the virtual camera source available automatically with the ability to change effects live.

## Requirements

1. **Package Distribution**: Users should be able to install via `dnf install camfx` (Phase 1)
2. **Always-Available Camera Source**: Virtual camera should be available immediately after installation/startup
3. **On-Demand Camera Activation**: Physical camera only activates when virtual source is being consumed
4. **Live Effect Control**: Users can change effects at runtime without restarting the service
5. **System Integration**: Runs as a systemd user service, starts automatically on login

## Phase 1: RPM Packaging (dnf)

### 1.1 Package Structure

```
camfx/
├── camfx.spec              # RPM spec file
├── packaging/
│   ├── camfx.service      # Systemd user service file
│   ├── camfx.conf         # Default configuration file
│   └── camfx.sysconfig    # Optional: system-wide config overrides
└── ...
```

### 1.2 RPM Spec File (`camfx.spec`)

**Key Components:**
- Package metadata (name, version, release, license)
- Build dependencies (Python 3.10+, setuptools, wheel)
- Runtime dependencies (Python packages, system libraries)
- Installation of Python package
- Installation of systemd service file
- Installation of configuration files
- Post-install scripts to enable service
- Pre-uninstall scripts to stop/disable service

**Dependencies:**
- **Build Requires:**
  - python3-devel
  - python3-setuptools
  - python3-wheel
  
- **Requires:**
  - python3 >= 3.10
  - python3-gobject (PyGObject)
  - gstreamer1
  - gstreamer1-plugins-base
  - gstreamer1-plugins-good
  - pipewire
  - wireplumber
  - python3-mediapipe (or bundled)
  - python3-opencv (or bundled)
  - python3-click
  - python3-numpy
  - python3-dbus (dbus-python)

**Note:** Python packages like mediapipe and opencv-python may need to be packaged separately or bundled, depending on distribution policies.

### 1.3 Systemd User Service (`camfx.service`)

**Location:** `~/.config/systemd/user/camfx.service` (user service)

**Key Features:**
- Runs as user service (not system-wide)
- Starts automatically on user login
- Restarts on failure
- Reads configuration from `/etc/camfx/camfx.conf` or `~/.config/camfx/camfx.conf`
- Enables D-Bus by default
- Uses lazy camera mode by default
- Logs to journald

**Service File Template:**
```ini
[Unit]
Description=camfx Virtual Camera Service
After=pipewire.service wireplumber.service
Wants=pipewire.service wireplumber.service

[Service]
Type=simple
ExecStart=/usr/bin/camfx start --dbus --lazy-camera --config /etc/camfx/camfx.conf
Restart=on-failure
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=default.target
```

### 1.4 Configuration File (`camfx.conf`)

**Location:** `/etc/camfx/camfx.conf` (system-wide) or `~/.config/camfx/camfx.conf` (user override)

**Purpose:**
- Default camera device index
- Default resolution and FPS
- Default virtual camera name
- Default initial effect (if any)
- Effect-specific defaults

**Configuration Format:**
```ini
[camera]
device_index = 0
width = 1280
height = 720
fps = 30

[virtual]
name = camfx

[effects]
# Initial effect (leave empty for no effect)
initial_effect = 
# Effect-specific defaults
blur_strength = 25
brightness_level = 0
beautify_smoothness = 5
```

### 1.5 Code Changes Required

#### 1.5.1 CLI Enhancement for Config File Support

**File:** `camfx/cli.py`

**Changes:**
- Add `--config` option to `start` command
- Load configuration from file if provided
- Merge config file settings with CLI arguments (CLI takes precedence)
- Support both system-wide (`/etc/camfx/camfx.conf`) and user (`~/.config/camfx/camfx.conf`) config files

**Implementation:**
```python
import configparser
from pathlib import Path

def load_config(config_path: str | None = None) -> dict:
    """Load configuration from file."""
    config = configparser.ConfigParser()
    
    # Default paths
    user_config = Path.home() / '.config' / 'camfx' / 'camfx.conf'
    system_config = Path('/etc/camfx/camfx.conf')
    
    # Load system config first, then user config (user overrides system)
    if system_config.exists():
        config.read(system_config)
    if user_config.exists():
        config.read(user_config)
    
    # Also load explicit config path if provided
    if config_path and Path(config_path).exists():
        config.read(config_path)
    
    # Convert to dict format expected by VideoEnhancer
    result = {}
    if 'camera' in config:
        if 'device_index' in config['camera']:
            result['input_index'] = int(config['camera']['device_index'])
        if 'width' in config['camera']:
            result['width'] = int(config['camera']['width'])
        if 'height' in config['camera']:
            result['height'] = int(config['camera']['height'])
        if 'fps' in config['camera']:
            result['fps'] = int(config['camera']['fps'])
    
    if 'virtual' in config:
        if 'name' in config['virtual']:
            result['camera_name'] = config['virtual']['name']
    
    if 'effects' in config:
        if 'initial_effect' in config['effects']:
            effect = config['effects']['initial_effect'].strip()
            if effect:
                result['effect'] = effect
                # Load effect-specific config
                if effect == 'blur' and 'blur_strength' in config['effects']:
                    result['strength'] = int(config['effects']['blur_strength'])
                # ... other effects
    
    return result
```

#### 1.5.2 Ensure Virtual Camera Available Without Effects

**File:** `camfx/core.py`

**Current Behavior:** Virtual camera is created, but if no effects are set, it may not send frames properly.

**Changes Needed:**
- Ensure virtual camera sends frames even when no effects are active (pass-through mode)
- When effect chain is empty, send original camera frames (or black frames if lazy camera is inactive)
- This ensures the virtual camera is always "visible" to applications

**Implementation:**
```python
# In VideoEnhancer.run():
chain = self.effect_controller.get_chain()

# If no effects, pass through original frame
if not chain.effects:
    processed = frame  # No processing needed
else:
    # Apply effect chain as normal
    processed = chain.apply(frame, mask, **kwargs)
```

#### 1.5.3 Default Behavior: Always Enable D-Bus and Lazy Camera

**File:** `camfx/cli.py`

**Changes:**
- When running as systemd service (detected via environment variable or config), enable D-Bus and lazy camera by default
- Add `--no-dbus` and `--no-lazy-camera` flags to disable if needed

### 1.6 Build and Release Process

#### 1.6.1 Local Build

```bash
# Install build dependencies
sudo dnf install rpm-build python3-devel python3-setuptools python3-wheel

# Build RPM
rpmbuild -ba camfx.spec

# Output: ~/rpmbuild/RPMS/noarch/camfx-<version>-<release>.rpm
```

#### 1.6.2 COPR (Fedora Copr Build Service)

**Setup:**
1. Create COPR project: https://copr.fedorainfracloud.org/
2. Add `.copr/Makefile` and `.copr/camfx.spec`
3. Enable automatic rebuilds on git push

**Benefits:**
- Automatic builds for multiple Fedora versions
- Public repository for users
- Easy updates

#### 1.6.3 Release Workflow

1. **Version Bumping:**
   - Update version in `setup.py`
   - Update version in `camfx.spec`
   - Tag git release: `git tag v0.1.0`

2. **Build RPM:**
   ```bash
   rpmbuild -ba camfx.spec
   ```

3. **Test Installation:**
   ```bash
   sudo dnf install ~/rpmbuild/RPMS/noarch/camfx-*.rpm
   systemctl --user start camfx
   systemctl --user status camfx
   ```

4. **Upload to COPR:**
   - Push tag to repository
   - COPR automatically builds

5. **Documentation:**
   - Update README with installation instructions
   - Add troubleshooting section

### 1.7 Installation and Usage

#### 1.7.1 User Installation

```bash
# Add COPR repository (once available)
sudo dnf copr enable <username>/camfx

# Install
sudo dnf install camfx

# Service starts automatically on next login
# Or start manually:
systemctl --user start camfx
systemctl --user enable camfx  # Enable auto-start on login
```

#### 1.7.2 Post-Installation

After installation, the virtual camera should be:
- ✅ Available immediately (PipeWire source created)
- ✅ Camera activates when an application connects
- ✅ Effects can be changed live via CLI or D-Bus

#### 1.7.3 User Commands

```bash
# Check service status
systemctl --user status camfx

# View logs
journalctl --user -u camfx -f

# Change effects (service must be running)
camfx set-effect --effect blur --strength 25
camfx add-effect --effect brightness --brightness 10
camfx get-effects

# Stop service
systemctl --user stop camfx

# Disable auto-start
systemctl --user disable camfx
```

### 1.8 Testing Checklist

- [ ] RPM builds successfully
- [ ] All dependencies are correctly specified
- [ ] Service starts automatically on login
- [ ] Virtual camera is available immediately
- [ ] Camera activates when application connects (lazy mode)
- [ ] Effects can be changed via D-Bus
- [ ] Configuration file is read correctly
- [ ] Service restarts on failure
- [ ] Uninstall removes all files cleanly
- [ ] Works on Fedora 38, 39, 40, Rawhide
- [ ] Works on RHEL 9, 10 (if targeting)

## Phase 2: Additional Package Formats (Future)

### 2.1 Debian/Ubuntu (apt)

- Create `debian/` directory with:
  - `control` (package metadata)
  - `rules` (build rules)
  - `camfx.service` (systemd service)
  - `camfx.conf` (configuration)
- Build with `dpkg-buildpackage`
- Publish to PPA or Debian repository

### 2.2 openSUSE (zypper/packman)

- Create `.spec` file (similar to RPM but SUSE-specific)
- Build with `rpmbuild` or `osc` (Open Build Service)
- Submit to openSUSE Build Service

### 2.3 Arch Linux (pacman)

- Create `PKGBUILD` file
- Submit to AUR (Arch User Repository)

## Implementation Steps

### Step 1: Code Changes
1. Add config file support to CLI
2. Ensure virtual camera works without effects
3. Add service detection/environment handling

### Step 2: Packaging Files
1. Create `camfx.spec` file
2. Create systemd service file
3. Create default configuration file
4. Create build scripts

### Step 3: Testing
1. Build RPM locally
2. Test installation on clean system
3. Verify service behavior
4. Test effect switching

### Step 4: Release Infrastructure
1. Set up COPR project
2. Configure automatic builds
3. Test release process

### Step 5: Documentation
1. Update README with installation instructions
2. Add service management documentation
3. Add troubleshooting guide

## File Structure After Implementation

```
camfx/
├── camfx.spec                    # RPM spec file
├── packaging/
│   ├── camfx.service            # Systemd user service
│   ├── camfx.conf               # Default configuration
│   └── camfx.sysconfig          # Optional system config
├── .copr/                       # COPR build configuration
│   └── Makefile
├── camfx/
│   ├── cli.py                   # Enhanced with config support
│   ├── core.py                  # Enhanced for pass-through mode
│   └── ...
└── docs/
    └── release-packaging-plan.md # This file
```

## Notes

1. **Python Package Dependencies**: Some Python packages (mediapipe, opencv-python) may not be available in Fedora repositories. Options:
   - Bundle them in the RPM (not ideal)
   - Create separate RPMs for them
   - Use pip to install them in post-install script (not ideal for system packages)
   - Recommend: Create separate RPMs or use COPR to build them

2. **User vs System Service**: Using user service ensures:
   - Each user has their own camfx instance
   - No root privileges needed
   - Camera permissions handled per-user
   - Service starts with user session

3. **Configuration Priority**: CLI arguments > User config > System config

4. **Virtual Camera Availability**: The virtual camera source is created immediately when the service starts, even if no effects are active. This ensures applications can see it right away.

5. **Lazy Camera Mode**: By default, the physical camera only activates when an application connects to the virtual camera. This saves resources and respects privacy.

## Success Criteria

- ✅ Users can install with `dnf install camfx`
- ✅ Virtual camera is available immediately after installation
- ✅ Camera activates automatically when applications connect
- ✅ Effects can be changed live without restarting service
- ✅ Service starts automatically on user login
- ✅ Service restarts on failure
- ✅ Clean uninstall removes all components

