from setuptools import setup, find_packages

setup(
	name='camfx',
	version='0.1.0',
	packages=find_packages(),
	install_requires=[
		'mediapipe>=0.10.0',
		'opencv-python>=4.8.0',
		'pyvirtualcam>=0.11.0',
		'click>=8.1.0',
		'numpy>=1.24.0',
	],
	entry_points={
		'console_scripts': [
			'camfx=camfx.cli:cli',
		],
	},
)


