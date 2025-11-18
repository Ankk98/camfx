"""Tests for PipeWire input functionality."""

import json
import subprocess
import threading
import time
from unittest.mock import Mock, MagicMock, patch, call
import numpy as np
import pytest

from camfx.input_pipewire import (
    _find_pipewire_source_id,
    PipeWireInput,
    PipeWireSourceInfo,
    GSTREAMER_AVAILABLE
)


def _make_source_info(node_id=42, name="camfx"):
    """Helper to construct PipeWireSourceInfo for tests."""
    return PipeWireSourceInfo(
        id=node_id,
        media_name=name,
        node_name=name,
        node_description=f"{name}-description",
        object_path=f"node/{node_id}",
        object_serial=str(node_id),
    )


class TestFindPipewireSourceId:
    """Test _find_pipewire_source_id helper function."""
    
    def test_find_source_success(self):
        """Test finding a valid PipeWire source."""
        mock_data = [
            {
                "id": 42,
                "type": "PipeWire:Interface:Node",
                "info": {
                    "props": {
                        "media.class": "Video/Source",
                        "media.name": "camfx"
                    }
                }
            }
        ]
        
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout=json.dumps(mock_data)
            )
            
            result = _find_pipewire_source_id("camfx")
            assert result == 42
            mock_run.assert_called_once()
    
    def test_find_source_not_found(self):
        """Test when source doesn't exist."""
        mock_data = [
            {
                "id": 42,
                "type": "PipeWire:Interface:Node",
                "info": {
                    "props": {
                        "media.class": "Video/Source",
                        "media.name": "other_source"
                    }
                }
            }
        ]
        
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout=json.dumps(mock_data)
            )
            
            result = _find_pipewire_source_id("camfx")
            assert result is None
    
    def test_find_source_empty_output(self):
        """Test when pw-dump returns empty list."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout="[]"
            )
            
            result = _find_pipewire_source_id("camfx")
            assert result is None
    
    def test_find_source_pw_dump_failure(self):
        """Test when pw-dump command fails."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                returncode=1,
                stdout=""
            )
            
            result = _find_pipewire_source_id("camfx")
            assert result is None
    
    def test_find_source_timeout(self):
        """Test when pw-dump times out."""
        with patch('subprocess.run') as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired('pw-dump', 5)
            
            result = _find_pipewire_source_id("camfx")
            assert result is None
    
    def test_find_source_json_parse_error(self):
        """Test when pw-dump returns invalid JSON."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout="invalid json {{"
            )
            
            result = _find_pipewire_source_id("camfx")
            assert result is None
    
    def test_find_source_no_video_sources(self):
        """Test when no Video/Source nodes exist."""
        mock_data = [
            {
                "id": 42,
                "type": "PipeWire:Interface:Node",
                "info": {
                    "props": {
                        "media.class": "Audio/Source",
                        "media.name": "audio_source"
                    }
                }
            }
        ]
        
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout=json.dumps(mock_data)
            )
            
            result = _find_pipewire_source_id("camfx")
            assert result is None
    
    def test_find_source_missing_props(self):
        """Test when node has missing properties."""
        mock_data = [
            {
                "id": 42,
                "type": "PipeWire:Interface:Node",
                "info": {}
            }
        ]
        
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout=json.dumps(mock_data)
            )
            
            result = _find_pipewire_source_id("camfx")
            assert result is None
    
    def test_find_source_unexpected_exception(self):
        """Test handling of unexpected exceptions."""
        with patch('subprocess.run') as mock_run:
            mock_run.side_effect = Exception("Unexpected error")
            
            result = _find_pipewire_source_id("camfx")
            assert result is None


@pytest.mark.skipif(not GSTREAMER_AVAILABLE, reason="GStreamer not available")
class TestPipeWireInputInit:
    """Test PipeWireInput initialization."""
    
    def test_init_gstreamer_not_available(self):
        """Test initialization when GStreamer is not available."""
        with patch('camfx.input_pipewire.GSTREAMER_AVAILABLE', False):
            with pytest.raises(RuntimeError, match="GStreamer Python bindings not available"):
                PipeWireInput("test_source")
    
    def test_init_source_not_found(self):
        """Test initialization when PipeWire source doesn't exist."""
        with patch('camfx.input_pipewire._find_pipewire_source', return_value=None):
            with pytest.raises(RuntimeError, match="PipeWire source .* not found"):
                PipeWireInput("nonexistent")
    
    def test_init_with_custom_source_name(self):
        """Test initialization with custom source name."""
        with patch('camfx.input_pipewire._find_pipewire_source', return_value=_make_source_info()):
            with patch('camfx.input_pipewire.Gst'):
                with patch.object(PipeWireInput, '_setup_pipeline'):
                    input_obj = PipeWireInput("custom_source")
                    assert input_obj.source_name == "custom_source"
    
    def test_init_default_source_name(self):
        """Test initialization with default source name."""
        with patch('camfx.input_pipewire._find_pipewire_source', return_value=_make_source_info()):
            with patch('camfx.input_pipewire.Gst'):
                with patch.object(PipeWireInput, '_setup_pipeline'):
                    input_obj = PipeWireInput()
                    assert input_obj.source_name == "camfx"


@pytest.mark.skipif(not GSTREAMER_AVAILABLE, reason="GStreamer not available")
class TestPipeWireInputPipeline:
    """Test PipeWireInput pipeline setup and operation."""
    
    def test_setup_pipeline_creates_elements(self):
        """Test that pipeline setup creates necessary elements."""
        with patch('camfx.input_pipewire._find_pipewire_source', return_value=_make_source_info()):
            mock_gst = MagicMock()
            mock_pipeline = MagicMock()
            mock_appsink = MagicMock()
            mock_pwsrc = MagicMock()
            
            mock_gst.parse_launch.return_value = mock_pipeline
            def get_by_name(name):
                return mock_pwsrc if name == 'pwsrc' else (mock_appsink if name == 'sink' else None)
            mock_pipeline.get_by_name.side_effect = get_by_name
            mock_pipeline.set_state.return_value = mock_gst.StateChangeReturn.SUCCESS
            mock_pipeline.get_state.return_value = (
                mock_gst.StateChangeReturn.SUCCESS,
                mock_gst.State.PLAYING,
                mock_gst.State.VOID_PENDING
            )
            
            with patch('camfx.input_pipewire.Gst', mock_gst):
                input_obj = PipeWireInput("test")
                
                assert input_obj.pipeline is not None
                assert input_obj.appsink is not None
                assert input_obj.running is True
    
    def test_setup_pipeline_parse_failure(self):
        """Test handling of pipeline parse failure."""
        with patch('camfx.input_pipewire._find_pipewire_source', return_value=_make_source_info()):
            mock_gst = MagicMock()
            mock_gst.parse_launch.return_value = None
            
            with patch('camfx.input_pipewire.Gst', mock_gst):
                with pytest.raises(RuntimeError, match="Failed to parse GStreamer pipeline"):
                    PipeWireInput("test")
    
    def test_setup_pipeline_appsink_not_found(self):
        """Test handling when appsink element is not found."""
        with patch('camfx.input_pipewire._find_pipewire_source', return_value=_make_source_info()):
            mock_gst = MagicMock()
            mock_pipeline = MagicMock()
            mock_pwsrc = MagicMock()
            
            mock_gst.parse_launch.return_value = mock_pipeline
            mock_pipeline.get_by_name.side_effect = lambda name: mock_pwsrc if name == 'pwsrc' else None
            
            with patch('camfx.input_pipewire.Gst', mock_gst):
                with pytest.raises(RuntimeError, match="Failed to get appsink element"):
                    PipeWireInput("test")
    
    def test_setup_pipeline_state_change_failure(self):
        """Test handling of pipeline state change failure."""
        with patch('camfx.input_pipewire._find_pipewire_source', return_value=_make_source_info()):
            mock_gst = MagicMock()
            mock_pipeline = MagicMock()
            mock_appsink = MagicMock()
            mock_pwsrc = MagicMock()
            
            mock_gst.parse_launch.return_value = mock_pipeline
            mock_pipeline.get_by_name.side_effect = lambda name: mock_pwsrc if name == 'pwsrc' else (mock_appsink if name == 'sink' else None)
            mock_pipeline.set_state.return_value = mock_gst.StateChangeReturn.FAILURE
            
            with patch('camfx.input_pipewire.Gst', mock_gst):
                with pytest.raises(RuntimeError, match="Failed to start GStreamer pipeline"):
                    PipeWireInput("test")


@pytest.mark.skipif(not GSTREAMER_AVAILABLE, reason="GStreamer not available")
class TestPipeWireInputRead:
    """Test PipeWireInput frame reading."""
    
    def create_mock_input(self):
        """Create a mock PipeWireInput for testing."""
        with patch('camfx.input_pipewire._find_pipewire_source', return_value=_make_source_info()):
            mock_gst = MagicMock()
            mock_pipeline = MagicMock()
            mock_appsink = MagicMock()
            mock_pwsrc = MagicMock()
            
            mock_gst.parse_launch.return_value = mock_pipeline
            mock_pipeline.get_by_name.side_effect = lambda name: mock_pwsrc if name == 'pwsrc' else (mock_appsink if name == 'sink' else None)
            mock_pipeline.set_state.return_value = mock_gst.StateChangeReturn.SUCCESS
            mock_pipeline.get_state.return_value = (
                mock_gst.StateChangeReturn.SUCCESS,
                mock_gst.State.PLAYING,
                mock_gst.State.VOID_PENDING
            )
            
            with patch('camfx.input_pipewire.Gst', mock_gst):
                with patch('time.sleep'):  # Speed up tests
                    return PipeWireInput("test")
    
    def test_read_from_queue(self):
        """Test reading frame from queue."""
        input_obj = self.create_mock_input()
        
        # Add a test frame to the queue
        test_frame = np.ones((100, 100, 3), dtype=np.uint8) * 128
        input_obj.frame_queue.append(test_frame)
        
        success, frame = input_obj.read()
        assert success is True
        assert frame is not None
        assert frame.shape == (100, 100, 3)
        np.testing.assert_array_equal(frame, test_frame)
    
    def test_read_empty_queue(self):
        """Test reading when queue is empty."""
        input_obj = self.create_mock_input()
        
        # Mock the manual pull-sample to return None
        input_obj.appsink.emit = MagicMock(return_value=None)
        
        success, frame = input_obj.read()
        assert success is False
        assert frame is None
    
    def test_read_not_running(self):
        """Test reading when input is not running."""
        input_obj = self.create_mock_input()
        input_obj.running = False
        
        success, frame = input_obj.read()
        assert success is False
        assert frame is None
    
    def test_read_no_appsink(self):
        """Test reading when appsink is None."""
        input_obj = self.create_mock_input()
        input_obj.appsink = None
        
        success, frame = input_obj.read()
        assert success is False
        assert frame is None
    
    def test_read_thread_safety(self):
        """Test that reading is thread-safe."""
        input_obj = self.create_mock_input()
        test_frame = np.ones((100, 100, 3), dtype=np.uint8) * 128
        
        results = []
        errors = []
        
        def reader_thread():
            try:
                # Add frame and read it multiple times
                input_obj.frame_queue.append(test_frame)
                for _ in range(10):
                    success, frame = input_obj.read()
                    results.append((success, frame is not None))
                    time.sleep(0.001)
            except Exception as e:
                errors.append(e)
        
        threads = [threading.Thread(target=reader_thread) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        assert len(errors) == 0
        assert len(results) > 0


@pytest.mark.skipif(not GSTREAMER_AVAILABLE, reason="GStreamer not available")
class TestPipeWireInputCallbacks:
    """Test PipeWireInput callback handlers."""
    
    def create_mock_input(self):
        """Create a mock PipeWireInput for testing."""
        with patch('camfx.input_pipewire._find_pipewire_source', return_value=_make_source_info()):
            mock_gst = MagicMock()
            mock_pipeline = MagicMock()
            mock_appsink = MagicMock()
            mock_pwsrc = MagicMock()
            
            mock_gst.parse_launch.return_value = mock_pipeline
            mock_pipeline.get_by_name.side_effect = lambda name: mock_pwsrc if name == 'pwsrc' else (mock_appsink if name == 'sink' else None)
            mock_pipeline.set_state.return_value = mock_gst.StateChangeReturn.SUCCESS
            mock_pipeline.get_state.return_value = (
                mock_gst.StateChangeReturn.SUCCESS,
                mock_gst.State.PLAYING,
                mock_gst.State.VOID_PENDING
            )
            
            with patch('camfx.input_pipewire.Gst', mock_gst):
                with patch('time.sleep'):
                    return PipeWireInput("test"), mock_gst
    
    def test_on_bus_message_error(self):
        """Test bus message handler for errors."""
        input_obj, mock_gst = self.create_mock_input()
        
        mock_message = MagicMock()
        mock_message.type = mock_gst.MessageType.ERROR
        mock_error = MagicMock()
        mock_error.message = "Test error"
        mock_message.parse_error.return_value = (mock_error, "debug info")
        
        # Should not raise, just log
        input_obj._on_bus_message(None, mock_message)
    
    def test_on_bus_message_warning(self):
        """Test bus message handler for warnings."""
        input_obj, mock_gst = self.create_mock_input()
        
        mock_message = MagicMock()
        mock_message.type = mock_gst.MessageType.WARNING
        mock_warning = MagicMock()
        mock_warning.message = "Test warning"
        mock_message.parse_warning.return_value = (mock_warning, "debug info")
        
        # Should not raise, just log
        input_obj._on_bus_message(None, mock_message)
    
    def test_on_bus_message_eos(self):
        """Test bus message handler for end of stream."""
        input_obj, mock_gst = self.create_mock_input()
        
        mock_message = MagicMock()
        mock_message.type = mock_gst.MessageType.EOS
        
        # Should not raise, just log
        input_obj._on_bus_message(None, mock_message)
    
    def test_on_new_sample_no_sample(self):
        """Test new sample callback when sample is None."""
        input_obj, mock_gst = self.create_mock_input()
        
        mock_appsink = MagicMock()
        mock_appsink.emit.return_value = None
        
        result = input_obj._on_new_sample(mock_appsink)
        # Import actual Gst to compare with real FlowReturn values
        from gi.repository import Gst as RealGst
        assert result == RealGst.FlowReturn.EOS
    
    def test_on_new_sample_no_buffer(self):
        """Test new sample callback when buffer is None."""
        input_obj, mock_gst = self.create_mock_input()
        
        mock_sample = MagicMock()
        mock_sample.get_buffer.return_value = None
        mock_appsink = MagicMock()
        mock_appsink.emit.return_value = mock_sample
        
        result = input_obj._on_new_sample(mock_appsink)
        # Import actual Gst to compare with real FlowReturn values
        from gi.repository import Gst as RealGst
        assert result == RealGst.FlowReturn.OK
    
    def test_on_new_sample_exception(self):
        """Test new sample callback exception handling."""
        input_obj, mock_gst = self.create_mock_input()
        
        mock_appsink = MagicMock()
        mock_appsink.emit.side_effect = Exception("Test error")
        
        result = input_obj._on_new_sample(mock_appsink)
        # Import actual Gst to compare with real FlowReturn values
        from gi.repository import Gst as RealGst
        assert result == RealGst.FlowReturn.ERROR


@pytest.mark.skipif(not GSTREAMER_AVAILABLE, reason="GStreamer not available")
class TestPipeWireInputCleanup:
    """Test PipeWireInput resource cleanup."""
    
    def create_mock_input(self):
        """Create a mock PipeWireInput for testing."""
        with patch('camfx.input_pipewire._find_pipewire_source', return_value=_make_source_info()):
            mock_gst = MagicMock()
            mock_pipeline = MagicMock()
            mock_appsink = MagicMock()
            mock_pwsrc = MagicMock()
            
            mock_gst.parse_launch.return_value = mock_pipeline
            mock_pipeline.get_by_name.side_effect = lambda name: mock_pwsrc if name == 'pwsrc' else (mock_appsink if name == 'sink' else None)
            mock_pipeline.set_state.return_value = mock_gst.StateChangeReturn.SUCCESS
            mock_pipeline.get_state.return_value = (
                mock_gst.StateChangeReturn.SUCCESS,
                mock_gst.State.PLAYING,
                mock_gst.State.VOID_PENDING
            )
            
            with patch('camfx.input_pipewire.Gst', mock_gst):
                with patch('time.sleep'):
                    return PipeWireInput("test"), mock_gst
    
    def test_release(self):
        """Test releasing resources."""
        input_obj, mock_gst = self.create_mock_input()
        
        assert input_obj.running is True
        assert input_obj.pipeline is not None
        
        input_obj.release()
        
        assert input_obj.running is False
        assert input_obj.pipeline is None
        assert input_obj.appsink is None
    
    def test_release_idempotent(self):
        """Test that release can be called multiple times safely."""
        input_obj, _ = self.create_mock_input()
        
        input_obj.release()
        input_obj.release()  # Should not raise
        
        assert input_obj.running is False
        assert input_obj.pipeline is None
    
    def test_isOpened_when_running(self):
        """Test isOpened returns True when running."""
        input_obj, mock_gst = self.create_mock_input()
        
        # Import actual Gst to use real State enum values
        from gi.repository import Gst as RealGst
        input_obj.pipeline.get_state.return_value = (
            RealGst.StateChangeReturn.SUCCESS,
            RealGst.State.PLAYING,
            RealGst.State.VOID_PENDING
        )
        
        assert input_obj.isOpened() is True
    
    def test_isOpened_when_stopped(self):
        """Test isOpened returns False when stopped."""
        input_obj, _ = self.create_mock_input()
        
        input_obj.release()
        
        assert input_obj.isOpened() is False
    
    def test_isOpened_no_pipeline(self):
        """Test isOpened returns False when pipeline is None."""
        input_obj, _ = self.create_mock_input()
        
        input_obj.pipeline = None
        
        assert input_obj.isOpened() is False


class TestPipeWireInputEdgeCases:
    """Test edge cases and error conditions."""
    
    def test_multiple_sources_with_same_media_class(self):
        """Test finding correct source among multiple Video/Source nodes."""
        mock_data = [
            {
                "id": 41,
                "type": "PipeWire:Interface:Node",
                "info": {
                    "props": {
                        "media.class": "Video/Source",
                        "media.name": "other_camera"
                    }
                }
            },
            {
                "id": 42,
                "type": "PipeWire:Interface:Node",
                "info": {
                    "props": {
                        "media.class": "Video/Source",
                        "media.name": "camfx"
                    }
                }
            },
            {
                "id": 43,
                "type": "PipeWire:Interface:Node",
                "info": {
                    "props": {
                        "media.class": "Video/Source",
                        "media.name": "another_camera"
                    }
                }
            }
        ]
        
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout=json.dumps(mock_data)
            )
            
            result = _find_pipewire_source_id("camfx")
            assert result == 42
    
    def test_frame_queue_maxlen(self):
        """Test that frame queue has maxlen of 2."""
        with patch('camfx.input_pipewire._find_pipewire_source', return_value=_make_source_info()):
            with patch('camfx.input_pipewire.Gst'):
                with patch.object(PipeWireInput, '_setup_pipeline'):
                    input_obj = PipeWireInput("test")
                    
                    assert input_obj.frame_queue.maxlen == 2
                    
                    # Add more than 2 frames
                    frame1 = np.ones((100, 100, 3), dtype=np.uint8) * 50
                    frame2 = np.ones((100, 100, 3), dtype=np.uint8) * 100
                    frame3 = np.ones((100, 100, 3), dtype=np.uint8) * 150
                    
                    input_obj.frame_queue.append(frame1)
                    input_obj.frame_queue.append(frame2)
                    input_obj.frame_queue.append(frame3)
                    
                    # Should only have 2 frames (latest)
                    assert len(input_obj.frame_queue) == 2
                    np.testing.assert_array_equal(input_obj.frame_queue[0], frame2)
                    np.testing.assert_array_equal(input_obj.frame_queue[1], frame3)

