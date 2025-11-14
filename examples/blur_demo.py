from camfx.core import VideoEnhancer


def main() -> None:
	enhancer = VideoEnhancer(0, effect_type='blur', config={'fps': 30})
	try:
		enhancer.run(preview=True, strength=25)
	except KeyboardInterrupt:
		print("Stopped")


if __name__ == "__main__":
	main()


