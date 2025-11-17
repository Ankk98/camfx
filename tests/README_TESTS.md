# CamFX Tests

This directory contains unit tests and integration tests for the CamFX project.

## Test Structure

```
tests/
├── test_effect_chaining.py       # Effect chaining unit tests
├── test_pipewire_input.py        # PipeWire input unit tests (mocked)
├── test_pipewire_output.py       # PipeWire output unit tests (mocked)
├── test_pipewire_integration.py  # Integration tests (real GStreamer/PipeWire)
└── README_TESTS.md               # This file
```

## Test Types

### Unit Tests
Unit tests use mocks and don't require actual PipeWire or hardware:
- `test_pipewire_input.py` - Tests PipeWireInput class with mocked GStreamer
- `test_pipewire_output.py` - Tests PipeWireOutput class with mocked components
- `test_effect_chaining.py` - Tests effect chaining functionality

### Integration Tests
Integration tests use real GStreamer and PipeWire components:
- `test_pipewire_integration.py` - End-to-end tests with real pipelines

## Running Tests

### Run All Unit Tests (Fast, No Dependencies)
```bash
# Run all unit tests (excluding integration tests)
pytest tests/ -m "not integration" -v

# Or run specific test files
pytest tests/test_pipewire_input.py -v
pytest tests/test_pipewire_output.py -v
```

### Run Integration Tests (Requires PipeWire/GStreamer)
```bash
# Run all integration tests
pytest tests/test_pipewire_integration.py -v -m integration

# Check system compatibility first
pytest tests/test_pipewire_integration.py::TestPipeWireSystemCheck -v
```

### Run Specific Tests
```bash
# Run tests in a specific class
pytest tests/test_pipewire_input.py::TestPipeWireInputInit -v

# Run a specific test method
pytest tests/test_pipewire_input.py::TestPipeWireInputInit::test_init_default_source_name -v

# Run tests matching a pattern
pytest tests/ -k "pipewire" -v
```

### Run With Different Verbosity
```bash
# Minimal output
pytest tests/ -q

# Verbose output
pytest tests/ -v

# Very verbose (show full diff)
pytest tests/ -vv

# Show print statements
pytest tests/ -s
```

## Requirements

### Unit Tests
- Python 3.8+
- pytest
- Required: `gi`, `numpy`
- Mocking works without actual GStreamer installation

### Integration Tests
Additional requirements:
- GStreamer 1.0+ with Python bindings (PyGObject)
- PipeWire daemon running
- wireplumber session manager running
- GStreamer plugins:
  - gst-plugins-base (videoconvert, videotestsrc)
  - gst-plugins-good (optional)
  - gst-plugin-pipewire (pipewiresrc, pipewiresink)

## Installing Dependencies

### Fedora/RHEL
```bash
# Install GStreamer and PipeWire
sudo dnf install gstreamer1 gstreamer1-plugins-base \
                 pipewire pipewire-gstreamer wireplumber \
                 python3-gobject

# Install Python test dependencies
pip install pytest numpy
```

### Ubuntu/Debian
```bash
# Install GStreamer and PipeWire
sudo apt install gstreamer1.0-tools gstreamer1.0-plugins-base \
                 pipewire pipewire-audio-client-libraries \
                 gstreamer1.0-pipewire \
                 python3-gi python3-gi-cairo gir1.2-gst-1.0

# Install Python test dependencies
pip install pytest numpy
```

### Arch Linux
```bash
# Install GStreamer and PipeWire
sudo pacman -S gstreamer gst-plugins-base gst-plugins-good \
               pipewire wireplumber python-gobject

# Install Python test dependencies
pip install pytest numpy
```

## Checking Your System

Run the system check tests to see what's available:
```bash
pytest tests/test_pipewire_integration.py::TestPipeWireSystemCheck -v -s
```

This will show:
- ✓ PipeWire daemon status
- ✓ wireplumber status
- ✓ Available GStreamer elements
- ✓ pw-dump command availability

## Common Issues

### "ModuleNotFoundError: No module named 'gi'"
Install PyGObject:
```bash
# Fedora/RHEL
sudo dnf install python3-gobject

# Ubuntu/Debian
sudo apt install python3-gi

# Or via pip (may need system packages first)
pip install PyGObject
```

### "wireplumber not running"
Start wireplumber:
```bash
systemctl --user start wireplumber
systemctl --user enable wireplumber  # Auto-start on login
```

### "PipeWire daemon not running"
Start PipeWire:
```bash
systemctl --user start pipewire
systemctl --user enable pipewire  # Auto-start on login
```

### "GStreamer element not found"
Check which plugins are installed:
```bash
gst-inspect-1.0 | grep -i pipewire
gst-inspect-1.0 pipewiresrc
gst-inspect-1.0 pipewiresink
```

Install missing plugins:
```bash
# Fedora
sudo dnf install gstreamer1-plugin-pipewire

# Ubuntu
sudo apt install gstreamer1.0-pipewire
```

### Integration Tests Skip or Fail
Integration tests are automatically skipped if:
- GStreamer is not available
- PipeWire is not running
- wireplumber is not running
- Required GStreamer elements are missing

This is expected behavior. Unit tests will still run and validate the code logic.

## Test Coverage

To generate coverage reports:
```bash
# Install coverage tools
pip install pytest-cov

# Run with coverage
pytest tests/ --cov=camfx --cov-report=html --cov-report=term

# View HTML report
firefox htmlcov/index.html
```

## Continuous Integration

For CI/CD pipelines:
```bash
# Run only unit tests (fast, no system dependencies)
pytest tests/ -m "not integration" -v --tb=short

# Run all tests if PipeWire is available
pytest tests/ -v --tb=short
```

## Writing New Tests

### Unit Test Template
```python
"""Tests for new_module."""

import pytest
from unittest.mock import Mock, patch
from camfx.new_module import NewClass

class TestNewClass:
    """Test NewClass functionality."""
    
    def test_basic_functionality(self):
        """Test basic functionality."""
        obj = NewClass()
        assert obj is not None
```

### Integration Test Template
```python
"""Integration tests for new_feature."""

import pytest

pytestmark = pytest.mark.integration

@pytest.mark.skipif(condition, reason="reason")
class TestNewFeatureIntegration:
    """Integration tests for new feature."""
    
    def test_real_functionality(self):
        """Test with real components."""
        # Use real components, not mocks
        result = real_function()
        assert result is not None
```

## Useful pytest Options

```bash
# Stop on first failure
pytest tests/ -x

# Run last failed tests
pytest tests/ --lf

# Run tests in parallel (requires pytest-xdist)
pytest tests/ -n auto

# Show slowest tests
pytest tests/ --durations=10

# Generate JUnit XML report
pytest tests/ --junit-xml=report.xml
```

## Test Markers

Use markers to selectively run tests:
```bash
# Run only integration tests
pytest tests/ -m integration

# Exclude integration tests
pytest tests/ -m "not integration"

# Run slow tests only
pytest tests/ -m slow

# Exclude slow tests
pytest tests/ -m "not slow"
```

## Getting Help

```bash
# Show available markers
pytest --markers

# Show available fixtures
pytest --fixtures

# Show pytest help
pytest --help
```

## Contributing

When adding new tests:
1. Place unit tests in appropriate `test_*.py` files
2. Mark integration tests with `@pytest.mark.integration`
3. Add docstrings to test classes and methods
4. Use descriptive test names: `test_<what>_<condition>_<expected>`
5. Mock external dependencies in unit tests
6. Test both success and failure cases
7. Clean up resources in tests (use fixtures or finally blocks)

## Summary

**Quick Commands:**
```bash
# Fast unit tests only
pytest tests/ -m "not integration" -v

# All tests including integration
pytest tests/ -v

# Check system compatibility
pytest tests/test_pipewire_integration.py::TestPipeWireSystemCheck -v -s

# Specific test file
pytest tests/test_pipewire_input.py -v
```

