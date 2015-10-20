try:
    from .version import version as __version__
except ImportError:
    # The package has not been installed; try setup.py install or develop
    __version__ = None
