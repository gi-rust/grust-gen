# grust-gen - Rust binding generator for GObject introspection
#
# Copyright (C) 2015  Mikhail Zabaluev <mikhail.zabaluev@gmail.com>
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301  USA

import io
import os
import shutil
import stat
import sys
import tempfile

class FileOutput(object):
    """A context manager to atomically overwrite an output file.

    Upon entering the context, this context manager creates a temporary
    file in the same filesystem as the target file and returns the file
    object to bind in the ``as`` clause of the ``with`` statement.

    Upon exiting the context without an exception, the temporary file is
    renamed to the target file name, atomically replacing it. If an
    exception has occurred, the temporary file is deleted.
    """

    def __init__(self, filename, mode='w', encoding=None, newline=None):
        """Create a :class:`FileOutput` object with the target file name.

        :param filename: name of the eventual output file
        :param mode: mode parameter to pass to `tempfile.NamedTemporaryFile`
        :param encoding: character encoding as for func:`io.open`
        :param newline: newline mode as for func:`io.open`
        """
        self._filename = os.path.abspath(filename)
        self._open_kwargs = {
                'mode': mode,
                'encoding': encoding,
                'newline': newline
            }

    def __enter__(self):
        dirname, basename = os.path.split(self._filename)
        if sys.version_info.major >= 3:
            self._tempfile = tempfile.NamedTemporaryFile(
                    dir=dirname,
                    prefix=basename,
                    delete=False,
                    **self._open_kwargs)
        else:
            # Can't use the file opened by tempfile.NamedTemporaryFile
            # or tempfile.mkstemp() on Python 2.x because neither
            # supports encoding and newline parameters. The io module
            # does not interoperate with file objects produced by
            # tempfile, either. The next best thing to do is to close
            # the file and reopen it by name with io.open. This would
            # add a security hazard in some rather unusual, already weak
            # setups, but we rely on the file staying unchanged
            # after being closed in the __exit__ handler as well, so no
            # added risk here.
            handle, name = tempfile.mkstemp(dir=dirname, prefix=basename)
            os.close(handle)
            self._tempfile = io.open(name, **self._open_kwargs)

        try:
            if (os.path.isfile(self._filename)):
                shutil.copystat(self._filename, self._tempfile.name)
            else:
                os.chmod(self._tempfile.name,
                         stat.S_IWUSR | stat.S_IRUSR
                            | stat.S_IRGRP | stat.S_IROTH)
        except Exception:
            self._tempfile.close()
            os.remove(self._tempfile.name)
            raise

        return self._tempfile

    def __exit__(self, exception_type, exception, traceback):
        self._tempfile.close()
        if exception_type:
            os.remove(self._tempfile.name)
        else:
            os.rename(self._tempfile.name, self._filename)
        return False

class DirectOutput(object):
    """A do-nothing context manager around an output stream.

    On exit from the runtime context, this context manager leaves the
    stream intact. This is useful to send the output to stdout in the
    same ``with`` context where a :class:`FileOutput` object may
    alternatively be used.
    """
    def __init__(self, output):
        self._output = output

    def __enter__(self):
        return self._output

    def __exit__(self, exception_type, exception, traceback):
        return False
