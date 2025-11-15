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
	gi.require_version('GstApp', '1.0')
	from gi.repository import Gst, GstApp
	GSTREAMER_AVAILABLE = True
except (ImportError, ValueError):
	GSTREAMER_AVAILABLE = False
	GstApp = None


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
		self.sample_available = threading.Event()  # Signal when new sample is available
		
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
		
		# Create pipeline using string (simpler and often more reliable)
		# pipewiresrc -> videoconvert -> appsink with BGR format
		pipeline_str = (
			f'pipewiresrc path={source_id} do-timestamp=true ! '
			f'videoconvert ! '
			f'video/x-raw,format=BGR ! '
			f'appsink name=sink sync=false max-buffers=2 drop=true emit-signals=true'
		)
		
		self.pipeline = Gst.parse_launch(pipeline_str)
		if self.pipeline is None:
			raise RuntimeError("Failed to parse GStreamer pipeline")
		
		# Get appsink and connect signal
		appsink_element = self.pipeline.get_by_name('sink')
		if appsink_element is None:
			raise RuntimeError("Failed to get appsink element")
		
		self.appsink = appsink_element
		
		# Connect to new-sample signal
		self.appsink.connect('new-sample', self._on_new_sample)
		
		# Set up message bus to catch errors
		bus = self.pipeline.get_bus()
		bus.add_signal_watch()
		bus.connect('message', self._on_bus_message)
		
		# Start pipeline
		ret = self.pipeline.set_state(Gst.State.PLAYING)
		if ret == Gst.StateChangeReturn.FAILURE:
			raise RuntimeError("Failed to start GStreamer pipeline")
		
		# Wait for pipeline to transition to PLAYING (with longer timeout)
		# The pipeline will go: NULL -> READY -> PAUSED -> PLAYING
		# It might stay in PAUSED if waiting for preroll (first frame)
		max_wait = 10  # seconds
		start_time = time.time()
		state = Gst.State.NULL
		
		while time.time() - start_time < max_wait:
			ret = self.pipeline.get_state(Gst.SECOND)
			if ret[0] == Gst.StateChangeReturn.FAILURE:
				raise RuntimeError("Failed to start GStreamer pipeline")
			
			state = ret[1]
			state_name = {Gst.State.VOID_PENDING: "VOID_PENDING", 
			              Gst.State.NULL: "NULL",
			              Gst.State.READY: "READY",
			              Gst.State.PAUSED: "PAUSED",
			              Gst.State.PLAYING: "PLAYING"}.get(state, f"UNKNOWN({state})")
			
			if state == Gst.State.PLAYING:
				break
			elif state == Gst.State.PAUSED:
				# Check if we're waiting for preroll or if there's an issue
				pending = ret[0]
				if pending == Gst.StateChangeReturn.ASYNC:
					# Still transitioning, wait a bit more
					time.sleep(0.1)
					continue
				else:
					# Check for errors on bus
					msg = bus.pop_filtered(Gst.MessageType.ERROR | Gst.MessageType.WARNING)
					if msg:
							if msg.type == Gst.MessageType.ERROR:
								err, debug = msg.parse_error()
								raise RuntimeError(f"Pipeline error: {err.message}")
					# If no error, might be waiting for preroll - this is OK
					break
		
		# Even if in PAUSED, we can still try to read frames
		# Some sources will transition to PLAYING once data starts flowing
		self.running = True
		
		# Wait a bit for first frame
		time.sleep(0.5)
		
	
	def _on_bus_message(self, bus, message):
		"""Handle bus messages from the pipeline."""
		# Silently handle bus messages - errors are raised as exceptions
		pass
	
	def _on_new_sample(self, appsink) -> int:
		"""Callback for new-sample signal from AppSink.
		
		Returns:
			Gst.FlowReturn.OK to continue, Gst.FlowReturn.EOS to stop
		"""
		# Pull the sample
		try:
			sample = appsink.emit('pull-sample')
			if not sample:
				return Gst.FlowReturn.EOS
		except Exception as e:
			return Gst.FlowReturn.ERROR
		
		# Process sample in a thread-safe way
		with self.lock:
			try:
				buffer = sample.get_buffer()
				if not buffer:
					return Gst.FlowReturn.OK
				
				# Get frame data
				success, map_info = buffer.map(Gst.MapFlags.READ)
				if not success:
					return Gst.FlowReturn.OK
				
				try:
					# Get caps to determine frame dimensions
					caps = sample.get_caps()
					if not caps:
						return Gst.FlowReturn.OK
					
					structure = caps.get_structure(0)
					if not structure:
						return Gst.FlowReturn.OK
					
					width = structure.get_int('width')[1]
					height = structure.get_int('height')[1]
					
					# Update dimensions if changed
					if self.width != width or self.height != height:
						self.width = width
						self.height = height
					
					# Create numpy array from buffer data
					frame_size = width * height * 3
					if map_info.size < frame_size:
						return Gst.FlowReturn.OK
					
					frame_data = map_info.data[:frame_size]
					frame = np.frombuffer(frame_data, dtype=np.uint8).reshape((height, width, 3))
					
					# Store frame in queue (keep latest)
					self.frame_queue.append(frame.copy())
					self.sample_available.set()
					
				finally:
					buffer.unmap(map_info)
			except Exception:
				pass
		
		return Gst.FlowReturn.OK
	
	def read(self) -> tuple[bool, Optional[np.ndarray]]:
		"""Read a frame from PipeWire source.
		
		Returns:
			Tuple of (success, frame) where frame is BGR format numpy array
		"""
		if not self.running or self.appsink is None:
			return False, None
		
		# Check if we have frames in the queue (from signal callback)
		with self.lock:
			if self.frame_queue:
				frame = self.frame_queue[-1]  # Get latest frame
				return True, frame.copy()
		
		# If no frames in queue and pipeline might be in PAUSED,
		# try to manually pull a sample (this might work even in PAUSED)
		try:
			# Try to emit pull-sample signal manually
			sample = self.appsink.emit('pull-sample')
			if sample:
				# Process the sample
				buffer = sample.get_buffer()
				if buffer:
					success, map_info = buffer.map(Gst.MapFlags.READ)
					if success:
						try:
							caps = sample.get_caps()
							if caps:
								structure = caps.get_structure(0)
								if structure:
									width = structure.get_int('width')[1]
									height = structure.get_int('height')[1]
									frame_size = width * height * 3
									if map_info.size >= frame_size:
										frame_data = map_info.data[:frame_size]
										frame = np.frombuffer(frame_data, dtype=np.uint8).reshape((height, width, 3))
										# Store in queue for next time
										with self.lock:
											self.frame_queue.append(frame.copy())
										return True, frame.copy()
						finally:
							buffer.unmap(map_info)
		except Exception as e:
			# Ignore errors from manual pull
			pass
		
		# No frame available
		return False, None
	
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
