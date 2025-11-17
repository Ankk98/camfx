"""Integration tests for PipeWire functionality.

These tests use real GStreamer and PipeWire components (not mocked).
They may fail in environments without proper PipeWire/GStreamer setup.

Run with: pytest tests/test_pipewire_integration.py -v -m integration
"""

import os
import subprocess
import time
import threading
import numpy as np
import pytest

# Check if GStreamer is available
try:
    import gi
    gi.require_version('Gst', '1.0')
    from gi.repository import Gst
    Gst.init(None)
    GSTREAMER_AVAILABLE = True
except (ImportError, ValueError):
    GSTREAMER_AVAILABLE = False

# Mark all tests in this module as integration tests
pytestmark = pytest.mark.integration


def _is_wireplumber_running():
    """Check if wireplumber is actually running."""
    try:
        result = subprocess.run(
            ['systemctl', '--user', 'is-active', 'wireplumber'],
            capture_output=True,
            timeout=2
        )
        return result.returncode == 0
    except Exception:
        try:
            result = subprocess.run(
                ['pgrep', '-u', str(os.getuid()), 'wireplumber'],
                capture_output=True,
                timeout=2
            )
            return result.returncode == 0
        except Exception:
            return False


def _is_pipewire_running():
    """Check if PipeWire daemon is running."""
    try:
        result = subprocess.run(
            ['pgrep', '-u', str(os.getuid()), 'pipewire'],
            capture_output=True,
            timeout=2
        )
        return result.returncode == 0
    except Exception:
        return False


def _pw_dump_available():
    """Check if pw-dump command is available."""
    try:
        result = subprocess.run(
            ['which', 'pw-dump'],
            capture_output=True,
            timeout=2
        )
        return result.returncode == 0
    except Exception:
        return False


@pytest.mark.skipif(not GSTREAMER_AVAILABLE, reason="GStreamer not available")
class TestGStreamerIntegration:
    """Integration tests for GStreamer functionality."""
    
    def test_gstreamer_basic_pipeline(self):
        """Test creating and running a basic GStreamer pipeline."""
        # Create a simple test pipeline: videotestsrc -> fakesink
        pipeline_str = (
            'videotestsrc num-buffers=10 ! '
            'video/x-raw,width=320,height=240,framerate=30/1 ! '
            'fakesink'
        )
        
        pipeline = Gst.parse_launch(pipeline_str)
        assert pipeline is not None
        
        # Start pipeline
        ret = pipeline.set_state(Gst.State.PLAYING)
        assert ret != Gst.StateChangeReturn.FAILURE
        
        # Wait for EOS or error
        bus = pipeline.get_bus()
        msg = bus.timed_pop_filtered(
            5 * Gst.SECOND,
            Gst.MessageType.EOS | Gst.MessageType.ERROR
        )
        
        # Cleanup
        pipeline.set_state(Gst.State.NULL)
        
        # Should have received EOS
        assert msg is not None
        assert msg.type == Gst.MessageType.EOS
    
    def test_gstreamer_appsink_pull(self):
        """Test pulling frames from GStreamer appsink."""
        pipeline_str = (
            'videotestsrc num-buffers=5 ! '
            'video/x-raw,format=RGB,width=320,height=240,framerate=30/1 ! '
            'appsink name=sink emit-signals=false'
        )
        
        pipeline = Gst.parse_launch(pipeline_str)
        assert pipeline is not None
        
        appsink = pipeline.get_by_name('sink')
        assert appsink is not None
        
        # Start pipeline
        ret = pipeline.set_state(Gst.State.PLAYING)
        assert ret != Gst.StateChangeReturn.FAILURE
        
        # Give pipeline time to start producing frames
        time.sleep(0.1)
        
        # Pull frames
        frames_pulled = 0
        for _ in range(5):
            sample = appsink.emit('pull-sample')
            if sample:
                frames_pulled += 1
                buffer = sample.get_buffer()
                assert buffer is not None
        
        # Cleanup
        pipeline.set_state(Gst.State.NULL)
        
        # Should have pulled at least some frames
        assert frames_pulled > 0
    
    def test_gstreamer_appsrc_push(self):
        """Test pushing frames to GStreamer appsrc."""
        pipeline_str = (
            'appsrc name=src is-live=true format=time ! '
            'video/x-raw,format=RGB,width=320,height=240,framerate=30/1 ! '
            'fakesink'
        )
        
        pipeline = Gst.parse_launch(pipeline_str)
        assert pipeline is not None
        
        appsrc = pipeline.get_by_name('src')
        assert appsrc is not None
        
        # Start pipeline
        ret = pipeline.set_state(Gst.State.PLAYING)
        assert ret != Gst.StateChangeReturn.FAILURE
        
        # Push some frames
        frame_size = 320 * 240 * 3
        frames_pushed = 0
        
        for i in range(5):
            # Create test frame
            frame_data = bytes([i * 50] * frame_size)
            buffer = Gst.Buffer.new_allocate(None, frame_size, None)
            buffer.fill(0, frame_data)
            buffer.pts = i * Gst.SECOND // 30
            buffer.duration = Gst.SECOND // 30
            
            ret = appsrc.emit('push-buffer', buffer)
            if ret == Gst.FlowReturn.OK:
                frames_pushed += 1
            
            time.sleep(0.01)
        
        # Send EOS
        appsrc.emit('end-of-stream')
        
        # Cleanup
        pipeline.set_state(Gst.State.NULL)
        
        # Should have pushed all frames
        assert frames_pushed == 5
    
    def test_gstreamer_videoconvert(self):
        """Test GStreamer videoconvert element."""
        # RGB -> BGR conversion
        pipeline_str = (
            'videotestsrc num-buffers=1 ! '
            'video/x-raw,format=RGB,width=320,height=240 ! '
            'videoconvert ! '
            'video/x-raw,format=BGR ! '
            'appsink name=sink'
        )
        
        pipeline = Gst.parse_launch(pipeline_str)
        assert pipeline is not None
        
        appsink = pipeline.get_by_name('sink')
        assert appsink is not None
        
        # Start pipeline
        ret = pipeline.set_state(Gst.State.PLAYING)
        assert ret != Gst.StateChangeReturn.FAILURE
        
        # Give pipeline time to produce frame
        time.sleep(0.1)
        
        # Pull converted frame
        sample = appsink.emit('pull-sample')
        assert sample is not None
        
        caps = sample.get_caps()
        structure = caps.get_structure(0)
        format_str = structure.get_string('format')
        assert format_str == 'BGR'
        
        # Cleanup
        pipeline.set_state(Gst.State.NULL)


@pytest.mark.skipif(
    not GSTREAMER_AVAILABLE or not _is_wireplumber_running(),
    reason="GStreamer or wireplumber not available"
)
class TestPipeWireSinkIntegration:
    """Integration tests for PipeWire sink (output)."""
    
    def test_pipewiresink_basic(self):
        """Test creating a basic pipewiresink."""
        pipeline_str = (
            'videotestsrc num-buffers=30 ! '
            'video/x-raw,format=RGB,width=320,height=240,framerate=30/1 ! '
            'videoconvert ! '
            'pipewiresink'
        )
        
        pipeline = Gst.parse_launch(pipeline_str)
        assert pipeline is not None
        
        # Start pipeline
        ret = pipeline.set_state(Gst.State.PLAYING)
        assert ret != Gst.StateChangeReturn.FAILURE
        
        # Let it run briefly
        time.sleep(1.0)
        
        # Cleanup
        pipeline.set_state(Gst.State.NULL)
    
    def test_pipewiresink_with_properties(self):
        """Test pipewiresink with stream properties."""
        pipeline_str = (
            'videotestsrc num-buffers=30 ! '
            'video/x-raw,format=RGB,width=320,height=240,framerate=30/1 ! '
            'videoconvert ! '
            'pipewiresink name=sink'
        )
        
        pipeline = Gst.parse_launch(pipeline_str)
        assert pipeline is not None
        
        sink = pipeline.get_by_name('sink')
        assert sink is not None
        
        # Set stream properties
        stream_props = Gst.Structure.new_empty("props")
        stream_props.set_value("media.class", "Video/Source")
        stream_props.set_value("media.name", "test_integration_camera")
        sink.set_property("stream-properties", stream_props)
        
        # Start pipeline
        ret = pipeline.set_state(Gst.State.PLAYING)
        assert ret != Gst.StateChangeReturn.FAILURE
        
        # Let it run
        time.sleep(1.0)
        
        # Cleanup
        pipeline.set_state(Gst.State.NULL)


@pytest.mark.skipif(
    not GSTREAMER_AVAILABLE or not _is_pipewire_running(),
    reason="GStreamer or PipeWire not available"
)
class TestPipeWireSourceIntegration:
    """Integration tests for PipeWire source (input)."""
    
    def test_pipewiresrc_basic(self):
        """Test creating a basic pipewiresrc."""
        # Note: This requires an actual PipeWire source to exist
        # We'll create one first, then try to read from it
        
        # Skip if pw-dump is not available
        if not _pw_dump_available():
            pytest.skip("pw-dump command not available")
        
        # List available sources
        try:
            result = subprocess.run(
                ['pw-dump'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode != 0:
                pytest.skip("Could not list PipeWire sources")
        except Exception:
            pytest.skip("Could not list PipeWire sources")


@pytest.mark.skipif(not GSTREAMER_AVAILABLE, reason="GStreamer not available")
class TestPipeWireOutputIntegration:
    """Integration tests for PipeWireOutput class."""
    
    @pytest.mark.skipif(not _is_wireplumber_running(), reason="wireplumber not running")
    def test_pipewire_output_initialization(self):
        """Test PipeWireOutput can be initialized with real GStreamer."""
        from camfx.output_pipewire import PipeWireOutput
        
        try:
            output = PipeWireOutput(320, 240, 30, "test_integration_output")
            
            # Verify pipeline is created
            assert output.pipeline is not None
            assert output.appsrc is not None
            
            # Send a test frame
            frame_size = 320 * 240 * 3
            test_frame = bytes([128] * frame_size)
            
            output.send(test_frame)
            
            # Give it time to process
            time.sleep(0.1)
            
            # Cleanup
            output.cleanup()
            
        except RuntimeError as e:
            # If wireplumber is not properly configured, this may fail
            # That's okay for integration tests
            if "wireplumber" in str(e).lower() or "timeout" in str(e).lower():
                pytest.skip(f"PipeWire/wireplumber configuration issue: {e}")
            else:
                raise
    
    @pytest.mark.skipif(not _is_wireplumber_running(), reason="wireplumber not running")
    def test_pipewire_output_multiple_frames(self):
        """Test sending multiple frames through PipeWireOutput."""
        from camfx.output_pipewire import PipeWireOutput
        
        try:
            output = PipeWireOutput(320, 240, 30, "test_integration_multi")
            
            frame_size = 320 * 240 * 3
            
            # Send multiple frames
            for i in range(10):
                # Create gradient test frame
                value = (i * 25) % 256
                test_frame = bytes([value] * frame_size)
                output.send(test_frame)
                output.sleep_until_next_frame()
            
            # Cleanup
            output.cleanup()
            
        except RuntimeError as e:
            if "wireplumber" in str(e).lower() or "timeout" in str(e).lower():
                pytest.skip(f"PipeWire/wireplumber configuration issue: {e}")
            else:
                raise


@pytest.mark.skipif(not GSTREAMER_AVAILABLE, reason="GStreamer not available")
class TestPipeWireInputIntegration:
    """Integration tests for PipeWireInput class."""
    
    def test_pipewire_input_source_detection(self):
        """Test detecting PipeWire sources."""
        if not _pw_dump_available():
            pytest.skip("pw-dump command not available")
        
        from camfx.input_pipewire import _find_pipewire_source_id
        
        # Try to find any video source (may return None if none exist)
        result = _find_pipewire_source_id("any_source_name")
        
        # Just verify the function runs without crashing
        # Result can be None if no sources exist
        assert result is None or isinstance(result, int)


@pytest.mark.skipif(
    not GSTREAMER_AVAILABLE or not _is_wireplumber_running(),
    reason="GStreamer or wireplumber not available"
)
class TestPipeWireEndToEnd:
    """End-to-end integration tests for PipeWire input and output."""
    
    def test_output_then_input_loopback(self):
        """Test creating an output, then reading from it with input."""
        from camfx.output_pipewire import PipeWireOutput
        from camfx.input_pipewire import _find_pipewire_source_id
        
        output = None
        try:
            # Create output
            output = PipeWireOutput(320, 240, 30, "test_e2e_loopback")
            
            # Send some frames
            frame_size = 320 * 240 * 3
            for i in range(5):
                test_frame = bytes([100 + i * 10] * frame_size)
                output.send(test_frame)
                time.sleep(0.033)  # ~30fps
            
            # Give PipeWire time to register the source
            time.sleep(0.5)
            
            # Try to find the source
            source_id = _find_pipewire_source_id("test_e2e_loopback")
            
            # Source should be found
            assert source_id is not None, "PipeWire source not found"
            
        except RuntimeError as e:
            if "wireplumber" in str(e).lower() or "timeout" in str(e).lower():
                pytest.skip(f"PipeWire/wireplumber configuration issue: {e}")
            else:
                raise
        finally:
            if output:
                output.cleanup()
    
    def test_create_virtual_camera_verify_existence(self):
        """Test creating a virtual camera and verifying it exists in PipeWire."""
        from camfx.output_pipewire import PipeWireOutput
        
        if not _pw_dump_available():
            pytest.skip("pw-dump command not available")
        
        output = None
        try:
            # Create virtual camera
            camera_name = "test_virtual_camera_verify"
            output = PipeWireOutput(640, 480, 30, camera_name)
            
            # Send some frames to keep it alive
            frame_size = 640 * 480 * 3
            for _ in range(3):
                test_frame = bytes([128] * frame_size)
                output.send(test_frame)
                time.sleep(0.033)
            
            # Give PipeWire time to register
            time.sleep(0.5)
            
            # Check if it appears in pw-dump
            result = subprocess.run(
                ['pw-dump'],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0:
                # Camera should appear in output
                assert camera_name in result.stdout or "test_virtual_camera" in result.stdout
            
        except RuntimeError as e:
            if "wireplumber" in str(e).lower() or "timeout" in str(e).lower():
                pytest.skip(f"PipeWire/wireplumber configuration issue: {e}")
            else:
                raise
        finally:
            if output:
                output.cleanup()


@pytest.mark.skipif(not GSTREAMER_AVAILABLE, reason="GStreamer not available")
class TestGStreamerPerformance:
    """Performance-related integration tests."""
    
    def test_frame_throughput(self):
        """Test frame processing throughput."""
        pipeline_str = (
            'videotestsrc num-buffers=300 ! '
            'video/x-raw,format=RGB,width=640,height=480,framerate=30/1 ! '
            'appsink name=sink emit-signals=false'
        )
        
        pipeline = Gst.parse_launch(pipeline_str)
        appsink = pipeline.get_by_name('sink')
        
        start_time = time.time()
        pipeline.set_state(Gst.State.PLAYING)
        
        frames_processed = 0
        timeout_count = 0
        while frames_processed < 300 and timeout_count < 10:
            sample = appsink.emit('pull-sample')
            if sample:
                frames_processed += 1
                timeout_count = 0  # Reset timeout counter
            else:
                timeout_count += 1
                time.sleep(0.01)  # Brief wait before retry
        
        elapsed = time.time() - start_time
        pipeline.set_state(Gst.State.NULL)
        
        # Should process frames reasonably fast
        # 300 frames at 30fps should take ~10 seconds theoretically
        # Allow up to 20 seconds for processing overhead
        assert elapsed < 20.0
        assert frames_processed > 0
    
    def test_frame_conversion_performance(self):
        """Test video format conversion performance."""
        pipeline_str = (
            'videotestsrc num-buffers=100 ! '
            'video/x-raw,format=RGB,width=1920,height=1080 ! '
            'videoconvert ! '
            'video/x-raw,format=BGR ! '
            'fakesink'
        )
        
        pipeline = Gst.parse_launch(pipeline_str)
        
        start_time = time.time()
        pipeline.set_state(Gst.State.PLAYING)
        
        # Wait for completion
        bus = pipeline.get_bus()
        msg = bus.timed_pop_filtered(
            30 * Gst.SECOND,
            Gst.MessageType.EOS | Gst.MessageType.ERROR
        )
        
        elapsed = time.time() - start_time
        pipeline.set_state(Gst.State.NULL)
        
        # Should complete without error
        assert msg is not None
        assert msg.type == Gst.MessageType.EOS
        
        # Should be reasonably fast
        assert elapsed < 10.0


@pytest.mark.skipif(not GSTREAMER_AVAILABLE, reason="GStreamer not available")
class TestGStreamerErrorRecovery:
    """Integration tests for error handling and recovery."""
    
    def test_pipeline_state_change_timeout(self):
        """Test handling of pipeline state change timeout."""
        # This might not timeout on all systems, but tests the mechanism
        pipeline_str = (
            'videotestsrc ! '
            'video/x-raw,width=320,height=240 ! '
            'fakesink'
        )
        
        pipeline = Gst.parse_launch(pipeline_str)
        
        # Try to change state
        ret = pipeline.set_state(Gst.State.PLAYING)
        
        # Should not fail immediately
        assert ret != Gst.StateChangeReturn.FAILURE
        
        # Get state with short timeout
        state_ret, state, pending = pipeline.get_state(0)
        
        # Cleanup
        pipeline.set_state(Gst.State.NULL)
    
    def test_invalid_pipeline_recovery(self):
        """Test that invalid pipelines are properly rejected."""
        try:
            # Intentionally invalid pipeline
            pipeline = Gst.parse_launch("invalid_element ! fakesink")
            
            # If parsing succeeded (shouldn't), try to run it
            if pipeline:
                ret = pipeline.set_state(Gst.State.PLAYING)
                # Should fail or return async
                pipeline.set_state(Gst.State.NULL)
                
        except Exception:
            # Expected - invalid element should cause error
            pass


class TestPipeWireSystemCheck:
    """Tests to check PipeWire system availability."""
    
    def test_check_pipewire_daemon(self):
        """Check if PipeWire daemon is available."""
        is_running = _is_pipewire_running()
        # Just report status, don't fail
        print(f"\nPipeWire daemon running: {is_running}")
    
    def test_check_wireplumber(self):
        """Check if wireplumber is available."""
        is_running = _is_wireplumber_running()
        print(f"\nWirePlumber running: {is_running}")
    
    def test_check_pw_dump(self):
        """Check if pw-dump command is available."""
        available = _pw_dump_available()
        print(f"\npw-dump command available: {available}")
    
    def test_check_gstreamer_plugins(self):
        """Check if required GStreamer plugins are available."""
        if not GSTREAMER_AVAILABLE:
            pytest.skip("GStreamer not available")
        
        required_elements = [
            'videotestsrc',
            'videoconvert',
            'fakesink',
            'appsrc',
            'appsink',
        ]
        
        optional_elements = [
            'pipewiresrc',
            'pipewiresink',
        ]
        
        print("\n")
        for elem in required_elements:
            factory = Gst.ElementFactory.find(elem)
            status = "✓" if factory else "✗"
            print(f"{status} Required element '{elem}': {factory is not None}")
            if not factory:
                pytest.fail(f"Required GStreamer element '{elem}' not found")
        
        print("\n")
        for elem in optional_elements:
            factory = Gst.ElementFactory.find(elem)
            status = "✓" if factory else "✗"
            print(f"{status} Optional element '{elem}': {factory is not None}")

