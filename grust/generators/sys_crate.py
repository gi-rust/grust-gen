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

from ..giscanner import ast
from ..giscanner import message
from ..mapping import RawMapper, MappingError

class SysCrateWriter(object):
    """Generator for -sys crates."""

    def __init__(self,
                 transformer,
                 template,
                 options,
                 gir_filename=None):
        self._mapper = RawMapper(transformer)
        self._template = template
        self._options = options
        if gir_filename:
            self._message_positions = set(
                    (message.Position(filename=gir_filename),))
        else:
            self._message_positions = set()
        transformer.namespace.walk(
            lambda node, chain: self._prepare_walk(node, chain))

    def write(self, output):
        result = self._template.render_unicode(
                    mapper=self._mapper,
                    message_positions=self._message_positions)
        output.write(result)

    def _prepare_walk(self, node, chain):
        try:
            self._mapper.resolve_types_for_node(node)
        except MappingError as e:
            message.error_node(node, e,
                               positions=self._message_positions,
                               context=node)
            return False
        return True
