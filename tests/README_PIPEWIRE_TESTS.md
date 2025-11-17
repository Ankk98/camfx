# PipeWire Tests Documentation

This directory contains comprehensive tests for the PipeWire-related functionality in the camfx project.

## Test Files

### test_pipewire_input.py

Tests for `camfx/input_pipewire.py` - the PipeWire virtual camera input module using GStreamer.

**Test Coverage (35 tests):**

1. **TestFindPipewireSourceId** (9 tests)
   - Finding valid PipeWire sources
   - Handling source not found scenarios
   - Empty output handling
   - pw-dump command failures
   - Timeout handling
   - JSON parsing errors
   - Filtering by Video/Source media class
   - Handling missing properties
   - Exception handling

2. **TestPipeWireInputInit** (4 tests)
   - GStreamer availability checking
   - Source existence validation
   - Custom and default source names
   - Initialization error handling

3. **TestPipeWireInputPipeline** (4 tests)
   - Pipeline element creation
   - Parse failures
   - Element not found scenarios
   - State change failures

4. **TestPipeWireInputRead** (5 tests)
   - Reading frames from queue
   - Empty queue handling
   - Not running state handling
   - Missing appsink handling
   - Thread safety

5. **TestPipeWireInputCallbacks** (6 tests)
   - Bus message handlers (error, warning, EOS)
   - New sample callbacks
   - Buffer handling
   - Exception handling

6. **TestPipeWireInputCleanup** (5 tests)
   - Resource release
   - Idempotent cleanup
   - isOpened state checking
   - Stopped state handling
   - Missing pipeline handling

7. **TestPipeWireInputEdgeCases** (2 tests)
   - Multiple sources with same media class
   - Frame queue maxlen behavior

### test_pipewire_output.py

Tests for `camfx/output_pipewire.py` - the PipeWire virtual camera output module using GStreamer.

**Test Coverage (40 tests):**

1. **TestWirePlumberCheck** (6 tests)
   - Wireplumber service status checking
   - systemctl command handling
   - Fallback to pgrep
   - Command failures
   - FileNotFoundError handling

2. **TestPipeWireOutputProperties** (3 tests)
   - Frame time calculations for different FPS
   - Frame size calculations

3. **TestPipeWireOutputValidation** (1 test)
   - Frame size validation

4. **TestPipeWireOutputStateMethods** (2 tests)
   - GStreamer state enum values
   - FlowReturn enum values

5. **TestPipeWireOutputConstants** (3 tests)
   - Default camera names
   - Common video resolutions
   - Common framerates

6. **TestPipeWireOutputIntegration** (3 tests)
   - GStreamer import checking
   - GStreamer initialization
   - Version information

7. **TestPipeWireOutputBufferOperations** (2 tests)
   - Buffer allocation
   - Buffer filling

8. **TestPipeWireOutputErrorScenarios** (3 tests)
   - Invalid frame sizes
   - Zero dimensions
   - Negative dimensions

9. **TestPipeWireOutputTimingOperations** (3 tests)
   - Sleep time calculations
   - Timestamp generation

10. **TestPipeWireOutputModuleImport** (3 tests)
    - Module import verification
    - Class existence
    - Required dependencies

11. **TestPipeWireOutputPipelineString** (2 tests)
    - Pipeline string format validation
    - Different resolution handling

12. **TestPipeWireOutputMediaProperties** (3 tests)
    - media.class format
    - media.name format
    - node.description format

13. **TestPipeWireOutputCleanupBehavior** (2 tests)
    - Pipeline cleanup
    - Appsrc cleanup

14. **TestPipeWireOutputDocumentation** (4 tests)
    - Class docstring
    - Method docstrings

## Running the Tests

### Run all PipeWire tests:
```bash
python -m pytest tests/test_pipewire_*.py -v
```

### Run only input tests:
```bash
python -m pytest tests/test_pipewire_input.py -v
```

### Run only output tests:
```bash
python -m pytest tests/test_pipewire_output.py -v
```

### Run with coverage:
```bash
python -m pytest tests/test_pipewire_*.py --cov=camfx.input_pipewire --cov=camfx.output_pipewire --cov-report=html
```

## Test Strategy

### Mocking Approach

The tests use extensive mocking to avoid dependencies on:
- Actual PipeWire daemon running
- GStreamer pipelines being created
- Real video hardware
- System services (wireplumber)

This makes tests:
- Fast (no actual video processing)
- Reliable (no hardware dependencies)
- Portable (run on any system)

### What's Tested

1. **Input Module:**
   - PipeWire source discovery via pw-dump
   - GStreamer pipeline setup for reading
   - Frame reading and queuing
   - Thread safety
   - Resource cleanup
   - Error handling

2. **Output Module:**
   - Wireplumber availability checking
   - GStreamer pipeline setup for writing
   - Frame sending
   - Frame rate control
   - Buffer management
   - Resource cleanup
   - Error handling

### Test Organization

Tests are organized by:
- **Functionality**: Grouped into test classes by feature
- **Isolation**: Each test is independent and can run alone
- **Clarity**: Descriptive test names that explain what is being tested

## Dependencies

Required for tests to run:
- pytest
- numpy
- GStreamer (gi.repository.Gst) - skipped if not available
- Standard library modules (subprocess, json, threading, etc.)

## Notes

- Some tests are marked with `@pytest.mark.skipif(not GSTREAMER_AVAILABLE)` to skip when GStreamer is not installed
- Tests use real GStreamer enums (Gst.FlowReturn, Gst.State) where needed for accurate comparisons
- Thread safety tests verify concurrent access doesn't cause errors
- Tests cover both success and failure paths

## Future Improvements

Potential additions:
- Integration tests with real PipeWire daemon
- Performance benchmarks
- Memory leak detection
- Long-running stability tests
- Stress tests with high frame rates

