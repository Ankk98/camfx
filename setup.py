from setuptools import setup, find_packages

setup(
	name='camfx',
	version='0.2.0',
	packages=find_packages(),
	package_data={
		'camfx': ['resources/*.jpg'],
	},
	include_package_data=True,
	install_requires=[
		'mediapipe>=0.10.0',
		'opencv-python>=4.8.0',
		'click>=8.1.0',
		'numpy>=1.24.0',
	],
	extras_require={
		# GUI requires GTK4 / PyGObject.
		'gui': [
			'PyGObject>=3.42.0',
		],
		# D-Bus runtime (camera start/stop + effect control).
		'dbus': [
			'dbus-python>=1.2.18',
			'PyGObject>=3.42.0',
		],
	},
	entry_points={
		'console_scripts': [
			'camfx=camfx.cli:cli',
		],
	},
	license='MIT',
)


