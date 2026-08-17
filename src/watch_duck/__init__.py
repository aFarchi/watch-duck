from importlib.metadata import PackageNotFoundError, version

try:  # ruff:ignore[non-empty-init-module]
    __version__ = version('watch-duck')
except PackageNotFoundError:
    __version__ = 'unknown'
