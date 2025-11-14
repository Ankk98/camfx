"""PipeWire virtual camera output using GStreamer via PyGObject."""

import os
import subprocess
import sys
import time
from typing import Optional

import gi

gi.require_version('Gst', '1.0')
from gi.repository import Gst


class PipeWireOutput:
	"""PipeWire virtual camera output using GStreamer's pipewiresink element."""

	@staticmethod
	def _check_wireplumber_available() -> tuple[bool, str]:
		"""Check if wireplumber service is available and running.
		
		Returns:
			Tuple of (is_available, status_message)
		"""
		try:
			# Check if wireplumber service exists and is active
			result = subprocess.run(
				['systemctl', '--user', 'is-active', 'wireplumber'],
				capture_output=True,
				text=True,
				timeout=2
			)
			if result.returncode == 0:
				return True, "wireplumber is running"
			else:
				return False, "wireplumber service is not active"
		except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.SubprocessError):
			# Fallback: check if wireplumber process is running
			try:
				result = subprocess.run(
					['pgrep', '-u', str(os.getuid()), 'wireplumber'],
					capture_output=True,
					timeout=2
				)
				if result.returncode == 0:
					return True, "wireplumber process is running"
				else:
					return False, "wireplumber process not found"
			except Exception:
				return False, "could not check wireplumber status"

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
		# Check wireplumber availability before attempting to create pipeline
		wireplumber_available, wireplumber_status = self._check_wireplumber_available()
		if not wireplumber_available:
			print(f"Warning: {wireplumber_status}. Virtual camera may not work.", file=sys.stderr)
			print("To start wireplumber: systemctl --user start wireplumber", file=sys.stderr)
		
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
		# We'll set stream-properties programmatically to handle names with spaces/special chars
		pipeline_str = (
			f'appsrc name=source is-live=true format=time do-timestamp=true '
			f'caps=video/x-raw,format=RGB,width={width},height={height},framerate={fps}/1 ! '
			f'videoconvert ! '
			f'pipewiresink name=sink'
		)

		try:
			self.pipeline = Gst.parse_launch(pipeline_str)
			if self.pipeline is None:
				raise RuntimeError("Failed to parse GStreamer pipeline")

			self.appsrc = self.pipeline.get_by_name('source')
			if self.appsrc is None:
				raise RuntimeError("Failed to get appsrc element from pipeline")
			
			# Set stream properties programmatically using GstStructure
			# This properly handles names with spaces and special characters
			sink = self.pipeline.get_by_name('sink')
			if sink is None:
				raise RuntimeError("Failed to get pipewiresink element from pipeline")
			
			# Create GstStructure for stream-properties
			# pipewiresink expects stream-properties to be a GstStructure, not a string
			stream_props = Gst.Structure.new_empty("props")
			stream_props.set_value("media.class", "Video/Source")
			stream_props.set_value("media.name", name)  # GstStructure handles spaces properly
			stream_props.set_value("media.role", "Camera")
			
			# Set the stream-properties property with the GstStructure
			# Properties should be set before starting the pipeline
			sink.set_property("stream-properties", stream_props)

			# Get message bus to capture errors before state change
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
						# Try multiple methods to get error message
						error_msg = self._check_bus_for_errors()
						if not error_msg:
							# Try blocking method as last resort
							error_msg = self._get_pipeline_error()
						
						# Get final state for additional context
						final_state_ret = self.pipeline.get_state(0)  # Non-blocking
						state = final_state_ret[1] if len(final_state_ret) > 1 else None
						state_name = self._get_state_name(state) if state is not None else "unknown"
						
						if not error_msg or error_msg == "Unknown error (no error message from GStreamer)":
							error_msg = f"No error message available (Pipeline stuck in state: {state_name})"
						
						# Provide more specific guidance based on state
						if state == Gst.State.PLAYING:
							guidance = (
								"Pipeline is stuck transitioning to PLAYING state. "
								"This usually means pipewiresink cannot connect to PipeWire. "
								"Ensure wireplumber (PipeWire session manager) is running:\n"
								"  systemctl --user start wireplumber\n"
								"  systemctl --user status wireplumber"
							)
						elif state == Gst.State.PAUSED:
							guidance = (
								"Pipeline is stuck in PAUSED state and cannot transition to PLAYING. "
								"This usually means pipewiresink cannot connect to PipeWire. "
								"Ensure wireplumber (PipeWire session manager) is running:\n"
								"  systemctl --user start wireplumber\n"
								"  systemctl --user status wireplumber"
							)
						else:
							guidance = (
								"This may indicate PipeWire session manager (wireplumber) is not running. "
								"Try: systemctl --user start wireplumber"
							)
						
						raise RuntimeError(
							f"Timeout ({timeout_seconds}s) waiting for pipeline to start.\n"
							f"{guidance}\n"
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
		
		# Collect all error and warning messages
		error_messages = []
		warning_messages = []
		
		# Poll for messages (non-blocking check first)
		while True:
			msg = bus.pop_filtered(Gst.MessageType.ERROR | Gst.MessageType.WARNING | Gst.MessageType.EOS)
			if not msg:
				break
			
			if msg.type == Gst.MessageType.ERROR:
				err, debug = msg.parse_error()
				error_msg = f"{err.message}"
				if debug:
					error_msg += f" (Debug: {debug})"
				error_messages.append(error_msg)
			elif msg.type == Gst.MessageType.WARNING:
				warn, debug = msg.parse_warning()
				warn_msg = f"{warn.message}"
				if debug:
					warn_msg += f" (Debug: {debug})"
				warning_messages.append(warn_msg)
		
		# If no immediate messages, try waiting briefly for more
		msg = bus.timed_pop_filtered(
			Gst.SECOND,  # Wait up to 1 second
			Gst.MessageType.ERROR | Gst.MessageType.WARNING | Gst.MessageType.EOS
		)
		if msg:
			if msg.type == Gst.MessageType.ERROR:
				err, debug = msg.parse_error()
				error_msg = f"{err.message}"
				if debug:
					error_msg += f" (Debug: {debug})"
				error_messages.append(error_msg)
			elif msg.type == Gst.MessageType.WARNING:
				warn, debug = msg.parse_warning()
				warn_msg = f"{warn.message}"
				if debug:
					warn_msg += f" (Debug: {debug})"
				warning_messages.append(warn_msg)
		
		# Return the most relevant error, or warnings if no errors
		if error_messages:
			return "; ".join(error_messages)
		elif warning_messages:
			return f"Warnings (no errors): {'; '.join(warning_messages)}"
		else:
			return "Unknown error (no error message from GStreamer)"

	def _get_state_name(self, state: int) -> str:
		"""Convert GStreamer state enum to human-readable name."""
		state_names = {
			Gst.State.VOID_PENDING: "VOID_PENDING",
			Gst.State.NULL: "NULL",
			Gst.State.READY: "READY",
			Gst.State.PAUSED: "PAUSED",
			Gst.State.PLAYING: "PLAYING",
		}
		return state_names.get(state, f"UNKNOWN({state})")
	
	def _check_bus_for_errors(self) -> str:
		"""Non-blocking check for error messages on the bus."""
		if self.pipeline is None:
			return ""
		
		bus = self.pipeline.get_bus()
		if bus is None:
			return ""
		
		# Check for ERROR messages
		msg = bus.pop_filtered(Gst.MessageType.ERROR)
		if msg and msg.type == Gst.MessageType.ERROR:
			err, debug = msg.parse_error()
			return f"{err.message} (Debug: {debug})"
		
		# Also check for WARNING messages which might provide context
		msg = bus.pop_filtered(Gst.MessageType.WARNING)
		if msg and msg.type == Gst.MessageType.WARNING:
			warn, debug = msg.parse_warning()
			return f"Warning: {warn.message} (Debug: {debug})"
		
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

