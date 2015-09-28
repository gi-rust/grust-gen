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

import argparse
import os
import sys
from mako.lookup import TemplateLookup
from .gi.transformer import Transformer
from .gi import utils
from .generators.sys_crate import SysCrateWriter
from .namemap import NameMapper

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

def generator_main(template_dir):
    arg_parser = _create_arg_parser()
    opts = arg_parser.parse_args()
    if not opts.sys_mode:
        sys.exit('only --sys mode is currently supported')
    output = opts.output
    if output is None:
        output = open('lib.rs', 'w')
    transformer = Transformer.parse_from_gir(opts.girfile, opts.include_dirs)
    name_mapper = NameMapper()
    if 'GRUST_GEN_TEMPLATE_DIR' in os.environ:
        template_dir = os.environ['GRUST_GEN_TEMPLATE_DIR']
    if 'GRUST_GEN_DISABLE_CACHE' in os.environ:
        tmpl_module_dir = None
    else:
        tmpl_module_dir = utils.get_user_cache_dir(
                os.path.join('grust-gen', 'template-modules'))
    tmpl_lookup = TemplateLookup(directories=[template_dir],
                                 output_encoding='utf-8',
                                 module_directory=tmpl_module_dir)
    gen = SysCrateWriter(transformer,
                         name_mapper=name_mapper,
                         template_lookup=tmpl_lookup,
                         options=opts)
    gen.write(output)
    output.close()
    return 0
