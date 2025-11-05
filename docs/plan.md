# Video Enhancement for Linux - New Project Plan

## Project: camfx

A lightweight, modular camera video enhancement middleware for Linux that provides quality of life features like background blur, background replacement, and lighting adjustment features. Output as a virtual camera for use with any video conferencing application. Integrates directly into GNOME and has deb & rpm installers for ease of use.

---

## Phase 1: MVP (Minimal Viable Product)

### 1.1 Project Setup

**Repository Structure:**
```
camfx/
├── README.md
├── setup.py
├── requirements.txt
├── camfx/
│   ├── __init__.py
│   ├── core.py           # Main processing logic
│   ├── segmentation.py   # MediaPipe wrapper
│   ├── effects.py        # Blur + background effects
│   └── cli.py            # Command-line interface
└── examples/
    └── blur_demo.py
```

**Technology Stack:**
- Python 3.9+
- MediaPipe (selfie segmentation model)
- OpenCV (image processing)
- pyvirtualcam (virtual camera output)
- v4l2loopback (Linux virtual camera device)

**Installation Requirements:**
- Linux kernel with v4l2loopback support
- Python 3.9+
- pip/conda for dependency management

### 1.2 MVP Features (Phase 1 Only)

**Feature 1: Background Blur**
- Input: Real webcam feed
- Process: MediaPipe person segmentation → apply Gaussian blur to background
- Output: Virtual camera device
- Configuration: Blur strength (adjustable)

**Feature 2: Basic Background Replacement**
- Input: Real webcam feed + static background image
- Process: MediaPipe person segmentation → composite foreground on background
- Output: Virtual camera device
- Configuration: Background image path

**Feature 3: CLI Interface**
```bash
# Run with background blur
camfx blur --strength 25

# Run with background replacement
camfx replace --image /path/to/background.jpg

# Stop
# Press 'q' to exit
```

**CLI Controls (MVP scope)**
- Input selection: `--input 0`
- Output device: `--vdevice /dev/video10`
- Resolution & FPS: `--width 1280 --height 720 --fps 30`
- Effect selection via subcommands: `blur`, `replace`
- Blur controls: `--strength 5..51` (odd kernel size)
- Replace controls: `--image /path/to/bg.jpg`
- Preview window: `--preview`
- Logging: `--verbose`

### 1.3 Core Implementation (Minimal Code)

**`segmentation.py` - ~50 lines**
```python
import mediapipe as mp
import numpy as np
import cv2

class PersonSegmenter:
    def __init__(self):
        self.segmenter = mp.solutions.selfie_segmentation.SelfieSegmentation(model_selection=1)
    
    def get_mask(self, frame):
        results = self.segmenter.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        mask = results.segmentation_mask
        if mask is None:
            h, w = frame.shape[:2]
            return np.zeros((h, w), dtype=np.float32)
        # Ensure float32 in [0,1] and smooth edges
        mask = np.clip(mask.astype(np.float32), 0.0, 1.0)
        mask = cv2.GaussianBlur(mask, (21, 21), 0)
        return mask
```

**`effects.py` - ~40 lines**
```python
import cv2
import numpy as np

class BackgroundBlur:
    def apply(self, frame, mask, strength=25):
        if strength <= 0 or strength % 2 == 0:
            raise ValueError("--strength must be a positive odd integer, e.g., 3,5,7,...")
        frame_f = frame.astype(np.float32)
        mask_f = np.clip(mask.astype(np.float32), 0.0, 1.0)
        blurred = cv2.GaussianBlur(frame_f, (strength, strength), 0)
        mask_3d = np.stack((mask_f,) * 3, axis=-1)
        blended = frame_f * mask_3d + blurred * (1.0 - mask_3d)
        return np.clip(blended, 0, 255).astype(np.uint8)

class BackgroundReplace:
    def apply(self, frame, mask, background):
        if background is None:
            raise ValueError("Background image is not loaded or invalid.")
        frame_f = frame.astype(np.float32)
        mask_f = np.clip(mask.astype(np.float32), 0.0, 1.0)
        bg = cv2.resize(background, (frame.shape[1], frame.shape[0])).astype(np.float32)
        mask_3d = np.stack((mask_f,) * 3, axis=-1)
        blended = frame_f * mask_3d + bg * (1.0 - mask_3d)
        return np.clip(blended, 0, 255).astype(np.uint8)
```

**`core.py` - ~80 lines**
```python
import cv2
import pyvirtualcam
from segmentation import PersonSegmenter
from effects import BackgroundBlur, BackgroundReplace

class VideoEnhancer:
    def __init__(self, input_device=0, effect_type='blur', config=None):
        self.cap = cv2.VideoCapture(input_device)
        if not self.cap.isOpened():
            raise RuntimeError(f"Unable to open input camera device index {input_device}. Use 'camfx list-devices' to discover working indexes.")
        self.segmenter = PersonSegmenter()
        self.effect = self._create_effect(effect_type, config)
        self.output_device = (config or {}).get('vdevice', '/dev/video10')
        self.target_fps = int((config or {}).get('fps', 30))
        # Optional input dimensions
        target_width = (config or {}).get('width')
        target_height = (config or {}).get('height')
        if target_width:
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, int(target_width))
        if target_height:
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, int(target_height))
        
        # Get input dimensions (after any requested sets)
        self.width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        
        # Virtual camera output
        try:
            self.virtual_cam = pyvirtualcam.Camera(
                width=self.width, height=self.height, fps=self.target_fps, device=self.output_device
            )
        except Exception as exc:
            self.cap.release()
            raise RuntimeError(
                f"Failed to open virtual camera at {self.output_device}. Ensure v4l2loopback is loaded and the device is writable. Original error: {exc}"
            )
    
    def _create_effect(self, effect_type, config):
        if effect_type == 'blur':
            return BackgroundBlur()
        elif effect_type == 'replace':
            return BackgroundReplace()
        raise ValueError(f"Unknown effect_type: {effect_type}")
    
    def run(self, preview=False, **kwargs):
        while True:
            ret, frame = self.cap.read()
            if not ret:
                break
            
            mask = self.segmenter.get_mask(frame)
            processed = self.effect.apply(frame, mask, **kwargs)
            
            self.virtual_cam.send(cv2.cvtColor(processed, cv2.COLOR_BGR2RGB))
            self.virtual_cam.sleep_until_next_frame()
            if preview:
                cv2.imshow('camfx preview', processed)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
        self.cap.release()
        try:
            cv2.destroyAllWindows()
        except Exception:
            pass
```

**`cli.py` - ~40 lines**
```python
import click
import cv2
from core import VideoEnhancer

@click.group()
def cli():
    pass

@cli.command()
@click.option('--strength', default=25, type=int)
@click.option('--input', default=0, type=int)
@click.option('--vdevice', default='/dev/video10', type=str)
@click.option('--preview', is_flag=True, default=False)
@click.option('--width', default=None, type=int)
@click.option('--height', default=None, type=int)
@click.option('--fps', default=30, type=int)
def blur(strength, input, vdevice, preview, width, height, fps):
    enhancer = VideoEnhancer(
        input,
        effect_type='blur',
        config={'vdevice': vdevice, 'width': width, 'height': height, 'fps': fps},
    )
    try:
        enhancer.run(preview=preview, strength=strength)
    except KeyboardInterrupt:
        print("Stopped")

@cli.command()
@click.option('--image', required=True, type=str)
@click.option('--input', default=0, type=int)
@click.option('--vdevice', default='/dev/video10', type=str)
@click.option('--preview', is_flag=True, default=False)
@click.option('--width', default=None, type=int)
@click.option('--height', default=None, type=int)
@click.option('--fps', default=30, type=int)
def replace(image, input, vdevice, preview, width, height, fps):
    bg = cv2.imread(image)
    if bg is None:
        raise click.ClickException(f"Failed to read background image: {image}")
    enhancer = VideoEnhancer(
        input,
        effect_type='replace',
        config={'vdevice': vdevice, 'width': width, 'height': height, 'fps': fps},
    )
    try:
        enhancer.run(preview=preview, background=bg)
    except KeyboardInterrupt:
        print("Stopped")

@cli.command('list-devices')
def list_devices():
    """List available camera devices and indexes."""
    import glob
    candidates = sorted(glob.glob('/dev/video*'))
    found = []
    for idx in range(10):
        cap = cv2.VideoCapture(idx)
        if cap.isOpened():
            found.append(f"index={idx}")
            cap.release()
    print("Detected device nodes:", ", ".join(candidates))
    print("Usable indexes:", ", ".join(found) if found else "none")

if __name__ == '__main__':
    cli()
```

### 1.4 Dependencies (Minimal)

**`requirements.txt`**
```
mediapipe==0.10.0
opencv-python==4.8.0
pyvirtualcam==0.11.0
click==8.1.7
numpy==1.24.0
```

### 1.5 Setup & Installation

**`setup.py`**
```python
from setuptools import setup, find_packages

setup(
    name='camfx',
    version='0.1.0',
    packages=find_packages(),
    install_requires=[
        'mediapipe>=0.10.0',
        'opencv-python>=4.8.0',
        'pyvirtualcam>=0.11.0',
        'click>=8.1.0',
        'numpy>=1.24.0',
    ],
    entry_points={
        'console_scripts': [
            'camfx=camfx.cli:cli',
        ],
    },
)
```

**Setup Instructions:**
```bash
# 1. Create virtual camera device
sudo modprobe v4l2loopback devices=1 video_nr=10 card_label="camfx" exclusive_caps=1

# 2. Create and activate virtual environment (recommended)
python3 -m venv .venv
source .venv/bin/activate

# 3. Install package (editable for local dev)
pip install -U pip wheel
pip install -e .

# 4. Run
camfx blur --strength 25
```

**Local Development Commands:**
```bash
# Lint and format (if using ruff)
ruff check . && ruff format .

# Run tests (see Testing section)
pytest -q

# Deactivate venv when done
deactivate
```

### 1.6 MVP Testing Checklist

- [ ] Install dependencies without errors
- [ ] Virtual camera device created successfully
- [ ] Blur effect works (visible on video conferencing app)
- [ ] Background replacement works with static image
- [ ] CLI commands execute without crashes
- [ ] Clean exit with Ctrl+C
- [ ] FPS performance acceptable (>20 FPS)
- [ ] CLI flags validated (input, vdevice, preview)
- [ ] README quickstart completes successfully

---

## Phase 2: Polish & Stability (After MVP)

### 2.1 Improvements
- Add lighting adjustment (simple brightness/contrast)
- Improve mask smoothing to reduce jitter
- Add FPS counter for performance monitoring
- Configuration file support (YAML)
- Better error handling and logging

### 2.2 Enhancements
- Add more blur styles (motion blur, pixelated)
- Support for multiple background images (random selection)
- Hotkey support for switching effects
- Performance optimization for lower-end systems

### 2.3 Packaging (DEB & RPM)
- Create distribution metadata with `pyproject.toml`/`setup.cfg`
- Build Python wheel and sdist: `pipx run build`
- Create native installers:
  - Debian/Ubuntu (.deb) via `fpm` or `debuild`
    - Depends: `python3, python3-venv, v4l2loopback-dkms`
    - Post-install: optional `modprobe v4l2loopback`, udev permissions
  - Fedora/RHEL (.rpm) via `fpm` or `rpmbuild`
    - Depends: `python3, python3-virtualenv, kmod-v4l2loopback`
    - Post-install: SELinux contexts if needed
- Makefile targets: `make build`, `make pkg-deb`, `make pkg-rpm`
- CI: Build and attach .deb and .rpm on tagged releases

### 2.4 CLI (Full Controls)
- Global: `--input`, `--vdevice`, `--width`, `--height`, `--fps`, `--preview`, `--log-level`
- Subcommands:
  - `blur` with `--strength`, future `--bokeh`
  - `replace` with `--image`, `--fit {cover,contain,stretch}`
  - `list-devices` to enumerate input/output devices
  - `doctor` to verify kernel module, permissions, camera access
  - `service` to run as background process
- Config file: `~/.config/camfx/config.yaml` reflecting CLI flags

---

## Phase 3: Advanced Features (Future)

### 3.1 Features
- Auto-detect and enhance lighting
- Edge refinement for better compositing
- Multi-person support
- Real-time preview window
- Configuration GUI (optional)
- D-Bus service for system integration

### 3.2 Desktop Integration (GNOME Settings)
- GNOME Control Center panel under Cameras with:
  - Live preview of input and processed output
  - Effect selection, blur strength, background image picker
  - Virtual camera on/off and device selection
- Approach:
  - Expose D-Bus API from a `camfx` daemon for real-time control
  - GNOME Settings plugin or Shell extension consuming D-Bus API
  - Package schemas/assets in deb/rpm with proper install hooks

### 3.3 Acceleration Roadmap (GPU & NPU)
- GPU: OpenCV CUDA ops, MediaPipe GPU delegate, ONNX Runtime/Torch CUDA
- NPU: ONNX Runtime with OpenVINO/NNAPI/other platform delegates
- Capability detection with CPU fallback
- CLI: `--accel {cpu,cuda,vulkan,openvino}` and `--accel-device 0`

---

## Success Criteria for MVP

1. **Works out of the box** - Install and run in 3 commands
2. **Low resource usage** - Runs smoothly on mid-range hardware
3. **Clean API** - Easy for others to build on top
4. **No bloat** - Minimal dependencies, simple codebase
5. **Documented** - Clear README with examples

---

## Development Timeline

- **Week 1:** Core implementation (segmentation + blur effect)
- **Week 2:** Background replacement + CLI
- **Week 3:** Testing, bug fixes, documentation
- **Total:** 3 weeks to MVP

---

## File Size Estimates

- Total code (MVP): ~250 lines of Python
- Dependencies: ~500MB (mostly OpenCV + MediaPipe)
- Build time: ~5 minutes
- First run setup: ~2 minutes

---

## Deployment

1. Create GitHub repository
2. Add to PyPI for easy installation
3. Create installation script for virtual camera setup
4. Document usage with examples
5. Provide native packages (.deb and .rpm) with post-install guidance

---

## Documentation

### README
- Overview and features
- Quickstart with venv, install, and first run
- CLI reference and examples
- Troubleshooting (camera access, v4l2loopback)
- Packaging/install notes for Debian/Fedora

### Local Setup Docs (`docs/local_dev.md`)
- Prerequisites (kernel module, Python version)
- Creating and using a virtual environment
- Running from source, tests, and linting
- Building packages and using `camfx doctor`

---

## Testing

### Scope (MVP)
- Unit tests for `segmentation.PersonSegmenter.get_mask` (mock MediaPipe)
- Unit tests for `effects.BackgroundBlur.apply` and `effects.BackgroundReplace.apply`
- Smoke test for `core.VideoEnhancer` loop with synthetic frames
- CLI tests with Click runner for `blur`/`replace` parsing

### Tooling
- `pytest` + `pytest-mock`
- GitHub Actions to run tests on PRs and main

---

## Notes

- Focus on simplicity, not features
- Linux-only for MVP (no Windows/macOS support)
- Use existing battle-tested libraries (MediaPipe, OpenCV)
- Keep code readable and well-commented
- Avoid unnecessary abstractions

---

## License

MIT License

Copyright (c) 2025 camfx contributors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
