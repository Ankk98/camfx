__all__ = [
	"__version__",
]

__version__ = "0.1.0"

# Configure logging for camfx
import logging
import sys

# Configure root logger to ensure all child loggers work properly
root_logger = logging.getLogger()
root_logger.setLevel(logging.DEBUG)

# Create logger for camfx
logger = logging.getLogger('camfx')
logger.setLevel(logging.DEBUG)
# Ensure child loggers propagate to parent (default is True, but explicit is better)
logger.propagate = True

# Create console handler if not already exists
# Only add to root logger to avoid duplicate messages (child loggers will propagate)
if not root_logger.handlers:
	handler = logging.StreamHandler(sys.stderr)
	handler.setLevel(logging.DEBUG)
	
	# Create formatter with detailed information
	formatter = logging.Formatter(
		'%(asctime)s [%(levelname)8s] %(name)s:%(funcName)s:%(lineno)d - %(message)s',
		datefmt='%Y-%m-%d %H:%M:%S'
	)
	handler.setFormatter(formatter)
	root_logger.addHandler(handler)


