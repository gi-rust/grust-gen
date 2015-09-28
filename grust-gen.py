#!/usr/bin/python

# grust-gen - Rust binding generator for GObject introspection
#
# Copyright (C) 2015  Mikhail Zabaluev <mikhail.zabaluev@gmail.com>
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301  USA

import os
import sys

if os.name == 'nt':
    datadir = os.path.join(os.path.dirname(__file__), '..', 'share')
    template_dir = os.path.join(datadir, 'grust-gen', 'templates')
else:
    datadir = "/usr/share"
    template_dir = "/usr/share/grust-gen/templates"

# This is needed to make Transformer work.
import __builtin__
__builtin__.__dict__['DATADIR'] = datadir

from grust.genmain import generator_main

exitcode = generator_main(template_dir=template_dir)

sys.exit(exitcode)
