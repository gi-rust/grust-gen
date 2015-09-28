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
from ..errors import RepresentationError

class SysCrateWriter(object):
    """Generator for -sys crates."""

    def __init__(self, transformer, name_mapper, template_lookup, options):
        self._transformer = transformer
        self._name_mapper = name_mapper
        self._lookup = template_lookup
        self._options = options
        self._imports = set()  # ast.Namespace
        self._transformer.namespace.walk(
            lambda node, chain: self._prepare_walk(node, chain))

    def write(self, output):
        template = self._lookup.get_template('sys/crate.tmpl')
        result = template.render(name_mapper=self._name_mapper,
                                 namespace=self._transformer.namespace,
                                 imports=self._imports)
        output.write(result)

    def _prepare_walk(self, node, chain):
        if isinstance(node, ast.Callable):
            self._prepare_callable(node)
        elif isinstance(node, ast.Compound):
            self._prepare_compound(node)
        elif isinstance(node, ast.Constant):
            self._prepare_type(node.value_type)
        return True

    def _prepare_type(self, typedesc):
        if typedesc is None:
            return;

        if isinstance(typedesc, ast.Array):
            self._prepare_array(typedesc)
        elif isinstance(typedesc, ast.List):
            self._resolve_giname(typedesc.name)
        elif isinstance(typedesc, ast.Map):
            self._resolve_giname('GLib.HashTable')
        elif typedesc.target_fundamental:
            return;
        elif typedesc.target_giname:
            self._resolve_giname(typedesc.target_giname)
        else:
            raise RepresentationError("can't represent type {}".format(typedesc))

    def _prepare_array(self, typedesc):
        if typedesc.array_type == ast.Array.C:
            self._prepare_type(typedesc.element_type)
        else:
            self._resolve_giname(typedesc.array_type)

    def _prepare_callable(self, node):
        for param in node.parameters:
            self._prepare_type(param.type)
        self._prepare_type(node.retval.type)

    def _prepare_compound(self, node):
        for field in node.fields:
            self._prepare_type(field.type)

    def _resolve_giname(self, name):
        typenode = self._transformer.lookup_giname(name)
        assert typenode, 'reference to undefined type {}'.format(name)
        ns = typenode.namespace
        if (ns != self._transformer.namespace):
            self._imports.add(ns)
