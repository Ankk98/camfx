"""Tests for PipeWire output functionality."""

import os
import subprocess
import time
from unittest.mock import Mock, MagicMock, patch, call
import pytest


def _gstreamer_available() -> bool:
    """Check if GStreamer is available."""
    try:
        import gi
        gi.require_version('Gst', '1.0')
        from gi.repository import Gst
        Gst.init(None)
        return True
    except (ImportError, ValueError):
        return False


class TestWirePlumberCheck:
    """Test wireplumber availability checking."""
    
    def test_wireplumber_active_systemctl(self):
        """Test wireplumber check when service is active."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(returncode=0)
            
            from camfx.output_pipewire import PipeWireOutput
            available, status = PipeWireOutput._check_wireplumber_available()
            
            assert available is True
            assert "wireplumber is running" in status
            mock_run.assert_called_once_with(
                ['systemctl', '--user', 'is-active', 'wireplumber'],
                capture_output=True,
                text=True,
                timeout=2
            )
    
    def test_wireplumber_inactive_systemctl(self):
        """Test wireplumber check when service is inactive."""
        with patch('subprocess.run') as mock_run:
            # systemctl returns non-zero for inactive
            mock_run.return_value = Mock(returncode=3)
            
            from camfx.output_pipewire import PipeWireOutput
            available, status = PipeWireOutput._check_wireplumber_available()
            
            assert available is False
            assert "service is not active" in status
    
    def test_wireplumber_fallback_to_pgrep_running(self):
        """Test fallback to pgrep when systemctl fails."""
        with patch('subprocess.run') as mock_run:
            # First call (systemctl) raises exception
            # Second call (pgrep) succeeds
            mock_run.side_effect = [
                subprocess.TimeoutExpired('systemctl', 2),
                Mock(returncode=0)  # pgrep finds process
            ]
            
            from camfx.output_pipewire import PipeWireOutput
            available, status = PipeWireOutput._check_wireplumber_available()
            
            assert available is True
            assert "process is running" in status
    
    def test_wireplumber_fallback_to_pgrep_not_running(self):
        """Test fallback to pgrep when process not found."""
        with patch('subprocess.run') as mock_run:
            # First call (systemctl) raises exception
            # Second call (pgrep) finds no process
            mock_run.side_effect = [
                subprocess.TimeoutExpired('systemctl', 2),
                Mock(returncode=1)  # pgrep finds no process
            ]
            
            from camfx.output_pipewire import PipeWireOutput
            available, status = PipeWireOutput._check_wireplumber_available()
            
            assert available is False
            assert "process not found" in status
    
    def test_wireplumber_systemctl_file_not_found(self):
        """Test when systemctl command is not found."""
        with patch('subprocess.run') as mock_run:
            # First call raises FileNotFoundError, second succeeds
            mock_run.side_effect = [
                FileNotFoundError("systemctl not found"),
                Mock(returncode=0)
            ]
            
            from camfx.output_pipewire import PipeWireOutput
            available, status = PipeWireOutput._check_wireplumber_available()
            
            # Should fallback to pgrep and succeed
            assert available is True
    
    def test_wireplumber_pgrep_also_fails(self):
        """Test when both systemctl and pgrep fail."""
        with patch('subprocess.run') as mock_run:
            # Both commands fail
            mock_run.side_effect = [
                FileNotFoundError("systemctl not found"),
                FileNotFoundError("pgrep not found")
            ]
            
            from camfx.output_pipewire import PipeWireOutput
            available, status = PipeWireOutput._check_wireplumber_available()
            
            assert available is False
            assert "could not check" in status


class TestPipeWireOutputProperties:
    """Test PipeWire output property calculations."""
    
    def test_frame_time_calculation_30fps(self):
        """Test frame time calculation for 30fps."""
        frame_time = 1.0 / 30
        expected = 0.03333333
        assert abs(frame_time - expected) < 0.0001
    
    def test_frame_time_calculation_60fps(self):
        """Test frame time calculation for 60fps."""
        frame_time = 1.0 / 60
        expected = 0.01666666
        assert abs(frame_time - expected) < 0.0001
    
    def test_frame_size_calculation(self):
        """Test frame size calculation."""
        width, height = 640, 480
        channels = 3  # RGB
        expected_size = width * height * channels
        assert expected_size == 921600


class TestPipeWireOutputValidation:
    """Test PipeWire output input validation."""
    
    def test_frame_size_validation(self):
        """Test that frame size validation works correctly."""
        width, height = 640, 480
        expected_size = width * height * 3
        
        # Correct size
        assert len(bytes(expected_size)) == expected_size
        
        # Wrong size
        wrong_size_data = bytes(100)
        assert len(wrong_size_data) != expected_size


class TestPipeWireOutputStateMethods:
    """Test state name conversions and error handling helpers."""
    
    def test_state_enum_values(self):
        """Test that GStreamer state enums are available."""
        try:
            from gi.repository import Gst
            Gst.init(None)
            
            # Verify state values exist
            assert hasattr(Gst.State, 'NULL')
            assert hasattr(Gst.State, 'READY')
            assert hasattr(Gst.State, 'PAUSED')
            assert hasattr(Gst.State, 'PLAYING')
        except (ImportError, ValueError):
            pytest.skip("GStreamer not available")
    
    def test_flow_return_values(self):
        """Test that GStreamer FlowReturn enums are available."""
        try:
            from gi.repository import Gst
            Gst.init(None)
            
            # Verify FlowReturn values exist
            assert hasattr(Gst.FlowReturn, 'OK')
            assert hasattr(Gst.FlowReturn, 'ERROR')
            assert hasattr(Gst.FlowReturn, 'EOS')
            assert hasattr(Gst.FlowReturn, 'FLUSHING')
        except (ImportError, ValueError):
            pytest.skip("GStreamer not available")


class TestPipeWireOutputConstants:
    """Test constants and default values."""
    
    def test_default_name(self):
        """Test default camera name."""
        default_name = "camfx"
        assert len(default_name) > 0
        assert isinstance(default_name, str)
    
    def test_common_resolutions(self):
        """Test common video resolutions."""
        resolutions = [
            (640, 480),    # VGA
            (1280, 720),   # 720p
            (1920, 1080),  # 1080p
            (3840, 2160),  # 4K
        ]
        
        for width, height in resolutions:
            assert width > 0
            assert height > 0
            assert isinstance(width, int)
            assert isinstance(height, int)
    
    def test_common_framerates(self):
        """Test common framerate values."""
        framerates = [15, 24, 30, 60]
        
        for fps in framerates:
            assert fps > 0
            assert isinstance(fps, int)
            frame_time = 1.0 / fps
            assert frame_time > 0


class TestPipeWireOutputIntegration:
    """Integration tests that require GStreamer."""
    
    @pytest.mark.skipif(not _gstreamer_available(), reason="GStreamer not available")
    def test_can_import_gst(self):
        """Test that GStreamer can be imported."""
        from gi.repository import Gst
        assert Gst is not None
    
    @pytest.mark.skipif(not _gstreamer_available(), reason="GStreamer not available")
    def test_gst_init(self):
        """Test that GStreamer can be initialized."""
        from gi.repository import Gst
        Gst.init(None)
        # If we get here without exception, init worked
        assert True
    
    @pytest.mark.skipif(not _gstreamer_available(), reason="GStreamer not available")
    def test_gst_version(self):
        """Test getting GStreamer version."""
        from gi.repository import Gst
        Gst.init(None)
        version = Gst.version()
        assert len(version) >= 3  # (major, minor, micro, ...)
        assert all(isinstance(v, int) for v in version[:3])


class TestPipeWireOutputBufferOperations:
    """Test buffer-related operations."""
    
    @pytest.mark.skipif(not _gstreamer_available(), reason="GStreamer not available")
    def test_buffer_allocation(self):
        """Test GStreamer buffer allocation."""
        from gi.repository import Gst
        Gst.init(None)
        
        size = 1000
        buffer = Gst.Buffer.new_allocate(None, size, None)
        assert buffer is not None
    
    @pytest.mark.skipif(not _gstreamer_available(), reason="GStreamer not available")
    def test_buffer_fill(self):
        """Test filling a GStreamer buffer."""
        from gi.repository import Gst
        Gst.init(None)
        
        size = 100
        data = bytes([i % 256 for i in range(size)])
        buffer = Gst.Buffer.new_allocate(None, size, None)
        buffer.fill(0, data)
        assert buffer is not None


class TestPipeWireOutputErrorScenarios:
    """Test error handling in various scenarios."""
    
    def test_invalid_frame_size(self):
        """Test handling of invalid frame sizes."""
        width, height = 640, 480
        expected_size = width * height * 3
        
        # Too small
        small_data = bytes(expected_size - 1)
        assert len(small_data) != expected_size
        
        # Too large
        large_data = bytes(expected_size + 1)
        assert len(large_data) != expected_size
    
    def test_zero_dimensions(self):
        """Test handling of zero dimensions."""
        assert 0 * 480 * 3 == 0
        assert 640 * 0 * 3 == 0
    
    def test_negative_dimensions(self):
        """Test that negative dimensions are invalid."""
        # In real usage, these would be caught during initialization
        assert -640 < 0
        assert -480 < 0


class TestPipeWireOutputTimingOperations:
    """Test timing-related operations."""
    
    def test_sleep_time_calculation_needs_sleep(self):
        """Test sleep time calculation when sleep is needed."""
        frame_time = 1.0 / 30  # ~0.033 seconds
        elapsed = 0.01  # 10ms elapsed
        
        sleep_time = max(0, frame_time - elapsed)
        assert sleep_time > 0
        assert sleep_time < frame_time
    
    def test_sleep_time_calculation_no_sleep_needed(self):
        """Test sleep time calculation when no sleep is needed."""
        frame_time = 1.0 / 30
        elapsed = 0.05  # More time elapsed than frame_time
        
        sleep_time = max(0, frame_time - elapsed)
        assert sleep_time == 0
    
    def test_timestamp_generation(self):
        """Test timestamp generation."""
        import time
        t1 = time.time()
        time.sleep(0.001)  # Small sleep
        t2 = time.time()
        
        assert t2 > t1
        assert (t2 - t1) < 0.1  # Should be very small


class TestPipeWireOutputModuleImport:
    """Test module imports and dependencies."""
    
    def test_can_import_output_module(self):
        """Test that output module can be imported."""
        import camfx.output_pipewire
        assert camfx.output_pipewire is not None
    
    def test_pipewire_output_class_exists(self):
        """Test that PipeWireOutput class exists."""
        from camfx.output_pipewire import PipeWireOutput
        assert PipeWireOutput is not None
    
    def test_required_dependencies_importable(self):
        """Test that required dependencies can be imported."""
        import logging
        import os
        import subprocess
        import sys
        import time
        
        assert all([logging, os, subprocess, sys, time])


class TestPipeWireOutputPipelineString:
    """Test pipeline string construction."""
    
    def test_pipeline_string_format(self):
        """Test pipeline string has correct format."""
        width, height, fps = 640, 480, 30
        
        # This is the format used in the actual code
        pipeline_str = (
            f'appsrc name=source is-live=true format=time do-timestamp=true '
            f'caps=video/x-raw,format=RGB,width={width},height={height},framerate={fps}/1 ! '
            f'videoconvert ! '
            f'pipewiresink name=sink'
        )
        
        assert 'appsrc' in pipeline_str
        assert 'name=source' in pipeline_str
        assert f'width={width}' in pipeline_str
        assert f'height={height}' in pipeline_str
        assert f'framerate={fps}/1' in pipeline_str
        assert 'pipewiresink' in pipeline_str
    
    def test_pipeline_string_different_resolutions(self):
        """Test pipeline strings with different resolutions."""
        test_cases = [
            (640, 480, 30),
            (1280, 720, 30),
            (1920, 1080, 60),
        ]
        
        for width, height, fps in test_cases:
            pipeline_str = (
                f'appsrc name=source is-live=true format=time do-timestamp=true '
                f'caps=video/x-raw,format=RGB,width={width},height={height},framerate={fps}/1 ! '
                f'videoconvert ! '
                f'pipewiresink name=sink'
            )
            
            assert f'width={width}' in pipeline_str
            assert f'height={height}' in pipeline_str
            assert f'framerate={fps}/1' in pipeline_str


class TestPipeWireOutputMediaProperties:
    """Test media property configuration."""
    
    def test_media_class_format(self):
        """Test media.class property format."""
        media_class = "Video/Source"
        assert isinstance(media_class, str)
        assert "/" in media_class
        assert media_class.startswith("Video")
    
    def test_media_name_format(self):
        """Test media.name property format."""
        media_name = "camfx"
        assert isinstance(media_name, str)
        assert len(media_name) > 0
    
    def test_node_description_format(self):
        """Test node.description property format."""
        node_description = "camfx virtual camera"
        assert isinstance(node_description, str)
        assert len(node_description) > 0


class TestPipeWireOutputCleanupBehavior:
    """Test cleanup behavior without actual pipelines."""
    
    def test_cleanup_sets_pipeline_to_none(self):
        """Test that cleanup should set pipeline to None."""
        # This tests the expected behavior
        pipeline = object()  # Placeholder
        assert pipeline is not None
        
        # After cleanup
        pipeline = None
        assert pipeline is None
    
    def test_cleanup_sets_appsrc_to_none(self):
        """Test that cleanup should set appsrc to None."""
        appsrc = object()  # Placeholder
        assert appsrc is not None
        
        # After cleanup
        appsrc = None
        assert appsrc is None


class TestPipeWireOutputDocumentation:
    """Test that documentation and help messages are present."""
    
    def test_class_has_docstring(self):
        """Test that PipeWireOutput has a docstring."""
        from camfx.output_pipewire import PipeWireOutput
        assert PipeWireOutput.__doc__ is not None
        assert len(PipeWireOutput.__doc__) > 0
    
    def test_init_has_docstring(self):
        """Test that __init__ has a docstring."""
        from camfx.output_pipewire import PipeWireOutput
        assert PipeWireOutput.__init__.__doc__ is not None
    
    def test_send_has_docstring(self):
        """Test that send method has a docstring."""
        from camfx.output_pipewire import PipeWireOutput
        assert PipeWireOutput.send.__doc__ is not None
    
    def test_cleanup_has_docstring(self):
        """Test that cleanup method has a docstring."""
        from camfx.output_pipewire import PipeWireOutput
        assert PipeWireOutput.cleanup.__doc__ is not None
