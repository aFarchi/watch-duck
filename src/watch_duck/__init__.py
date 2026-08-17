from importlib.metadata import PackageNotFoundError
from importlib.metadata import version

try:
    __version__ = version('watch-duck')
except PackageNotFoundError:
    __version__ = 'unknown'

