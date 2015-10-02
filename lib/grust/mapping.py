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

"""Machinery for mapping GI namespaces and types to Rust.

This module provides utilities and data types for mapping GObject
introspection data to Rust language constructs. The main functionality
for FFI bindings is implemented in :class:`RawMapper`.

Name mapping conventions
========================
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

import re
import string
from .gi import ast

_nonalpha_pat = re.compile(r'\W')
_lowercase_tr = string.maketrans(string.ascii_uppercase,
                                 string.ascii_lowercase)

def _sanitize_crate_name_chars(name):
    return _nonalpha_pat.sub('_', name).translate(_lowercase_tr)

def sys_crate_name(namespace):
    """Generate a conventional ``*_sys`` crate name for a GI namespace.

    The crate name is derived by replacing all non-alphanumeric
    characters in the namespace name and version with underscores
    and converting the name to lowercase, then concatenating the
    resulting strings separated with a ``_`` and appending ``_sys``.

    :param namespace: an object of :class:`grust.gi.ast.Namespace`.
    :return: a string with the crate name.
    """
    return '{name}_{version}_sys'.format(
            name=_sanitize_crate_name_chars(namespace.name),
            version=_sanitize_crate_name_chars(namespace.version))

class MappingError(Exception):
    """Raised when something cannot be represented in Rust.
    """
    pass

class Crate(object):
    """Information for a Rust crate.

    Typically, a crate corresponds to a GObject introspection namespace.
    """

    def __init__(self, name, local_name=None, namespace=None):
        self.name = name
        if local_name is not None:
            self.local_name = local_name
        else:
            self.local_name = name
        self.namespace = namespace

class RawMapper(object):
    """State and methods for mapping GI entities to Rust FFI and -sys crates. 

    This class provides a configurable mapping from GObject
    introspection entities to the information on Rust crates, Cargo packages,
    and Rust types generated as FFI bindings for the introspected APIs.
    """

    def __init__(self, namespace):
        self.crate = self._create_crate(namespace)
        self._extern_crates = {}  # namespace name -> Crate
        self._crate_libc = None

    def _create_crate(self, namespace):
        # This is a method, to allow per-namespace configuration
        # with overridable names later
        name = sys_crate_name(namespace)
        local_name = namespace.name.lower()  # FIXME: escape keywords and 'libc'
        return Crate(name, local_name, namespace)

    def register_namespace(self, namespace):
        if namespace == self.crate.namespace:
            return
        name = namespace.name
        if name not in self._extern_crates:
            crate = self._create_crate(namespace)
            self._extern_crates[name] = crate

    def resolve_fundamental_type(self, typedesc):
        """Ensure correct crate imports for a fundamental type.

        Most fundamental types are mapped to their namesakes in ``gtypes``
        and so don't need any specific imports provided that the definitions
        from ``gtypes`` are glob-imported. However, some exotic types,
        such as the Rust representation of ``long long``,
        are imported from ``libc`` as they don't have a conventional
        GLib name that would prevent potential name conflicts.
        """
        if self._crate_libc is not None:
            return
        if typedesc in (ast.TYPE_LONG_LONG, ast.TYPE_LONG_ULONG):
            self._crate_libc = Crate('libc')

    def extern_crates(self):
        """Return an iterator over the extern crate descriptions.

        The crates are listed in alphabetic order, except ``libc``
        which comes last when required.
        :return: an iterator of `Crate` objects.
        """
        for xc in sorted(self._extern_crates.values(), key=lambda xc: xc.name):
            yield xc
        if self._crate_libc:
            yield self._crate_libc
