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

from __future__ import print_function

import argparse
import os
import sys
from pkg_resources import resource_filename
import mako
from mako.lookup import Template, TemplateLookup
from .gi.transformer import Transformer
from .gi import message
from .gi import utils
from .generators.sys_crate import SysCrateWriter

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
    parser.add_argument('-t', '--template',
                        help='name of the custom template file')
    return parser

def error_cleanup(output):
    output.close()
    os.remove(output.name)

def generator_main():
    arg_parser = _create_arg_parser()
    opts = arg_parser.parse_args()
    if not opts.sys_mode:
        sys.exit('only --sys mode is currently supported')
    output = opts.output
    if output is None:
        output = open('lib.rs', 'w')
    logger = message.MessageLogger.get()
    logger.enable_warnings((message.FATAL, message.ERROR, message.WARNING))
    transformer = Transformer.parse_from_gir(opts.girfile, opts.include_dirs)

    if 'GRUST_GEN_TEMPLATE_DIR' in os.environ:
        template_dir = os.environ['GRUST_GEN_TEMPLATE_DIR']
    else:
        template_dir = resource_filename(__name__, 'templates')

    if 'GRUST_GEN_DISABLE_CACHE' in os.environ:
        tmpl_module_dir = None
    else:
        tmpl_module_dir = utils.get_user_cache_dir(
                os.path.join('grust-gen', 'template-modules'))

    tmpl_lookup = TemplateLookup(directories=[template_dir],
                                 output_encoding='utf-8',
                                 module_directory=tmpl_module_dir)
    if opts.template is None:
        template = tmpl_lookup.get_template('/sys/crate.tmpl')
    else:
        template = Template(filename=opts.template, lookup=tmpl_lookup)
    gen = SysCrateWriter(transformer=transformer,
                         template=template,
                         options=opts,
                         gir_filename=opts.girfile)
    try:
        gen.write(output)
    except Exception:
        error_template = mako.exceptions.text_error_template()
        sys.stderr.write(error_template.render())
        error_cleanup(output)
        return 1

    error_count = logger.get_error_count()
    warning_count = logger.get_warning_count()
    if error_count > 0 or warning_count > 0:
        print('{:d} error(s), {:d} warning(s)'.format(error_count, warning_count),
              file=sys.stderr)
    if error_count > 0:
        error_cleanup(output)
        return 2

    # FIXME: output should be a tempfile and replace the
    # existing file atomically
    output.close()
    return 0
