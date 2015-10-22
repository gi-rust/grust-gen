def _get_version():
    try:
        from .version import version
    except ImportError:
        # The package has not been installed; try setup.py install or develop
        return None

    import os

    parent_dir = os.path.join(os.path.dirname(__file__), '..')
    if os.path.isdir(os.path.join(parent_dir, '.git')):

        import subprocess

        try:
            out = subprocess.check_output(['git', 'status', '--porcelain'],
                                          cwd=parent_dir)
        except Exception:
            out = ''
        if len(out) > 0:
            if '+' in version:
                version += '.dirty'
            else:
                version += '+dirty'

    return version

__version__ = _get_version()
