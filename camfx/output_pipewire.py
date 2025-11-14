"""PipeWire virtual camera output using GStreamer via PyGObject."""

import time
from typing import Optional

import gi

gi.require_version('Gst', '1.0')
from gi.repository import Gst


class PipeWireOutput:
	"""PipeWire virtual camera output using GStreamer's pipewiresink element."""

	def __init__(self, width: int, height: int, fps: int, name: str = "camfx") -> None:
		"""Initialize PipeWire output.

		Args:
			width: Frame width in pixels
			height: Frame height in pixels
			fps: Target frames per second
			name: Name for the virtual camera source

		Raises:
			RuntimeError: If GStreamer pipeline fails to start
		"""
		Gst.init(None)
		self.width = width
		self.height = height
		self.fps = fps
		self.name = name
		self.frame_time = 1.0 / fps
		self.pipeline: Optional[Gst.Pipeline] = None
		self.appsrc: Optional[Gst.Element] = None

		# Create GStreamer pipeline
		# pipewiresink needs media.class=Video/Source to create a virtual camera source
		pipeline_str = (
			f'appsrc name=source is-live=true format=time do-timestamp=true '
			f'caps=video/x-raw,format=RGB,width={width},height={height},framerate={fps}/1 ! '
			f'videoconvert ! '
			f'pipewiresink name=sink stream-properties="props,media.class=Video/Source,media.name={name},media.role=Camera"'
		)

		try:
			self.pipeline = Gst.parse_launch(pipeline_str)
			if self.pipeline is None:
				raise RuntimeError("Failed to parse GStreamer pipeline")

			self.appsrc = self.pipeline.get_by_name('source')
			if self.appsrc is None:
				raise RuntimeError("Failed to get appsrc element from pipeline")

			# Get message bus to capture errors
			bus = self.pipeline.get_bus()
			bus.add_signal_watch()
			
			# Start pipeline
			ret = self.pipeline.set_state(Gst.State.PLAYING)
			if ret == Gst.StateChangeReturn.FAILURE:
				error_msg = self._get_pipeline_error()
				raise RuntimeError(f"Failed to start GStreamer pipeline: {error_msg}")
			elif ret == Gst.StateChangeReturn.ASYNC:
				# Wait for state change to complete with a timeout (5 seconds)
				# Poll the bus for errors while waiting
				start_time = time.time()
				timeout_seconds = 5.0
				check_interval = 0.1  # Check every 100ms
				
				while True:
					# Check for errors on the bus (non-blocking)
					error_msg = self._check_bus_for_errors()
					if error_msg:
						raise RuntimeError(f"Failed to start GStreamer pipeline: {error_msg}")
					
					# Check state with a short timeout
					ret = self.pipeline.get_state(int(check_interval * Gst.SECOND))
					state = ret[0]
					
					if state == Gst.StateChangeReturn.FAILURE:
						error_msg = self._get_pipeline_error()
						raise RuntimeError(f"Failed to start GStreamer pipeline: {error_msg}")
					elif state == Gst.StateChangeReturn.SUCCESS:
						# State change completed successfully
						break
					
					# Check timeout
					elapsed = time.time() - start_time
					if elapsed > timeout_seconds:
						# Try one more time to get error message
						error_msg = self._check_bus_for_errors()
						if not error_msg:
							error_msg = "No error message available"
						raise RuntimeError(
							f"Timeout ({timeout_seconds}s) waiting for pipeline to start. "
							f"This may indicate PipeWire session manager (wireplumber) is not running. "
							f"Try: systemctl --user start wireplumber\n"
							f"Error: {error_msg}"
						)
					
					# Small sleep to avoid busy-waiting
					time.sleep(check_interval)

		except Exception as exc:
			self.cleanup()
			raise RuntimeError(
				f"Failed to initialize PipeWire output. Ensure PipeWire and GStreamer are installed. "
				f"Original error: {exc}"
			) from exc

		self.last_frame_time = time.time()

	def send(self, frame_rgb: bytes) -> None:
		"""Send RGB frame data to PipeWire.

		Args:
			frame_rgb: RGB frame data as bytes (width * height * 3 bytes)

		Raises:
			RuntimeError: If buffer push fails
		"""
		if self.appsrc is None or self.pipeline is None:
			raise RuntimeError("PipeWire output not initialized")

		size = len(frame_rgb)
		expected_size = self.width * self.height * 3
		if size != expected_size:
			raise ValueError(
				f"Frame size mismatch: expected {expected_size} bytes, got {size}"
			)

		# Create GStreamer buffer
		buffer = Gst.Buffer.new_allocate(None, size, None)
		if buffer is None:
			raise RuntimeError("Failed to allocate GStreamer buffer")

		buffer.fill(0, frame_rgb)
		buffer.pts = Gst.util_get_timestamp()
		buffer.duration = int(Gst.SECOND / self.fps)

		# Push buffer
		ret = self.appsrc.emit('push-buffer', buffer)
		if ret != Gst.FlowReturn.OK:
			if ret == Gst.FlowReturn.FLUSHING:
				raise RuntimeError("Pipeline is flushing, cannot push buffer")
			elif ret == Gst.FlowReturn.EOS:
				raise RuntimeError("Pipeline reached end of stream")
			else:
				raise RuntimeError(f"Failed to push buffer: {ret}")

	def sleep_until_next_frame(self) -> None:
		"""Maintain target frame rate by sleeping if necessary."""
		current_time = time.time()
		elapsed = current_time - self.last_frame_time
		sleep_time = max(0, self.frame_time - elapsed)
		if sleep_time > 0:
			time.sleep(sleep_time)
		self.last_frame_time = time.time()

	def _get_pipeline_error(self) -> str:
		"""Extract error message from GStreamer pipeline bus (blocking)."""
		if self.pipeline is None:
			return "Pipeline is None"
		
		bus = self.pipeline.get_bus()
		if bus is None:
			return "Failed to get message bus"
		
		# Poll for error messages (non-blocking check first)
		msg = bus.pop_filtered(Gst.MessageType.ERROR | Gst.MessageType.EOS)
		if msg and msg.type == Gst.MessageType.ERROR:
			err, debug = msg.parse_error()
			return f"{err.message} (Debug: {debug})"
		
		# If no immediate message, try waiting briefly
		msg = bus.timed_pop_filtered(
			Gst.SECOND,  # Wait up to 1 second
			Gst.MessageType.ERROR | Gst.MessageType.EOS
		)
		if msg and msg.type == Gst.MessageType.ERROR:
			err, debug = msg.parse_error()
			return f"{err.message} (Debug: {debug})"
		
		return "Unknown error (no error message from GStreamer)"

	def _check_bus_for_errors(self) -> str:
		"""Non-blocking check for error messages on the bus."""
		if self.pipeline is None:
			return ""
		
		bus = self.pipeline.get_bus()
		if bus is None:
			return ""
		
		msg = bus.pop_filtered(Gst.MessageType.ERROR)
		if msg and msg.type == Gst.MessageType.ERROR:
			err, debug = msg.parse_error()
			return f"{err.message} (Debug: {debug})"
		
		return ""

	def cleanup(self) -> None:
		"""Stop and cleanup GStreamer pipeline."""
		if self.pipeline is not None:
			# Remove bus watch before stopping
			bus = self.pipeline.get_bus()
			if bus:
				bus.remove_signal_watch()
			self.pipeline.set_state(Gst.State.NULL)
			self.pipeline = None
			self.appsrc = None

