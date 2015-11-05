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
from .giscanner.transformer import Transformer
from .giscanner import message
from .giscanner import utils
from .generators.sys_crate import SysCrateWriter
from .output import FileOutput, DirectOutput
from . import __version__ as version

def output_file(name):
    if name == '-':
        return DirectOutput(sys.stdout)
    else:
        return FileOutput(name, encoding='utf-8')

def _create_arg_parser():
    parser = argparse.ArgumentParser(
        description='Generate a Rust crate from GIR XML')
    parser.add_argument('girfile', help='GIR XML file')
    parser.add_argument('--version', action='version',
                        version='%(prog)s ' + version)
    parser.add_argument('--sys', dest='sys_mode', action='store_true',
                        help='generate a sys crate')
    parser.add_argument('-o', '--output', type=output_file,
                        help='output file')
    parser.add_argument('-I', '--include-dir', action='append',
                        dest='include_dirs', metavar='DIR',
                        help='add directory to include search path')
    parser.add_argument('-t', '--template',
                        help='name of the custom template file')
    return parser

def generator_main():
    arg_parser = _create_arg_parser()
    opts = arg_parser.parse_args()
    if not opts.sys_mode:
        sys.exit('only --sys mode is currently supported')

    output = opts.output
    if output is None:
        output = output_file('lib.rs')

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
        py_suffix = '-py{}.{}'.format(sys.version_info.major,
                                      sys.version_info.minor)
        tmpl_module_dir = utils.get_user_cache_dir(
                os.path.join('grust-gen', 'template-modules' + py_suffix))

    tmpl_lookup = TemplateLookup(directories=[template_dir],
                                 module_directory=tmpl_module_dir)
    if opts.template is None:
        template = tmpl_lookup.get_template('/sys/crate.tmpl')
    else:
        template = Template(filename=opts.template,
                            lookup=tmpl_lookup)

    gen = SysCrateWriter(transformer=transformer,
                         template=template,
                         options=opts,
                         gir_filename=opts.girfile)

    with output as out:
        try:
            gen.write(out)
        except Exception:
            error_template = mako.exceptions.text_error_template()
            sys.stderr.write(error_template.render())
            raise SystemExit(1)

        error_count = logger.get_error_count()
        warning_count = logger.get_warning_count()
        if error_count > 0 or warning_count > 0:
            print('{:d} error(s), {:d} warning(s)'.format(error_count, warning_count),
                  file=sys.stderr)
        if error_count > 0:
            raise SystemExit(2)

    return 0
