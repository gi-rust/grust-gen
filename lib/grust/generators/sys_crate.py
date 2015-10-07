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

from ..gi import ast
from ..gi import message
from ..mapping import RawMapper, MappingError

class SysCrateWriter(object):
    """Generator for -sys crates."""

    def __init__(self,
                 transformer,
                 template_lookup,
                 options,
                 gir_filename=None):
        self._transformer = transformer
        self._mapper = RawMapper(transformer.namespace)
        self._lookup = template_lookup
        self._options = options
        if gir_filename:
            self._message_positions = set(
                    (message.Position(filename=gir_filename),))
        else:
            self._message_positions = set()
        self._extern_crates = {}  # namespace name -> Crate
        self._transformer.namespace.walk(
            lambda node, chain: self._prepare_walk(node, chain))

    def write(self, output):
        template = self._lookup.get_template('sys/crate.tmpl')
        result = template.render(mapper=self._mapper,
                                 message_positions=self._message_positions)
        output.write(result)

    def _prepare_walk(self, node, chain):
        try:
            if isinstance(node, ast.Callable):
                self._prepare_callable(node)
            elif isinstance(node, ast.Compound):
                self._prepare_compound(node)
            elif isinstance(node, ast.Constant):
                self._prepare_type(node.value_type)
            elif isinstance(node, ast.Alias):
                self._prepare_type(node.target)
            elif isinstance(node, ast.Interface):
                assert len(node.fields) == 0, \
                    'Fields found in interface {}. Strange, huh?'.format(node.name)
        except MappingError as e:
            message.log_node(message.ERROR, node, e,
                             positions=self._message_positions,
                             context=node)
            return False
        return True

    def _prepare_type(self, typedesc):
        if typedesc is None:
            return;
        self._mapper.resolve_type(typedesc, self._transformer)

    def _prepare_callable(self, node):
        if not isinstance(node, (ast.Function, ast.Callback)):
            return
        for param in node.parameters:
            self._mapper.resolve_call_signature_type(param, self._transformer)
        self._mapper.resolve_call_signature_type(node.retval, self._transformer)

    def _prepare_compound(self, node):
        for field in node.fields:
            self._prepare_type(field.type)
