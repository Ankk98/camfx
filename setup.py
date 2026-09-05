from setuptools import setup, find_packages

setup(
	name='camfx',
	version='0.2.0a1',
	packages=find_packages(exclude=['tests', 'tests.*']),
	package_data={
		'camfx': ['resources/*.jpg'],
		'camfx_omarchy': ['hooks/*.sh', 'bindings/*.lua', 'systemd/*.service', 'templates/*', 'shell_plugin/camfx.camfx/*'],
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
		# Omarchy integration (plugin registry, theme adapter, bar widget)
		# Pure python (tomllib) — no extra runtime deps on Omarchy's Python 3.11+.
		# Optional backport for older interpreters:
		'omarchy': [],
		'all': [
			'PyGObject>=3.42.0',
			'dbus-python>=1.2.18',
		],
	},
	entry_points={
		'console_scripts': [
			'camfx=camfx.cli:cli',
			'omarchy-camfx=camfx_omarchy.cli:main',
		],
	},
	scripts=[
		'bin/omarchy-camfx',
		'bin/omarchy-camfx-status',
		'bin/omarchy-camfx-toggle',
		'bin/omarchy-camfx-theme-sync',
		'bin/omarchy-camfx-doctor',
		'bin/omarchy-camfx-gui',
	],
	license='MIT',
)


