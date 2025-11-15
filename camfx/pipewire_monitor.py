"""PipeWire source usage monitoring to detect when virtual camera is being consumed."""

import json
import subprocess
import threading
import time
from typing import Optional, Callable, Set

try:
	import gi
	gi.require_version('PipeWire', '0.3')
	from gi.repository import PipeWire, GLib
	PIPEWIRE_AVAILABLE = True
except (ImportError, ValueError):
	PIPEWIRE_AVAILABLE = False


class PipeWireSourceMonitor:
	"""Monitor PipeWire source usage to detect when it's being consumed.
	
	Supports multiple simultaneous consumers - camera stays active as long as
	at least one client is connected.
	
	Uses pw-dump as a fallback if PipeWire GObject bindings are not available.
	"""
	
	def __init__(self, source_name: str = "camfx"):
		self.source_name = source_name
		self.active_clients: Set[int] = set()  # Track client IDs
		self.is_used = False
		self.callback: Optional[Callable[[bool], None]] = None
		self.monitoring = False
		self.use_pw_dump = not PIPEWIRE_AVAILABLE
		
		# PipeWire context and core (only if using GObject bindings)
		self.context: Optional[object] = None
		self.core: Optional[object] = None
		self.registry: Optional[object] = None
		self.source_node_id: Optional[int] = None
		
		# GLib main loop for event handling (only if using GObject bindings)
		self.main_loop: Optional[object] = None
		self.loop_thread: Optional[threading.Thread] = None
		
		# For pw-dump polling mode
		self.poll_thread: Optional[threading.Thread] = None
		self.poll_interval = 1.0  # Poll every second
	
	def _check_pw_dump_available(self) -> bool:
		"""Check if pw-dump command is available."""
		try:
			subprocess.run(['pw-dump', '--version'], capture_output=True, timeout=2)
			return True
		except (FileNotFoundError, subprocess.TimeoutExpired):
			return False
	
	def _poll_pw_dump(self):
		"""Poll pw-dump to check for active links to our source node."""
		if not self._check_pw_dump_available():
			print("Warning: pw-dump not available, cannot monitor source usage")
			if self.callback:
				self.callback(False)  # Indicate monitoring failed
			return
		
		last_state = False
		
		while self.monitoring:
			try:
				# Get all PipeWire objects
				result = subprocess.run(
					['pw-dump'],
					capture_output=True,
					text=True,
					timeout=5
				)
				
				if result.returncode != 0:
					time.sleep(self.poll_interval)
					continue
				
				data = json.loads(result.stdout)
				
				# Find our source node
				source_node = None
				for obj in data:
					if obj.get('type') == 'PipeWire:Interface:Node':
						props = obj.get('info', {}).get('props', {})
						if (props.get('media.class') == 'Video/Source' and
							props.get('media.name') == self.source_name):
							source_node = obj
							self.source_node_id = obj.get('id')
							break
				
				if source_node is None:
					# Source node not found yet
					self.active_clients.clear()
					current_state = False
				else:
					# Find all links connected to our source node
					source_id = source_node.get('id')
					active_clients = set()
					
					for obj in data:
						if obj.get('type') == 'PipeWire:Interface:Link':
							link_info = obj.get('info', {})
							output_node = link_info.get('output-node-id')
							input_node = link_info.get('input-node-id')
							
							# Check if link is connected to our source (as output)
							if output_node == source_id:
								# Link is active if input node exists
								if input_node:
									active_clients.add(input_node)
					
					self.active_clients = active_clients
					current_state = len(active_clients) > 0
				
				# Notify if state changed
				if current_state != last_state:
					self.is_used = current_state
					if self.callback:
						self.callback(current_state)
					last_state = current_state
				
			except Exception as e:
				print(f"Error polling PipeWire state: {e}")
			
			time.sleep(self.poll_interval)
	
	def _on_registry_global(self, registry, id, permissions, type, version, props):
		"""Callback when a new global object is registered (GObject bindings only)."""
		if type == PipeWire.types.DICT_ENTRY_SPA_TYPE_INFO_Node:
			# Check if this is our source node
			name = props.get('media.name', '')
			if name == self.source_name:
				self.source_node_id = id
				print(f"Found source node: {self.source_name} (id: {id})")
				self._update_usage_state()
	
	def _on_registry_global_remove(self, registry, id):
		"""Callback when a global object is removed (GObject bindings only)."""
		if id == self.source_node_id:
			self.source_node_id = None
			self.active_clients.clear()
			self._update_usage_state()
	
	def _on_link_state_changed(self, link, state):
		"""Callback when a link state changes (GObject bindings only)."""
		if self.source_node_id is None:
			return
		
		# Get link properties
		props = link.get_properties()
		output_node_id = props.get('link.output.node', 0)
		
		if output_node_id == self.source_node_id:
			input_node_id = props.get('link.input.node', 0)
			
			if state == PipeWire.LinkState.ACTIVE:
				if input_node_id not in self.active_clients:
					self.active_clients.add(input_node_id)
					print(f"Client connected (node {input_node_id}). Active clients: {len(self.active_clients)}")
					self._update_usage_state()
			elif state in [PipeWire.LinkState.UNLINKED, PipeWire.LinkState.ERROR]:
				if input_node_id in self.active_clients:
					self.active_clients.remove(input_node_id)
					print(f"Client disconnected (node {input_node_id}). Active clients: {len(self.active_clients)}")
					self._update_usage_state()
	
	def _update_usage_state(self):
		"""Update usage state based on active clients (GObject bindings only)."""
		was_used = self.is_used
		self.is_used = len(self.active_clients) > 0
		
		if was_used != self.is_used:
			if self.callback:
				self.callback(self.is_used)
	
	def _setup_pipewire_connection(self):
		"""Set up PipeWire connection and event handlers (GObject bindings only)."""
		try:
			# Create PipeWire context
			self.context = PipeWire.Context.new()
			self.core = self.context.connect(None)
			
			if self.core is None:
				raise RuntimeError("Failed to connect to PipeWire")
			
			# Get registry to monitor nodes and links
			self.registry = self.core.get_registry()
			
			# Connect to registry events
			self.registry.connect('global', self._on_registry_global)
			self.registry.connect('global-remove', self._on_registry_global_remove)
			
			# Update registry to get current state
			self.core.sync(PipeWire.types.PW_ID_CORE, 0)
			
			print("PipeWire connection established")
			
		except Exception as e:
			print(f"Failed to set up PipeWire connection: {e}")
			raise
	
	def _main_loop_thread(self):
		"""Run GLib main loop in separate thread (GObject bindings only)."""
		try:
			self.main_loop = GLib.MainLoop.new(None, False)
			self.main_loop.run()
		except Exception as e:
			print(f"Error in main loop: {e}")
	
	def start_monitoring(self, callback: Callable[[bool], None]):
		"""Start monitoring source usage and call callback when state changes.
		
		Args:
			callback: Function to call when usage state changes (bool: is_used)
		"""
		self.callback = callback
		
		if self.use_pw_dump:
			# Use pw-dump polling mode
			print("Using pw-dump polling mode for PipeWire monitoring")
			self.monitoring = True
			self.poll_thread = threading.Thread(target=self._poll_pw_dump, daemon=True)
			self.poll_thread.start()
			
			# Give it a moment to initialize
			time.sleep(0.5)
			
			# Initial state check (will be done in polling thread)
		else:
			# Use GObject bindings
			try:
				self._setup_pipewire_connection()
				
				# Start GLib main loop in separate thread
				self.monitoring = True
				self.loop_thread = threading.Thread(target=self._main_loop_thread, daemon=True)
				self.loop_thread.start()
				
				# Give it a moment to initialize
				time.sleep(0.5)
				
				# Initial state check
				self._update_usage_state()
				
			except Exception as e:
				print(f"Failed to start PipeWire monitoring: {e}")
				print("Falling back to pw-dump polling mode")
				self.use_pw_dump = True
				self.monitoring = True
				self.poll_thread = threading.Thread(target=self._poll_pw_dump, daemon=True)
				self.poll_thread.start()
				time.sleep(0.5)
	
	def stop_monitoring(self):
		"""Stop monitoring."""
		self.monitoring = False
		
		if self.main_loop:
			self.main_loop.quit()
		
		if self.loop_thread:
			self.loop_thread.join(timeout=2.0)
		
		if self.poll_thread:
			self.poll_thread.join(timeout=2.0)
		
		# Clean up PipeWire connection (if using GObject bindings)
		if self.core:
			try:
				self.core.disconnect()
			except Exception:
				pass
		if self.context:
			try:
				self.context.destroy()
			except Exception:
				pass
		
		self.active_clients.clear()
		self.source_node_id = None

