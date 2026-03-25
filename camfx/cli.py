"""Simple CLI for camfx."""

import glob
import io
import logging
import os
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import TextIO

import click

from .core import VideoEnhancer
from .effect_specs import EFFECT_SPECS, EFFECT_KEYS

logger = logging.getLogger('camfx.cli')
_CLI_LOGGING_CONFIGURED = False
_CLI_LOG_FILE: Path | None = None
_CLI_LOG_HANDLE: TextIO | None = None
_ORIGINAL_STDOUT: TextIO | None = None
_ORIGINAL_STDERR: TextIO | None = None


class _RunIdentifierFilter(logging.Filter):
	def __init__(self, run_id: str, command_name: str | None):
		super().__init__()
		self.run_id = run_id
		self.command_name = (command_name or 'cli').replace(' ', '_')

	def filter(self, record: logging.LogRecord) -> bool:
		record.cli_run_id = self.run_id
		record.cli_command = self.command_name
		return True


class _TeeStream(io.TextIOBase):
	def __init__(self, original: TextIO, log_handle: TextIO, stream_name: str, run_id: str, command_name: str | None):
		self._original = original
		self._log_handle = log_handle
		self._stream_name = stream_name
		self._run_id = run_id
		self._command_name = (command_name or 'cli').replace(' ', '_')

	def write(self, s) -> int:
		if not s:
			return 0

		# Some libraries (including click) may write bytes depending on stream detection.
		if isinstance(s, (bytes, bytearray)):
			try:
				s = bytes(s).decode("utf-8", errors="replace")
			except Exception:
				s = str(s)

		self._original.write(s)
		timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
		for chunk in s.splitlines(True):
			if chunk == '':
				continue
			self._log_handle.write(
				f"{timestamp} [{self._stream_name}] {self._run_id} {self._command_name} - {chunk}"
			)
		self._log_handle.flush()
		return len(s)

	def flush(self) -> None:
		self._original.flush()
		self._log_handle.flush()

	def isatty(self) -> bool:
		return getattr(self._original, 'isatty', lambda: False)()

	def fileno(self) -> int:
		return getattr(self._original, 'fileno', lambda: -1)()


def _setup_cli_logging(command_name: str | None) -> Path:
	global _CLI_LOGGING_CONFIGURED, _CLI_LOG_FILE

	if _CLI_LOGGING_CONFIGURED and _CLI_LOG_FILE is not None:
		return _CLI_LOG_FILE

	project_root = Path(__file__).resolve().parents[1]
	logs_dir = project_root / 'logs'
	logs_dir.mkdir(parents=True, exist_ok=True)

	log_file = logs_dir / 'cli.log'
	run_id = uuid.uuid4().hex[:8]

	file_handler = logging.FileHandler(log_file, encoding='utf-8')
	file_handler.setLevel(logging.DEBUG)
	file_handler.addFilter(_RunIdentifierFilter(run_id, command_name))
	file_handler.setFormatter(logging.Formatter(
		'%(asctime)s [%(levelname)8s] %(cli_run_id)s %(cli_command)s %(name)s:%(funcName)s:%(lineno)d - %(message)s',
		datefmt='%Y-%m-%d %H:%M:%S'
	))

	root_logger = logging.getLogger()
	root_logger.addHandler(file_handler)

	global _CLI_LOG_HANDLE, _ORIGINAL_STDOUT, _ORIGINAL_STDERR
	if _CLI_LOG_HANDLE is None:
		_CLI_LOG_HANDLE = open(log_file, 'a', encoding='utf-8')

	if _ORIGINAL_STDOUT is None:
		_ORIGINAL_STDOUT = sys.stdout
	if _ORIGINAL_STDERR is None:
		_ORIGINAL_STDERR = sys.stderr

	sys.stdout = _TeeStream(_ORIGINAL_STDOUT, _CLI_LOG_HANDLE, 'STDOUT', run_id, command_name)
	sys.stderr = _TeeStream(_ORIGINAL_STDERR, _CLI_LOG_HANDLE, 'STDERR', run_id, command_name)

	_CLI_LOGGING_CONFIGURED = True
	_CLI_LOG_FILE = log_file
	print(f"[camfx] Logging CLI output to: {log_file} (run_id={run_id})")

	return log_file


class CamfxCLI(click.Group):
	def invoke(self, ctx):
		_setup_cli_logging(ctx.invoked_subcommand)
		return super().invoke(ctx)


@click.group(cls=CamfxCLI)
def cli():
	"""camfx - Camera effects with live switching and chaining."""
	pass


@cli.command()
@click.option('--input', 'input_index', default=0, type=int, help='Camera index (e.g., 0)')
@click.option('--width', default=None, type=int, help='Input capture width')
@click.option('--height', default=None, type=int, help='Input capture height')
@click.option('--fps', default=30, type=int, help='Virtual camera FPS')
@click.option('--name', default='camfx', type=str, help='Virtual camera card label (v4l2loopback card_label)')
@click.option('--v4l2-device', default='auto', type=str, help='v4l2 device node (e.g. /dev/video0) or auto')
@click.option('--v4l2-card-label', default=None, type=str, help='Card label for auto-discovery (defaults to --name)')
@click.option('--dbus', is_flag=True, default=False, help='Enable D-Bus service for runtime effect and camera control (REQUIRED for camera toggle)')
def start(input_index: int, width: int | None, height: int | None, fps: int, name: str,
         v4l2_device: str, v4l2_card_label: str | None, dbus: bool):
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
			'v4l2_device': v4l2_device,
			'v4l2_card_label': v4l2_card_label or name,
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
@click.option('--v4l2-device', default='auto', type=str, help='v4l2 device node (e.g. /dev/video0) or auto')
def preview_virtual(name: str, v4l2_device: str):
	"""Preview from camfx v4l2 virtual camera."""
	import cv2
	import time

	logger.info(f"Starting virtual camera preview: name={name}")

	try:
		device = v4l2_device
		if device == "auto":
			device = None
			try:
				sys_class = "/sys/class/video4linux"
				if os.path.isdir(sys_class):
					for entry in sorted(os.listdir(sys_class)):
						name_path = f"{sys_class}/{entry}/name"
						try:
							with open(name_path, "r", encoding="utf-8") as f:
								n = f.read().strip()
							if n == name:
								candidate = f"/dev/{entry}"
								if os.path.exists(candidate):
									device = candidate
									break
						except OSError:
							continue
			except Exception:
				device = None
			if not device:
				raise RuntimeError("Could not resolve v4l2 device. Use --v4l2-device=/dev/videoX.")

		cap = cv2.VideoCapture(device)
		if not cap.isOpened():
			raise RuntimeError(f"Cannot open v4l2 device: {device}")

		logger.info(f"Successfully connected to v4l2 device '{device}'")
		print(f"Previewing output from v4l2 device '{device}'")
		print("Press 'q' to quit.")

		cv2.namedWindow('camfx virtual preview', cv2.WINDOW_NORMAL)
		logger.debug("Created OpenCV preview window")

		try:
			frame_count = 0
			no_frame_count = 0
			last_log_time = time.time()
			logger.info("Entering preview loop")

			while True:
				ret, frame = cap.read()
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
			cap.release()
			cv2.destroyAllWindows()
			logger.debug("Preview cleanup complete")

	except RuntimeError as e:
		logger.error(f"Virtual camera not available: {e}")
		print(f"Error: {e}")
		print("Make sure v4l2loopback is loaded and /dev/videoX exists")
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


@cli.command("effects")
def effects():
	"""List effects and their supported options."""
	print("Available effects:\n")
	for spec in EFFECT_SPECS:
		req = " (requires MediaPipe Tasks models)" if spec.requires_mediapipe_tasks else ""
		print(f"- {spec.key}: {spec.title}{req}")
		print(f"  {spec.description}")
		if not spec.params:
			print("  Options: (none)")
		else:
			print("  Options:")
			for p in spec.params:
				extra = []
				if p.value_range:
					extra.append(p.value_range)
				if p.default is not None:
					extra.append(f"default={p.default}")
				if p.notes:
					extra.append(p.notes)
				suffix = f" ({'; '.join(extra)})" if extra else ""
				print(f"    {p.flag}: {p.help}{suffix}")
		print()


@cli.command('set-effect')
@click.option('--effect', required=True, type=click.Choice(EFFECT_KEYS))
@click.option('--strength', type=float, help='Blur: kernel size (int) | Gaze: strength (0.0..1.0)')
@click.option('--image', type=str, help='Replace: background image path')
@click.option('--brightness', type=int, help='Brightness: -100..100')
@click.option('--contrast', type=float, help='Brightness: 0.5..2.0')
@click.option('--face-only', is_flag=True, default=False, help='Brightness: apply only to masked region (requires segmentation)')
@click.option('--smoothness', type=int, help='Beautify: 1..15')
@click.option('--padding', type=float, help='Autoframe: 0.0..1.0')
@click.option('--min-zoom', type=float, help='Autoframe: >= 1.0')
@click.option('--max-zoom', type=float, help='Autoframe: >= min-zoom')
def set_effect(effect, **kwargs):
	"""Change effect at runtime via D-Bus (replaces all effects)."""
	try:
		import dbus
		bus = dbus.SessionBus()
		service = bus.get_object('org.camfx.Control1', '/org/camfx/Control1')
		control = dbus.Interface(service, 'org.camfx.Control1')
		
		# Build config dict from kwargs (drop None, and omit false flags by default)
		config = {}
		for key, value in kwargs.items():
			if value is None:
				continue
			if isinstance(value, bool) and value is False:
				continue
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
@click.option('--effect', required=True, type=click.Choice(EFFECT_KEYS))
@click.option('--strength', type=float, help='Blur: kernel size (int) | Gaze: strength (0.0..1.0)')
@click.option('--image', type=str, help='Replace: background image path')
@click.option('--brightness', type=int, help='Brightness: -100..100')
@click.option('--contrast', type=float, help='Brightness: 0.5..2.0')
@click.option('--face-only', is_flag=True, default=False, help='Brightness: apply only to masked region (requires segmentation)')
@click.option('--smoothness', type=int, help='Beautify: 1..15')
@click.option('--padding', type=float, help='Autoframe: 0.0..1.0')
@click.option('--min-zoom', type=float, help='Autoframe: >= 1.0')
@click.option('--max-zoom', type=float, help='Autoframe: >= min-zoom')
def add_effect(effect, **kwargs):
	"""Add effect to chain at runtime via D-Bus."""
	try:
		import dbus
		bus = dbus.SessionBus()
		service = bus.get_object('org.camfx.Control1', '/org/camfx/Control1')
		control = dbus.Interface(service, 'org.camfx.Control1')
		
		# Build config dict from kwargs (drop None, and omit false flags by default)
		config = {}
		for key, value in kwargs.items():
			if value is None:
				continue
			if isinstance(value, bool) and value is False:
				continue
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
@click.option('--effect', type=click.Choice(EFFECT_KEYS), help='Type of effect to remove')
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


@cli.command('models-download')
def models_download():
	"""Prefetch MediaPipe Tasks models for ML effects."""
	try:
		from .mediapipe_tasks import ensure_model, SELFIE_SEGMENTER_LANDSCAPE, FACE_LANDMARKER, _default_models_dir
	except Exception as e:
		print(f"Error: cannot import MediaPipe Tasks backend: {e}")
		print("Make sure mediapipe is installed: pip install mediapipe")
		raise SystemExit(1)

	print(f"Downloading models to: {_default_models_dir()}")
	try:
		p1 = ensure_model(SELFIE_SEGMENTER_LANDSCAPE)
		print(f"✓ {SELFIE_SEGMENTER_LANDSCAPE.name}: {p1}")
		p2 = ensure_model(FACE_LANDMARKER)
		print(f"✓ {FACE_LANDMARKER.name}: {p2}")
		print("All models downloaded.")
	except Exception as e:
		print(f"Error downloading models: {e}")
		raise SystemExit(1)


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
