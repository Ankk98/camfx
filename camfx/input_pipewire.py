"""PipeWire virtual camera input using GStreamer."""

import json
import subprocess
import threading
import time
import numpy as np
from typing import Optional
from collections import deque

try:
	import gi
	gi.require_version('Gst', '1.0')
	from gi.repository import Gst
	GSTREAMER_AVAILABLE = True
except (ImportError, ValueError):
	GSTREAMER_AVAILABLE = False


def _find_pipewire_source_id(source_name: str) -> Optional[int]:
	"""Find PipeWire source object ID by name.
	
	Args:
		source_name: Name of the PipeWire source
		
	Returns:
		Object ID if found, None otherwise
	"""
	try:
		result = subprocess.run(
			['pw-dump'],
			capture_output=True,
			text=True,
			timeout=5
		)
		if result.returncode != 0:
			return None
		
		data = json.loads(result.stdout)
		
		# Find source node with matching name
		for obj in data:
			if obj.get('type') == 'PipeWire:Interface:Node':
				props = obj.get('info', {}).get('props', {})
				if (props.get('media.class') == 'Video/Source' and
					props.get('media.name') == source_name):
					return obj.get('id')
		
		return None
	except Exception:
		return None


class PipeWireInput:
	"""Read from PipeWire virtual camera source using GStreamer."""
	
	def __init__(self, source_name: str = "camfx"):
		"""Initialize PipeWire input.
		
		Args:
			source_name: Name of the PipeWire source to read from
		"""
		if not GSTREAMER_AVAILABLE:
			raise RuntimeError("GStreamer Python bindings not available. Install PyGObject.")
		
		self.source_name = source_name
		self.pipeline: Optional[Gst.Pipeline] = None
		self.appsink: Optional[Gst.Element] = None
		self.width: Optional[int] = None
		self.height: Optional[int] = None
		self.frame_queue = deque(maxlen=2)  # Keep latest 2 frames
		self.running = False
		self.lock = threading.Lock()
		
		Gst.init(None)
		self._setup_pipeline()
	
	def _setup_pipeline(self):
		"""Set up GStreamer pipeline to read from PipeWire source."""
		# Find the PipeWire source object ID
		source_id = _find_pipewire_source_id(self.source_name)
		if source_id is None:
			raise RuntimeError(
				f"PipeWire source '{self.source_name}' not found. "
				f"Make sure 'camfx start' is running."
			)
		
		# Create pipeline: pipewiresrc -> videoconvert -> appsink
		# Use pull-mode appsink instead of signal-based to avoid threading issues
		pipeline_str = (
			f'pipewiresrc path={source_id} do-timestamp=true ! '
			f'videoconvert ! '
			f'video/x-raw,format=BGR ! '
			f'appsink name=sink sync=false max-buffers=2 drop=true'
		)
		
		self.pipeline = Gst.parse_launch(pipeline_str)
		if self.pipeline is None:
			raise RuntimeError("Failed to parse GStreamer pipeline")
		
		# Get appsink
		self.appsink = self.pipeline.get_by_name('sink')
		if self.appsink is None:
			raise RuntimeError("Failed to get appsink element")
		
		# Configure appsink for pull mode (no signals needed)
		self.appsink.set_property('sync', False)
		self.appsink.set_property('max-buffers', 2)
		self.appsink.set_property('drop', True)
		
		# Start pipeline
		ret = self.pipeline.set_state(Gst.State.PLAYING)
		if ret == Gst.StateChangeReturn.FAILURE:
			raise RuntimeError("Failed to start GStreamer pipeline")
		
		# Wait for pipeline to start
		ret = self.pipeline.get_state(Gst.SECOND * 2)
		if ret[0] == Gst.StateChangeReturn.FAILURE:
			raise RuntimeError("Failed to start GStreamer pipeline")
		
		self.running = True
		
		# Wait a bit for first frame
		time.sleep(0.5)
	
	def read(self) -> tuple[bool, Optional[np.ndarray]]:
		"""Read a frame from PipeWire source.
		
		Returns:
			Tuple of (success, frame) where frame is BGR format numpy array
		"""
		if not self.running or self.appsink is None:
			return False, None
		
		# Pull sample directly (non-blocking)
		sample = self.appsink.emit('pull-sample')
		if not sample:
			return False, None
		
		buffer = sample.get_buffer()
		if not buffer:
			return False, None
		
		# Get frame data
		success, map_info = buffer.map(Gst.MapFlags.READ)
		if not success:
			return False, None
		
		try:
			# Get caps to determine frame dimensions
			caps = sample.get_caps()
			if not caps:
				return False, None
			
			structure = caps.get_structure(0)
			if not structure:
				return False, None
			
			width = structure.get_int('width')[1]
			height = structure.get_int('height')[1]
			
			# Update dimensions if changed
			if self.width != width or self.height != height:
				self.width = width
				self.height = height
			
			# Create numpy array from buffer data
			frame_size = width * height * 3
			if map_info.size < frame_size:
				return False, None
			
			frame_data = map_info.data[:frame_size]
			frame = np.frombuffer(frame_data, dtype=np.uint8).reshape((height, width, 3))
			
			return True, frame.copy()
		
		finally:
			buffer.unmap(map_info)
	
	def release(self):
		"""Release resources."""
		self.running = False
		
		if self.pipeline:
			self.pipeline.set_state(Gst.State.NULL)
			self.pipeline = None
		
		self.appsink = None
	
	def isOpened(self) -> bool:
		"""Check if input is opened."""
		return (self.pipeline is not None and 
		        self.pipeline.get_state(0)[1] == Gst.State.PLAYING and
		        self.running)
