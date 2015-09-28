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

import re
import string

_nonalpha_pat = re.compile(r'\W')
_lowercase_tr = string.maketrans(string.ascii_uppercase,
                                 string.ascii_lowercase)

def _sanitize_crate_name_chars(name):
    return _nonalpha_pat.sub('_', name).translate(_lowercase_tr)

class NameMapper(object):
    """Machinery for mapping GI namespaces to Rust crate names.
    
    This class provides a configurable mapping from GObject
    introspection namespaces to names of Rust crates and Cargo packages
    generated as bindings for the introspected APIs.

    There are two kinds of Rust packages that can in principle be
    produced for a GObject namespace. A `*-sys package`_ links to the
    library that provides the C API, and the library crate in such a
    package contains only the FFI definitions. A high-level binding
    package builds on that to provide a safe and idiomatic Rust API.
    The name mapping convention for both kinds of packages and crates
    built from them is designed to automatically derive unique,
    lint-compliant names allowing existence of bindings for multiple
    versions of a GObject namespace on crates.io.

    :: _`*-sys package`: http://doc.crates.io/build-script.html#*-sys-packages
    """

    def sys_crate_name(self, namespace):
        """Return the ``*_sys`` crate name for a GI namespace.

        The crate name is derived by replacing all non-alphanumeric
        characters in the namespace name and version with underscores
        and converting the name to lowercase, then concatenating the
        resulting strings separated with a ``_`` and appending ``_sys``.

        The parameter `namespace` should be an object of
        class `giscanner.ast.Namespace`.
        """
        return '{name}_{version}_sys'.format(
                name=_sanitize_crate_name_chars(namespace.name),
                version=_sanitize_crate_name_chars(namespace.version))
