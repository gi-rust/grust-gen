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

import fnmatch
import re

class MatchList(object):
    """Implements name matching on a list of glob patterns.
    """

    def __init__(self, *args):
        if len(args) == 0:
            self._regexp = re.compile('(?!)')  # does not match anything
        else:
            branches = []
            for glob_pat in args:
                branch = '(?:{})'.format(fnmatch.translate(glob_pat))
                branches.append(branch)
            self._regexp = re.compile('|'.join(branches))

    def __contains__(self, name):
        return bool(self._regexp.match(name))
