import glob
import os

import click


@click.group()
def cli():
	pass


@cli.command()
@click.option('--strength', default=25, type=int, help='Odd kernel size for Gaussian blur (e.g., 3,5,7,...)')
@click.option('--input', 'input_index', default=0, type=int, help='Camera index (e.g., 0)')
@click.option('--vdevice', default='/dev/video10', type=str, help='Virtual device path')
@click.option('--preview', is_flag=True, default=False, help='Show a preview window')
@click.option('--no-virtual', is_flag=True, default=False, help='Disable virtual camera output (preview only)')
@click.option('--width', default=None, type=int, help='Input capture width')
@click.option('--height', default=None, type=int, help='Input capture height')
@click.option('--fps', default=30, type=int, help='Virtual camera FPS')
def blur(strength: int, input_index: int, vdevice: str, preview: bool, no_virtual: bool, width: int | None, height: int | None, fps: int):
	# Defer heavy imports to avoid slowing other commands
	from .core import VideoEnhancer
	import cv2  # noqa: F401
	enhancer = VideoEnhancer(
		input_index,
		effect_type='blur',
		config={'vdevice': vdevice, 'width': width, 'height': height, 'fps': fps, 'enable_virtual': (not no_virtual)},
	)
	try:
		enhancer.run(preview=preview, strength=strength)
	except KeyboardInterrupt:
		print("Stopped")


@cli.command()
@click.option('--image', required=True, type=str, help='Path to background image')
@click.option('--input', 'input_index', default=0, type=int, help='Camera index (e.g., 0)')
@click.option('--vdevice', default='/dev/video10', type=str, help='Virtual device path')
@click.option('--preview', is_flag=True, default=False, help='Show a preview window')
@click.option('--no-virtual', is_flag=True, default=False, help='Disable virtual camera output (preview only)')
@click.option('--width', default=None, type=int, help='Input capture width')
@click.option('--height', default=None, type=int, help='Input capture height')
@click.option('--fps', default=30, type=int, help='Virtual camera FPS')
def replace(image: str, input_index: int, vdevice: str, preview: bool, no_virtual: bool, width: int | None, height: int | None, fps: int):
	# Defer heavy imports to avoid slowing other commands
	from .core import VideoEnhancer
	import cv2
	bg = cv2.imread(image)
	if bg is None:
		raise click.ClickException(f"Failed to read background image: {image}")
	enhancer = VideoEnhancer(
		input_index,
		effect_type='replace',
		config={'vdevice': vdevice, 'width': width, 'height': height, 'fps': fps, 'enable_virtual': (not no_virtual)},
	)
	try:
		enhancer.run(preview=preview, background=bg)
	except KeyboardInterrupt:
		print("Stopped")


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


