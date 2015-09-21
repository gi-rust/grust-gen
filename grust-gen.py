# This file is part of Grust, GObject introspection bindings for Rust
#
# Copyright (C) 2013, 2015  Mikhail Zabaluev <mikhail.zabaluev@gmail.com>
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

# Taken from g-ir-scanner executable, to make Transformer work.
import os
import __builtin__
if os.name == 'nt':
    datadir = os.path.join(os.path.dirname(__file__), '..', 'share')
else:
    datadir = "/usr/share"
__builtin__.__dict__['DATADIR'] = datadir

from giscanner import ast
from giscanner.transformer import Transformer
from mako.lookup import TemplateLookup
import argparse
import re
import string
import sys

def _sanitize_crate_name(name):
    return re.sub(r'\W', '_', name).lower()

def _sys_crate_name(namespace):
    """Derive a sys crate name from GIR data."""
    name = _sanitize_crate_name(namespace.name)
    name += '_'
    name += _sanitize_crate_name(namespace.version)
    return name + '_sys';

class SysCrateWriter(object):
    """Generator for -sys crates."""

    def __init__(self, transformer, options):
        self._transformer = transformer
        self._options = options
        self._lookup = self._get_template_lookup()
        self._imports = {}  # name -> ast.Namespace
        self._transformer.namespace.walk(
            lambda node, chain: self._prepare_walk(node, chain))

    def _get_template_lookup(self):
        srcdir = os.path.dirname(__file__)
        template_dir = os.path.join(srcdir, 'templates', 'sys')
        return TemplateLookup(directories=[template_dir],
                              output_encoding='utf-8')

    def write(self, output):
        template = self._lookup.get_template('crate.tmpl')
        options = self._options
        crate_name = (options.crate_name or
                _sys_crate_name(self._transformer.namespace))
        result = template.render(crate_name=crate_name,
                                 imports=self._imports,
                                 sys_crate_name=_sys_crate_name)
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
        typenode = self._transformer.lookup_typenode(typedesc)
        if typenode:
            ns = typenode.namespace
            if (ns != self._transformer.namespace
                    and ns.name not in self._imports):
                self._imports[ns.name] = ns

    def _prepare_callable(self, node):
        for param in node.parameters:
            self._prepare_type(param.type)
        self._prepare_type(node.retval.type)

    def _prepare_compound(self, node):
        for field in node.fields:
            self._prepare_type(field.type)

def _create_arg_parser():
    parser = argparse.ArgumentParser(
        description='Generate a Rust crate from GIR XML')
    parser.add_argument('girfile', help='GIR XML file')
    parser.add_argument('--sys', dest='sys_mode', action='store_true',
                        help='generate a sys crate')
    parser.add_argument('-o', '--output', type=argparse.FileType('w'),
                        help='output file')
    parser.add_argument('-I', '--include-dir', action='append',
                        dest='include_dirs', metavar='DIR',
                        help='add directory to include search path')
    parser.add_argument('--crate-name',
                        help='Name of the generated crate')
    return parser

if __name__ == '__main__':
    arg_parser = _create_arg_parser()
    args = arg_parser.parse_args()
    output = args.output
    if not args.sys_mode:
        sys.exit('only --sys mode is currently supported')
    if output is None:
        output = open('lib.rs', 'w')
    transformer = Transformer.parse_from_gir(args.girfile, args.include_dirs)
    gen = SysCrateWriter(transformer, args)
    gen.write(output)
