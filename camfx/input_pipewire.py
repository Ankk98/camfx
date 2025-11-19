"""PipeWire virtual camera input using GStreamer."""

import json
import logging
import subprocess
import threading
import time
import numpy as np
from typing import Optional
from collections import deque
from dataclasses import dataclass

logger = logging.getLogger('camfx.input_pipewire')

try:
	import gi
	gi.require_version('Gst', '1.0')
	gi.require_version('GstApp', '1.0')
	from gi.repository import Gst, GstApp
	GSTREAMER_AVAILABLE = True
	logger.debug("GStreamer bindings available")
except (ImportError, ValueError) as e:
	GSTREAMER_AVAILABLE = False
	GstApp = None
	logger.warning(f"GStreamer bindings not available: {e}")


@dataclass
class PipeWireSourceInfo:
	id: int
	media_name: Optional[str]
	node_name: Optional[str]
	node_description: Optional[str]
	object_path: Optional[str]
	object_serial: Optional[str]


def _find_pipewire_source(source_name: str) -> Optional[PipeWireSourceInfo]:
	"""Locate PipeWire source metadata for the given name."""
	logger.debug(f"Searching for PipeWire source '{source_name}'")
	try:
		result = subprocess.run(
			['pw-dump'],
			capture_output=True,
			text=True,
			timeout=5
		)
		if result.returncode != 0:
			logger.error(f"pw-dump failed with return code {result.returncode}")
			return None
		
		data = json.loads(result.stdout)
		logger.debug(f"pw-dump returned {len(data)} objects")
		
		for obj in data:
			if obj.get('type') != 'PipeWire:Interface:Node':
				continue
			
			props = obj.get('info', {}).get('props', {}) or {}
			media_class = props.get('media.class')
			media_name = props.get('media.name')
			if media_class == 'Video/Source':
				logger.debug(f"Found Video/Source: '{media_name}' (id={obj.get('id')})")
			if media_class != 'Video/Source':
				continue
			if media_name != source_name:
				continue
			
			source_id = obj.get('id')
			if source_id is None:
				continue
			
			info = PipeWireSourceInfo(
				id=int(source_id),
				media_name=media_name,
				node_name=props.get('node.name'),
				node_description=props.get('node.description'),
				object_path=props.get('object.path'),
				object_serial=str(props.get('object.serial') or source_id)
			)
			logger.info(
				"Found PipeWire source '%s' with id=%s node_name=%s description=%s",
				source_name,
				info.id,
				info.node_name,
				info.node_description,
			)
			return info
		
		logger.warning(f"PipeWire source '{source_name}' not found in pw-dump output")
		return None
	except subprocess.TimeoutExpired:
		logger.error("pw-dump command timed out")
		return None
	except json.JSONDecodeError as e:
		logger.error(f"Failed to parse pw-dump JSON output: {e}")
		return None
	except Exception as e:
		logger.error(f"Exception in _find_pipewire_source: {e}", exc_info=True)
		return None


def _find_pipewire_source_id(source_name: str) -> Optional[int]:
	"""Backward-compatible helper that returns only the PipeWire node id."""
	info = _find_pipewire_source(source_name)
	return info.id if info else None


class PipeWireInput:
	"""Read from PipeWire virtual camera source using GStreamer."""
	
	def __init__(self, source_name: str = "camfx"):
		"""Initialize PipeWire input.
		
		Args:
			source_name: Name of the PipeWire source to read from
		"""
		if not GSTREAMER_AVAILABLE:
			logger.error("GStreamer Python bindings not available")
			raise RuntimeError("GStreamer Python bindings not available. Install PyGObject.")
		
		logger.info(f"Initializing PipeWireInput for source '{source_name}'")
		self.source_name = source_name
		self.pipeline: Optional[Gst.Pipeline] = None
		self.appsink: Optional[Gst.Element] = None
		self.pipewire_src: Optional[Gst.Element] = None
		self.source_info: Optional[PipeWireSourceInfo] = None
		self.width: Optional[int] = None
		self.height: Optional[int] = None
		self.frame_queue = deque(maxlen=2)  # Keep latest 2 frames
		self.running = False
		self.lock = threading.Lock()
		self.sample_available = threading.Event()  # Signal when new sample is available
		self._frames_received = 0
		self._last_sample_log = 0.0
		self._last_empty_log = 0.0
		
		Gst.init(None)
		self._setup_pipeline_with_retry()
	
	def _setup_pipeline_with_retry(self, max_attempts: int = 3, base_delay: float = 0.5):
		"""Attempt to set up the pipeline with retries on transient errors."""
		attempt = 0
		while True:
			try:
				self._setup_pipeline()
				return
			except RuntimeError as exc:
				attempt += 1
				if attempt >= max_attempts:
					logger.error("Failed to initialize PipeWireInput after %s attempts", attempt)
					raise
				delay = base_delay * attempt
				logger.warning(
					"PipeWireInput setup failed (%s). Retrying in %.1fs (attempt %s/%s)",
					exc,
					delay,
					attempt + 1,
					max_attempts,
				)
				self._teardown_pipeline()
				time.sleep(delay)
	
	def _setup_pipeline(self):
		"""Set up GStreamer pipeline to read from PipeWire source."""
		# Find PipeWire source metadata
		source_info = _find_pipewire_source(self.source_name)
		if source_info is None:
			logger.error(f"PipeWire source '{self.source_name}' not found")
			raise RuntimeError(
				f"PipeWire source '{self.source_name}' not found. "
				f"Make sure 'camfx start' is running."
			)
		self.source_info = source_info
		logger.info(
			"Setting up PipeWireInput for '%s' (node_id=%s, node_name=%s, path=%s)",
			self.source_name,
			source_info.id,
			source_info.node_name,
			source_info.object_path,
		)
		
		# Create pipeline using string (simpler and often more reliable)
		# pipewiresrc -> videoconvert -> appsink with BGR format
		pipeline_str = (
			'pipewiresrc name=pwsrc do-timestamp=true ! '
			'videoconvert ! '
			'video/x-raw,format=BGR ! '
			'appsink name=sink'
		)
		logger.debug("Input pipeline description: %s", pipeline_str)
		
		self.pipeline = Gst.parse_launch(pipeline_str)
		if self.pipeline is None:
			logger.error("Failed to parse GStreamer pipeline")
			raise RuntimeError("Failed to parse GStreamer pipeline")
		
		# Get pipewiresrc element for configuration
		pwsrc_element = self.pipeline.get_by_name('pwsrc')
		if pwsrc_element is None:
			logger.error("Failed to get pipewiresrc element from pipeline")
			raise RuntimeError("Failed to get pipewiresrc element")
		self.pipewire_src = pwsrc_element
		
		target_object = None
		target_reason = None
		
		if source_info.object_serial:
			target_object = str(source_info.object_serial)
			target_reason = "object_serial"
		elif source_info.node_name:
			target_object = source_info.node_name
			target_reason = "node_name"
		elif source_info.media_name:
			target_object = source_info.media_name
			target_reason = "media_name"
		elif self.source_name:
			target_object = self.source_name
			target_reason = "configured_source_name"
		elif source_info.id is not None:
			target_object = str(source_info.id)
			target_reason = "node_id"
		
		path_value = None
		if source_info.object_path:
			path_value = source_info.object_path
		elif source_info.id is not None:
			path_value = str(source_info.id)
		
		if target_object:
			self.pipewire_src.set_property('target-object', target_object)
		# Provide friendly client name when supported
		try:
			self.pipewire_src.set_property('client-name', 'camfx GUI Preview')
		except (TypeError, AttributeError):
			pass
		actual_target = self.pipewire_src.get_property('target-object')
		
		actual_path = None
		if path_value:
			self.pipewire_src.set_property('path', path_value)
			actual_path = self.pipewire_src.get_property('path')
		
		logger.info(
			"Configured pipewiresrc with target_object=%s reason=%s path=%s",
			actual_target,
			target_reason,
			actual_path,
		)
		
		# Get appsink and connect signal
		appsink_element = self.pipeline.get_by_name('sink')
		if appsink_element is None:
			logger.error("Failed to get appsink element from pipeline")
			raise RuntimeError("Failed to get appsink element")
		
		self.appsink = appsink_element
		
		# Configure appsink programmatically for better control
		# Set caps to specify expected format (helps with negotiation)
		caps_str = "video/x-raw,format=BGR"
		caps = Gst.Caps.from_string(caps_str)
		self.appsink.set_property('caps', caps)
		
		# Configure appsink for live source (don't wait for preroll)
		self.appsink.set_property('sync', False)
		self.appsink.set_property('max-buffers', 1)
		self.appsink.set_property('drop', True)
		self.appsink.set_property('emit-signals', True)
		
		# Connect to new-sample signal
		self.appsink.connect('new-sample', self._on_new_sample)
		
		# Set up message bus to catch errors
		bus = self.pipeline.get_bus()
		bus.add_signal_watch()
		bus.connect('message', self._on_bus_message)
		
		# Ensure pipeline is in NULL state before configuring and starting
		self.pipeline.set_state(Gst.State.NULL)
		
		# Start pipeline
		ret = self.pipeline.set_state(Gst.State.PLAYING)
		if ret == Gst.StateChangeReturn.FAILURE:
			logger.error("Failed to start GStreamer pipeline")
			raise RuntimeError("Failed to start GStreamer pipeline")
		logger.debug("Requested input pipeline PLAYING transition (ret=%s)", ret)
		
		# Wait for pipeline to transition to PLAYING
		max_wait = 10  # seconds
		start_time = time.time()
		
		while time.time() - start_time < max_wait:
			ret = self.pipeline.get_state(Gst.SECOND)
			if ret[0] == Gst.StateChangeReturn.FAILURE:
				logger.error("Pipeline state check returned FAILURE")
				raise RuntimeError("Failed to start GStreamer pipeline")
			
			state = ret[1]
			if state == Gst.State.PLAYING:
				break
			elif state == Gst.State.PAUSED:
				# Check for errors on bus
				pending = ret[0]
				if pending != Gst.StateChangeReturn.ASYNC:
					msg = bus.pop_filtered(Gst.MessageType.ERROR | Gst.MessageType.WARNING)
					if msg and msg.type == Gst.MessageType.ERROR:
						err, debug = msg.parse_error()
						logger.error(f"Pipeline error: {err.message} (debug: {debug})")
						raise RuntimeError(f"Pipeline error: {err.message}")
				# If no error, might be waiting for preroll - this is OK
				break
			time.sleep(0.1)
		
		# Even if in PAUSED, we can still try to read frames
		self.running = True
		time.sleep(0.5)  # Wait a bit for first frame
		logger.info("PipeWireInput pipeline started (source=%s)", self.source_name)
		
	
	def _on_bus_message(self, bus, message):
		"""Handle bus messages from the pipeline."""
		if message.type == Gst.MessageType.ERROR:
			err, debug = message.parse_error()
			logger.error(f"GStreamer bus error: {err.message} (debug: {debug})")
		elif message.type == Gst.MessageType.WARNING:
			warn, debug = message.parse_warning()
			logger.warning(f"GStreamer bus warning: {warn.message} (debug: {debug})")
		elif message.type == Gst.MessageType.EOS:
			logger.info("GStreamer pipeline reached end of stream")
	
	def _on_new_sample(self, appsink) -> int:
		"""Callback for new-sample signal from AppSink.
		
		Returns:
			Gst.FlowReturn.OK to continue, Gst.FlowReturn.EOS to stop
		"""
		# Pull the sample
		try:
			sample = appsink.emit('pull-sample')
			if not sample:
				logger.debug("pull-sample returned None")
				return Gst.FlowReturn.EOS
		except Exception as e:
			logger.error(f"Exception in pull-sample: {e}", exc_info=True)
			return Gst.FlowReturn.ERROR
		
		# Process sample in a thread-safe way
		with self.lock:
			try:
				buffer = sample.get_buffer()
				if not buffer:
					logger.debug("Sample has no buffer")
					return Gst.FlowReturn.OK
				
				# Get frame data
				success, map_info = buffer.map(Gst.MapFlags.READ)
				if not success:
					logger.warning("Failed to map buffer")
					return Gst.FlowReturn.OK
				
				try:
					# Get caps to determine frame dimensions
					caps = sample.get_caps()
					if not caps:
						logger.debug("Sample has no caps")
						return Gst.FlowReturn.OK
					
					structure = caps.get_structure(0)
					if not structure:
						logger.debug("Caps have no structure")
						return Gst.FlowReturn.OK
					
					width = structure.get_int('width')[1]
					height = structure.get_int('height')[1]
					
					# Update dimensions if changed
					if self.width != width or self.height != height:
						logger.info(f"Frame dimensions changed: {self.width}x{self.height} -> {width}x{height}")
						self.width = width
						self.height = height
					
					# Create numpy array from buffer data
					frame_size = width * height * 3
					if map_info.size < frame_size:
						logger.warning(f"Buffer size ({map_info.size}) < expected frame size ({frame_size})")
						return Gst.FlowReturn.OK
					
					frame_data = map_info.data[:frame_size]
					frame = np.frombuffer(frame_data, dtype=np.uint8).reshape((height, width, 3))
					
					# Store frame in queue (keep latest)
					self.frame_queue.append(frame.copy())
					self.sample_available.set()
					logger.debug(f"Frame queued: {width}x{height}")
					self._frames_received += 1
					now = time.time()
					if self._frames_received == 1 or now - self._last_sample_log >= 5.0:
						logger.debug(
							"Total frames received from '%s': %s (latest %sx%s)",
							self.source_name,
							self._frames_received,
							width,
							height,
						)
						self._last_sample_log = now
					
				finally:
					buffer.unmap(map_info)
			except Exception as e:
				logger.error(f"Exception processing sample: {e}", exc_info=True)
		
		return Gst.FlowReturn.OK
	
	def read(self) -> tuple[bool, Optional[np.ndarray]]:
		"""Read a frame from PipeWire source.
		
		Returns:
			Tuple of (success, frame) where frame is BGR format numpy array
		"""
		if not self.running or self.appsink is None:
			return False, None
		
		# Wait briefly for frame availability to avoid busy-polling
		if not self.frame_queue:
			self.sample_available.wait(timeout=0.05)
		
		now = time.time()
		
		# Check if we have frames in the queue (from signal callback)
		with self.lock:
			if self.frame_queue:
				frame = self.frame_queue.pop()  # Get latest frame and remove
				if not self.frame_queue:
					self.sample_available.clear()
				return True, frame.copy()
		
		# Try to manually pull a sample
		try:
			sample = self.appsink.emit('pull-sample')
			if sample:
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
											self.sample_available.set()
										return True, frame.copy()
						finally:
							buffer.unmap(map_info)
		except Exception:
			pass
		
		if now - self._last_empty_log >= 2.0:
			logger.debug(
				"No frames currently available from PipeWireInput (running=%s, appsink=%s)",
				self.running,
				self.appsink is not None,
			)
			self._last_empty_log = now
		return False, None
	
	def release(self):
		"""Release resources."""
		self.running = False
		logger.info("Releasing PipeWireInput resources (frames_received=%s)", self._frames_received)
		self._teardown_pipeline()
		self.sample_available.set()
	
	def _teardown_pipeline(self):
		"""Helper to shutdown and clear pipeline elements."""
		if self.pipeline:
			try:
				bus = self.pipeline.get_bus()
				if bus:
					bus.remove_signal_watch()
			except Exception:
				pass
			try:
				self.pipeline.set_state(Gst.State.NULL)
			except Exception:
				pass
		self.pipeline = None
		self.appsink = None
		self.pipewire_src = None
	
	def isOpened(self) -> bool:
		"""Check if input is opened."""
		return (self.pipeline is not None and 
		        self.pipeline.get_state(0)[1] == Gst.State.PLAYING and
		        self.running)
