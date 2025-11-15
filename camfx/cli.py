import glob
import os

import click


@click.group()
def cli():
	pass


@cli.command()
@click.option('--strength', default=25, type=int, help='Kernel size for Gaussian blur (must be odd, e.g., 3,5,7,...). Even values will be adjusted to next odd number.')
@click.option('--input', 'input_index', default=0, type=int, help='Camera index (e.g., 0)')
@click.option('--preview', is_flag=True, default=False, help='Show a preview window')
@click.option('--no-virtual', is_flag=True, default=False, help='Disable virtual camera output (preview only)')
@click.option('--width', default=None, type=int, help='Input capture width')
@click.option('--height', default=None, type=int, help='Input capture height')
@click.option('--fps', default=30, type=int, help='Virtual camera FPS')
@click.option('--name', default='camfx', type=str, help='Name for the virtual camera source')
def blur(strength: int, input_index: int, preview: bool, no_virtual: bool, width: int | None, height: int | None, fps: int, name: str):
	"""Apply background blur effect to camera feed."""
	# Validate and adjust strength value
	if strength <= 0:
		raise click.ClickException(f"Invalid strength value: {strength}. Strength must be a positive integer (e.g., 3, 5, 7, ...)")
	
	original_strength = strength
	if strength % 2 == 0:
		strength = strength + 1  # Round up to next odd number
		click.echo(f"Warning: Strength must be odd. Adjusted {original_strength} to {strength}.", err=True)
	
	# Defer heavy imports to avoid slowing other commands
	from .core import VideoEnhancer
	import cv2  # noqa: F401
	enhancer = VideoEnhancer(
		input_index,
		effect_type='blur',
		config={'width': width, 'height': height, 'fps': fps, 'enable_virtual': (not no_virtual), 'camera_name': name},
	)
	try:
		enhancer.run(preview=preview, strength=strength)
	except KeyboardInterrupt:
		print("Stopped")
	except ValueError as e:
		# Re-raise as ClickException for better CLI error formatting
		raise click.ClickException(str(e))


@cli.command()
@click.option('--image', required=True, type=str, help='Path to background image')
@click.option('--input', 'input_index', default=0, type=int, help='Camera index (e.g., 0)')
@click.option('--preview', is_flag=True, default=False, help='Show a preview window')
@click.option('--no-virtual', is_flag=True, default=False, help='Disable virtual camera output (preview only)')
@click.option('--width', default=None, type=int, help='Input capture width')
@click.option('--height', default=None, type=int, help='Input capture height')
@click.option('--fps', default=30, type=int, help='Virtual camera FPS')
@click.option('--name', default='camfx', type=str, help='Name for the virtual camera source')
def replace(image: str, input_index: int, preview: bool, no_virtual: bool, width: int | None, height: int | None, fps: int, name: str):
	"""Replace background with a static image."""
	# Defer heavy imports to avoid slowing other commands
	from .core import VideoEnhancer
	import cv2
	bg = cv2.imread(image)
	if bg is None:
		raise click.ClickException(f"Failed to read background image: {image}")
	enhancer = VideoEnhancer(
		input_index,
		effect_type='replace',
		config={'width': width, 'height': height, 'fps': fps, 'enable_virtual': (not no_virtual), 'camera_name': name},
	)
	try:
		enhancer.run(preview=preview, background=bg)
	except KeyboardInterrupt:
		print("Stopped")


@cli.command()
@click.option('--brightness', default=0, type=int, help='Brightness adjustment (-100 to 100, 0 = no change)')
@click.option('--contrast', default=1.0, type=float, help='Contrast multiplier (0.5 to 2.0, 1.0 = no change)')
@click.option('--face-only', is_flag=True, default=False, help='Apply brightness/contrast only to face region (requires segmentation)')
@click.option('--input', 'input_index', default=0, type=int, help='Camera index (e.g., 0)')
@click.option('--preview', is_flag=True, default=False, help='Show a preview window')
@click.option('--no-virtual', is_flag=True, default=False, help='Disable virtual camera output (preview only)')
@click.option('--width', default=None, type=int, help='Input capture width')
@click.option('--height', default=None, type=int, help='Input capture height')
@click.option('--fps', default=30, type=int, help='Virtual camera FPS')
@click.option('--name', default='camfx', type=str, help='Name for the virtual camera source')
def brightness(brightness: int, contrast: float, face_only: bool, input_index: int, preview: bool, no_virtual: bool, width: int | None, height: int | None, fps: int, name: str):
	"""Adjust brightness and contrast of the camera feed."""
	from .core import VideoEnhancer
	enhancer = VideoEnhancer(
		input_index,
		effect_type='brightness',
		config={'width': width, 'height': height, 'fps': fps, 'enable_virtual': (not no_virtual), 'camera_name': name},
	)
	try:
		enhancer.run(preview=preview, brightness=brightness, contrast=contrast, face_only=face_only)
	except KeyboardInterrupt:
		print("Stopped")
	except ValueError as e:
		raise click.ClickException(str(e))


@cli.command()
@click.option('--smoothness', default=5, type=int, help='Skin smoothing strength (1-15, higher = more smoothing)')
@click.option('--input', 'input_index', default=0, type=int, help='Camera index (e.g., 0)')
@click.option('--preview', is_flag=True, default=False, help='Show a preview window')
@click.option('--no-virtual', is_flag=True, default=False, help='Disable virtual camera output (preview only)')
@click.option('--width', default=None, type=int, help='Input capture width')
@click.option('--height', default=None, type=int, help='Input capture height')
@click.option('--fps', default=30, type=int, help='Virtual camera FPS')
@click.option('--name', default='camfx', type=str, help='Name for the virtual camera source')
def beautify(smoothness: int, input_index: int, preview: bool, no_virtual: bool, width: int | None, height: int | None, fps: int, name: str):
	"""Apply skin smoothing and face beautification effects."""
	from .core import VideoEnhancer
	enhancer = VideoEnhancer(
		input_index,
		effect_type='beautify',
		config={'width': width, 'height': height, 'fps': fps, 'enable_virtual': (not no_virtual), 'camera_name': name},
	)
	try:
		enhancer.run(preview=preview, smoothness=smoothness)
	except KeyboardInterrupt:
		print("Stopped")
	except ValueError as e:
		raise click.ClickException(str(e))


@cli.command()
@click.option('--padding', default=0.3, type=float, help='Padding around face as fraction of face size (0.0-1.0)')
@click.option('--min-zoom', default=1.0, type=float, help='Minimum zoom level (1.0 = no zoom)')
@click.option('--max-zoom', default=2.0, type=float, help='Maximum zoom level')
@click.option('--input', 'input_index', default=0, type=int, help='Camera index (e.g., 0)')
@click.option('--preview', is_flag=True, default=False, help='Show a preview window')
@click.option('--no-virtual', is_flag=True, default=False, help='Disable virtual camera output (preview only)')
@click.option('--width', default=None, type=int, help='Input capture width')
@click.option('--height', default=None, type=int, help='Input capture height')
@click.option('--fps', default=30, type=int, help='Virtual camera FPS')
@click.option('--name', default='camfx', type=str, help='Name for the virtual camera source')
def autoframe(padding: float, min_zoom: float, max_zoom: float, input_index: int, preview: bool, no_virtual: bool, width: int | None, height: int | None, fps: int, name: str):
	"""Automatically crop and center the frame on the detected face."""
	from .core import VideoEnhancer
	enhancer = VideoEnhancer(
		input_index,
		effect_type='autoframe',
		config={'width': width, 'height': height, 'fps': fps, 'enable_virtual': (not no_virtual), 'camera_name': name},
	)
	try:
		enhancer.run(preview=preview, padding=padding, min_zoom=min_zoom, max_zoom=max_zoom)
	except KeyboardInterrupt:
		print("Stopped")
	except ValueError as e:
		raise click.ClickException(str(e))


@cli.command('list-devices')
def list_devices():
	"""List available camera device nodes and names via sysfs (non-blocking)."""
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


if __name__ == '__main__':
	cli()


