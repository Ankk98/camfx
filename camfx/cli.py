"""Simple CLI for camfx."""

import glob
import logging
import os
import sys

import click

from .core import VideoEnhancer

logger = logging.getLogger('camfx.cli')


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
@click.option('--dbus', is_flag=True, default=False, help='Enable D-Bus service for runtime effect and camera control (REQUIRED for camera toggle)')
def start(input_index: int, width: int | None, height: int | None, fps: int, name: str,
         dbus: bool):
	"""Start camfx daemon (virtual camera service).

	The camera is OFF by default. Use D-Bus or CLI commands to control it:
	- camfx camera-start: Start the camera
	- camfx camera-stop: Stop the camera
	- camfx camera-status: Check camera status

	Use D-Bus commands (set-effect, add-effect) to configure effects.
	"""
	enhancer = VideoEnhancer(
		input_index,
		effect_type=None,
		config={
			'width': width,
			'height': height,
			'fps': fps,
			'enable_virtual': True,
			'camera_name': name,
			'enable_dbus': dbus,
		},
	)
	
	try:
		enhancer.run(preview=False)
	except KeyboardInterrupt:
		print("Stopped")


@cli.command('preview-camera')
@click.option('--input', 'input_index', default=0, type=int, help='Camera index (e.g., 0)')
def preview_camera(input_index: int):
	"""Preview from a camera source."""
	import cv2
	import time

	logger.info(f"Starting camera preview: input_index={input_index}")

	try:
		cap = cv2.VideoCapture(input_index)
		if not cap.isOpened():
			print(f"Error: Cannot open camera {input_index}")
			return

		print("Previewing camera feed")
		print("Press 'q' to quit.")
		cv2.namedWindow('camfx camera preview', cv2.WINDOW_NORMAL)

		try:
			while True:
				ret, frame = cap.read()
				if ret:
					cv2.imshow('camfx camera preview', frame)
				else:
					print("Warning: Failed to read frame from camera")

				key = cv2.waitKey(1) & 0xFF
				if key == ord('q'):
					break
		finally:
			cap.release()
			cv2.destroyAllWindows()

	except Exception as e:
		logger.error(f"Error in camera preview: {e}", exc_info=True)
		print(f"Error: {e}")


@cli.command('preview-virtual')
@click.option('--name', default='camfx', type=str, help='Name of the camfx virtual camera source to preview')
def preview_virtual(name: str):
	"""Preview from camfx virtual camera."""
	import cv2
	import time

	logger.info(f"Starting virtual camera preview: name={name}")

	try:
		from .input_pipewire import PipeWireInput
		pw_input = PipeWireInput(source_name=name)
		logger.info(f"Successfully connected to PipeWire source '{name}'")
		print(f"Previewing output from '{name}' virtual camera")
		print("Press 'q' to quit.")

		cv2.namedWindow('camfx virtual preview', cv2.WINDOW_NORMAL)
		logger.debug("Created OpenCV preview window")

		try:
			frame_count = 0
			no_frame_count = 0
			last_log_time = time.time()
			logger.info("Entering preview loop")

			while True:
				ret, frame = pw_input.read()
				if ret and frame is not None:
					logger.debug(f"Received frame: shape={frame.shape}, dtype={frame.dtype}")
					cv2.imshow('camfx virtual preview', frame)
					frame_count += 1
					no_frame_count = 0

					if frame_count == 1:
						logger.info("First frame received from virtual camera")
						print("Receiving frames from virtual camera...")

					# Log FPS every 5 seconds
					current_time = time.time()
					if current_time - last_log_time >= 5.0:
						fps = frame_count / (current_time - last_log_time + 0.001)
						logger.info(f"Preview FPS: {fps:.2f} (total frames: {frame_count})")
						frame_count = 0
						last_log_time = current_time
				else:
					# No frame available, wait a bit
					no_frame_count += 1
					if no_frame_count == 1:
						logger.debug("No frame available, waiting...")
					if no_frame_count == 100:  # ~1 second at 10ms intervals
						logger.warning("No frames received for ~1 second. Is camfx start running?")
						print("Warning: No frames received. Is camfx start running?")
					time.sleep(0.01)

				key = cv2.waitKey(1) & 0xFF
				if key == ord('q'):
					logger.info("User pressed 'q', exiting preview")
					break
		finally:
			logger.info("Cleaning up preview resources")
			pw_input.release()
			cv2.destroyAllWindows()
			logger.debug("Preview cleanup complete")

	except RuntimeError as e:
		logger.error(f"Virtual camera '{name}' not found: {e}")
		print(f"Error: Virtual camera '{name}' not found: {e}")
		print("Make sure camfx is running (camfx start)")
	except Exception as e:
		logger.error(f"Error in virtual camera preview: {e}", exc_info=True)
		print(f"Error: {e}")


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


@cli.command('camera-start')
def camera_start():
	"""Start the camera via D-Bus."""
	try:
		import dbus
		bus = dbus.SessionBus()
		service = bus.get_object('org.camfx.Control1', '/org/camfx/Control1')
		control = dbus.Interface(service, 'org.camfx.Control1')
		
		success = control.StartCamera()
		if success:
			print("Camera started")
		else:
			print("Failed to start camera")
	except dbus.exceptions.DBusException as e:
		print(f"Error connecting to camfx D-Bus service: {e}")
		print("Make sure camfx is running with D-Bus support enabled (camfx start --dbus)")
	except ImportError:
		print("Error: D-Bus Python bindings not available. Install dbus-python or python-dbus.")
	except Exception as e:
		print(f"Error: {e}")


@cli.command('camera-stop')
def camera_stop():
	"""Stop the camera via D-Bus."""
	try:
		import dbus
		bus = dbus.SessionBus()
		service = bus.get_object('org.camfx.Control1', '/org/camfx/Control1')
		control = dbus.Interface(service, 'org.camfx.Control1')
		
		success = control.StopCamera()
		if success:
			print("Camera stopped")
		else:
			print("Failed to stop camera")
	except dbus.exceptions.DBusException as e:
		print(f"Error connecting to camfx D-Bus service: {e}")
		print("Make sure camfx is running with D-Bus support enabled (camfx start --dbus)")
	except ImportError:
		print("Error: D-Bus Python bindings not available. Install dbus-python or python-dbus.")
	except Exception as e:
		print(f"Error: {e}")


@cli.command('camera-status')
def camera_status():
	"""Get camera status via D-Bus."""
	try:
		import dbus
		bus = dbus.SessionBus()
		service = bus.get_object('org.camfx.Control1', '/org/camfx/Control1')
		control = dbus.Interface(service, 'org.camfx.Control1')
		
		is_active = control.GetCameraState()
		if is_active:
			print("Camera is ON")
		else:
			print("Camera is OFF")
	except dbus.exceptions.DBusException as e:
		print(f"Error connecting to camfx D-Bus service: {e}")
		print("Make sure camfx is running with D-Bus support enabled (camfx start --dbus)")
	except ImportError:
		print("Error: D-Bus Python bindings not available. Install dbus-python or python-dbus.")
	except Exception as e:
		print(f"Error: {e}")


@cli.command()
def gui():
	"""Launch camfx control panel GUI."""
	try:
		from .gui.main_window import main
		exit_code = main()
		if exit_code:
			sys.exit(exit_code)
	except ImportError as e:
		print(f"Error importing GUI module: {e}")
		print("Make sure PyGObject and GTK4 are installed.")
		print("On Fedora: sudo dnf install python3-gobject gtk4")
		print("On Ubuntu/Debian: sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-4.0")
		sys.exit(1)
	except Exception as e:
		print(f"Error launching GUI: {e}")
		import traceback
		traceback.print_exc()
		sys.exit(1)


if __name__ == '__main__':
	cli()
