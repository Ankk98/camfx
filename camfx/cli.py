"""Simple CLI for camfx."""

import glob
import os

import click

from .core import VideoEnhancer


@click.group()
def cli():
	"""camfx - Camera effects with live switching and chaining."""
	pass


@cli.command()
@click.option('--input', 'input_index', default=0, type=int, help='Camera index (e.g., 0)')
@click.option('--width', default=None, type=int, help='Input capture width')
@click.option('--height', default=None, type=int, help='Input capture height')
@click.option('--fps', default=30, type=int, help='Virtual camera FPS')
@click.option('--name', default='camfx', type=str, help='Name for the virtual camera source')
@click.option('--lazy-camera', is_flag=True, default=False, help='Only use camera when virtual source is actively consumed')
@click.option('--dbus', is_flag=True, default=False, help='Enable D-Bus service for runtime effect control')
@click.option('--effect', type=click.Choice(['blur', 'replace', 'brightness', 'beautify', 'autoframe', 'gaze-correct']), help='Initial effect to apply')
@click.option('--strength', type=int, help='For blur effect (must be odd)')
@click.option('--brightness', type=int, help='For brightness effect (-100 to 100)')
@click.option('--contrast', type=float, help='For brightness effect (0.5 to 2.0)')
@click.option('--smoothness', type=int, help='For beautify effect (1-15)')
@click.option('--padding', type=float, help='For autoframe effect')
@click.option('--min-zoom', type=float, help='For autoframe effect')
@click.option('--max-zoom', type=float, help='For autoframe effect')
def start(input_index: int, width: int | None, height: int | None, fps: int, name: str, 
         lazy_camera: bool, dbus: bool, effect: str | None, **kwargs):
	"""Start virtual camera with optional initial effect.
	
	Use D-Bus commands (set-effect, add-effect) to change effects at runtime.
	"""
	# Build initial effect config
	initial_config = {}
	if effect:
		for key, value in kwargs.items():
			if value is not None:
				initial_config[key] = value
	
	enhancer = VideoEnhancer(
		input_index,
		effect_type=effect or None,
		config={
			'width': width,
			'height': height,
			'fps': fps,
			'enable_virtual': True,
			'camera_name': name,
			'enable_dbus': dbus,
			**initial_config,
		},
		enable_lazy_camera=lazy_camera,
	)
	
	try:
		enhancer.run(preview=False)
	except KeyboardInterrupt:
		print("Stopped")


@cli.command()
@click.option('--name', default='camfx', type=str, help='Name of the camfx virtual camera source to preview')
@click.option('--input', 'input_index', default=0, type=int, help='Camera index (fallback if virtual camera not found)')
@click.option('--effect', type=click.Choice(['blur', 'replace', 'brightness', 'beautify', 'autoframe', 'gaze-correct']), help='Effect to preview (only used if virtual camera not found)')
@click.option('--strength', type=int, help='For blur effect (must be odd)')
@click.option('--brightness', type=int, help='For brightness effect (-100 to 100)')
@click.option('--contrast', type=float, help='For brightness effect (0.5 to 2.0)')
@click.option('--smoothness', type=int, help='For beautify effect (1-15)')
@click.option('--padding', type=float, help='For autoframe effect')
@click.option('--min-zoom', type=float, help='For autoframe effect')
@click.option('--max-zoom', type=float, help='For autoframe effect')
def preview(name: str, input_index: int, effect: str | None, **kwargs):
	"""Preview output from running camfx instance, or camera feed with optional effect.
	
	If a camfx virtual camera is running, previews its output.
	Otherwise, falls back to previewing camera directly with optional effect.
	"""
	import cv2
	
	# Try to connect to PipeWire virtual camera first
	try:
		from .input_pipewire import PipeWireInput
		pw_input = PipeWireInput(source_name=name)
		print(f"Previewing output from '{name}' virtual camera")
		print("Press 'q' to quit.")
		
		cv2.namedWindow('camfx preview', cv2.WINDOW_NORMAL)
		
		try:
			frame_count = 0
			no_frame_count = 0
			while True:
				ret, frame = pw_input.read()
				if ret and frame is not None:
					cv2.imshow('camfx preview', frame)
					frame_count += 1
					no_frame_count = 0
					if frame_count == 1:
						print("Receiving frames from virtual camera...")
				else:
					# No frame available, wait a bit
					no_frame_count += 1
					if no_frame_count == 100:  # ~1 second at 10ms intervals
						print("Warning: No frames received. Is camfx start running?")
					import time
					time.sleep(0.01)
				
				key = cv2.waitKey(1) & 0xFF
				if key == ord('q'):
					break
		finally:
			pw_input.release()
			cv2.destroyAllWindows()
		
	except RuntimeError as e:
		# Virtual camera not found, fall back to direct camera preview
		print(f"Virtual camera '{name}' not found: {e}")
		print("Falling back to direct camera preview...")
		
		# Build effect config
		effect_config = {}
		if effect:
			for key, value in kwargs.items():
				if value is not None:
					effect_config[key] = value
		
		enhancer = VideoEnhancer(
			input_index,
			effect_type=effect or None,
			config={
				'enable_virtual': False,
				**effect_config,
			},
			enable_lazy_camera=False,
		)
		
		try:
			enhancer.run(preview=True, **effect_config)
		except KeyboardInterrupt:
			print("Stopped")


@cli.command('list-devices')
def list_devices():
	"""List available camera device nodes and names."""
	paths = sorted(glob.glob('/dev/video*'))
	print("Detected device nodes:", ", ".join(paths) if paths else "none")
	for dev in paths:
		basename = os.path.basename(dev)
		name_path = f"/sys/class/video4linux/{basename}/name"
		try:
			with open(name_path, 'r', encoding='utf-8') as f:
				name = f.read().strip()
		except Exception:
			name = "?"
		print(f"{dev}: {name}")


@cli.command('set-effect')
@click.option('--effect', required=True, type=click.Choice(['blur', 'replace', 'brightness', 'beautify', 'autoframe', 'gaze-correct']))
@click.option('--strength', type=int, help='For blur effect (must be odd)')
@click.option('--brightness', type=int, help='For brightness effect (-100 to 100)')
@click.option('--contrast', type=float, help='For brightness effect (0.5 to 2.0)')
@click.option('--smoothness', type=int, help='For beautify effect (1-15)')
@click.option('--padding', type=float, help='For autoframe effect')
@click.option('--min-zoom', type=float, help='For autoframe effect')
@click.option('--max-zoom', type=float, help='For autoframe effect')
def set_effect(effect, **kwargs):
	"""Change effect at runtime via D-Bus (replaces all effects)."""
	try:
		import dbus
		bus = dbus.SessionBus()
		service = bus.get_object('org.camfx.Control1', '/org/camfx/Control1')
		control = dbus.Interface(service, 'org.camfx.Control1')
		
		# Build config dict from kwargs
		config = {}
		for key, value in kwargs.items():
			if value is not None:
				config[key] = value
		
		success = control.SetEffect(effect, config)
		if success:
			print(f"Effect changed to: {effect}")
		else:
			print(f"Failed to change effect to: {effect}")
	except dbus.exceptions.DBusException as e:
		print(f"Error connecting to camfx D-Bus service: {e}")
		print("Make sure camfx is running with D-Bus support enabled (camfx start --dbus)")
	except ImportError:
		print("Error: D-Bus Python bindings not available. Install dbus-python or python-dbus.")
	except Exception as e:
		print(f"Error: {e}")


@cli.command('add-effect')
@click.option('--effect', required=True, type=click.Choice(['blur', 'replace', 'brightness', 'beautify', 'autoframe', 'gaze-correct']))
@click.option('--strength', type=int, help='For blur effect (must be odd)')
@click.option('--brightness', type=int, help='For brightness effect (-100 to 100)')
@click.option('--contrast', type=float, help='For brightness effect (0.5 to 2.0)')
@click.option('--smoothness', type=int, help='For beautify effect (1-15)')
@click.option('--padding', type=float, help='For autoframe effect')
@click.option('--min-zoom', type=float, help='For autoframe effect')
@click.option('--max-zoom', type=float, help='For autoframe effect')
def add_effect(effect, **kwargs):
	"""Add effect to chain at runtime via D-Bus."""
	try:
		import dbus
		bus = dbus.SessionBus()
		service = bus.get_object('org.camfx.Control1', '/org/camfx/Control1')
		control = dbus.Interface(service, 'org.camfx.Control1')
		
		# Build config dict from kwargs
		config = {}
		for key, value in kwargs.items():
			if value is not None:
				config[key] = value
		
		success = control.AddEffect(effect, config)
		if success:
			print(f"Effect added/updated in chain: {effect}")
		else:
			print(f"Failed to add effect: {effect}")
	except dbus.exceptions.DBusException as e:
		print(f"Error connecting to camfx D-Bus service: {e}")
		print("Make sure camfx is running with D-Bus support enabled (camfx start --dbus)")
	except ImportError:
		print("Error: D-Bus Python bindings not available. Install dbus-python or python-dbus.")
	except Exception as e:
		print(f"Error: {e}")


@cli.command('remove-effect')
@click.option('--index', type=int, help='Index of effect to remove (0-based)')
@click.option('--effect', type=click.Choice(['blur', 'replace', 'brightness', 'beautify', 'autoframe', 'gaze-correct']), help='Type of effect to remove')
def remove_effect(index, effect):
	"""Remove effect from chain at runtime via D-Bus.
	
	Either --index or --effect must be provided.
	"""
	if index is None and effect is None:
		print("Error: Either --index or --effect must be provided")
		return
	
	if index is not None and effect is not None:
		print("Error: Cannot specify both --index and --effect. Use one or the other.")
		return
	
	try:
		import dbus
		bus = dbus.SessionBus()
		service = bus.get_object('org.camfx.Control1', '/org/camfx/Control1')
		control = dbus.Interface(service, 'org.camfx.Control1')
		
		if index is not None:
			success = control.RemoveEffect(index)
			if success:
				print(f"Effect at index {index} removed from chain")
			else:
				print(f"Failed to remove effect at index {index}")
		else:
			success = control.RemoveEffectByType(effect)
			if success:
				print(f"Effect '{effect}' removed from chain")
			else:
				print(f"Effect '{effect}' not found in chain")
	except dbus.exceptions.DBusException as e:
		print(f"Error connecting to camfx D-Bus service: {e}")
		print("Make sure camfx is running with D-Bus support enabled (camfx start --dbus)")
	except ImportError:
		print("Error: D-Bus Python bindings not available. Install dbus-python or python-dbus.")
	except Exception as e:
		print(f"Error: {e}")


@cli.command('get-effects')
def get_effects():
	"""Get current effect chain via D-Bus."""
	try:
		import dbus
		bus = dbus.SessionBus()
		service = bus.get_object('org.camfx.Control1', '/org/camfx/Control1')
		control = dbus.Interface(service, 'org.camfx.Control1')
		
		effects = control.GetCurrentEffects()
		if not effects:
			print("No effects in chain")
		else:
			print(f"Current effect chain ({len(effects)} effects):")
			for i, (effect_type, class_name, config) in enumerate(effects):
				config_str = ", ".join(f"{k}={v}" for k, v in config.items())
				print(f"  {i}: {effect_type} ({class_name}) - {config_str}")
	except dbus.exceptions.DBusException as e:
		print(f"Error connecting to camfx D-Bus service: {e}")
		print("Make sure camfx is running with D-Bus support enabled (camfx start --dbus)")
	except ImportError:
		print("Error: D-Bus Python bindings not available. Install dbus-python or python-dbus.")
	except Exception as e:
		print(f"Error: {e}")


if __name__ == '__main__':
	cli()
