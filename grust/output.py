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

import os
import shutil
import stat
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

    def __init__(self, filename, text=True):
        """Create a :class:`FileOutput` object with the target file name.
        """
        self._filename = os.path.abspath(filename)
        self._text_mode = text

    def __enter__(self):
        dirname, basename = os.path.split(self._filename)
        handle, name = tempfile.mkstemp(
                dir=dirname,
                prefix=basename,
                suffix='.tmp',
                text=self._text_mode)
        mode = 'w' if self._text_mode else 'wb'
        self._tmp_output = os.fdopen(handle, mode)
        self._tmp_filename = name
        if (os.path.isfile(self._filename)):
            shutil.copystat(self._filename, self._tmp_filename)
        else:
            os.chmod(self._tmp_filename,
                     stat.S_IWUSR | stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
        return self._tmp_output

    def __exit__(self, exception_type, exception, traceback):
        self._tmp_output.close()
        if exception:
            os.remove(self._tmp_filename)
        else:
            os.rename(self._tmp_filename, self._filename)
        return False

class DirectOutput(object):
    """A do-nothing context manager around an output stream.

    On exit from the runtime context, this context manager leaves the
    stream intact. This is useful to send the output to stdout in the
    same ``with`` context where a :class:`FileOutput` may alternatively
    be used.
    """
    def __init__(self, output):
        self._output = output

    def __enter__(self):
        return self._output

    def __exit__(self, exception_type, exception, traceback):
        return False
