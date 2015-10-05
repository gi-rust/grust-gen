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

ffi_basic_types = {}
for name in ('gpointer', 'gconstpointer', 'gboolean', 'gchar', 'gshort',
             'gushort', 'gint', 'guint', 'glong', 'gulong', 'gsize', 'gssize',
             'gintptr', 'guintptr', 'gfloat', 'gdouble', 'GType'):
    ffi_basic_types[name] = name
ffi_basic_types['gint8']   = 'i8'
ffi_basic_types['guint8']  = 'u8'
ffi_basic_types['gint16']  = 'i16'
ffi_basic_types['guint16'] = 'u16'
ffi_basic_types['gint32']  = 'i32'
ffi_basic_types['guint32'] = 'u32'
ffi_basic_types['gint64']  = 'i64'
ffi_basic_types['guint64'] = 'u64'

# GIR introspects char pointers as either 'utf8' or 'filename',
# and we'd lose constness mapping those to the FFI pointer type
# '*mut gchar'. Instead, put a direct mapping here.
ffi_basic_types['const gchar*'] = '*const gchar'
ffi_basic_types['const char*']  = '*const gchar'

# Workaround for gobject-introspection bug #756009
ffi_basic_types['gchar**'] = '*mut *mut gchar'
ffi_basic_types['char**']  = '*mut *mut gchar'
ffi_basic_types['const gchar**'] = '*mut *const gchar'
ffi_basic_types['const char**']  = '*mut *const gchar'
ffi_basic_types['const gchar* const*'] = '*const *const gchar'
ffi_basic_types['const char* const*']  = '*const *const gchar'

# Another lossy mapping performed by GIR scanner is transmutation
# of OS-specific types to some guess at their built-in C type
# representation. We can do better and resolve those as libc
# imports. The same lookup works for 'long long' and
# 'unsigned long long'.
libc_types = {}
for t in ('size_t', 'ssize_t', 'time_t', 'off_t', 'pid_t', 'uid_t', 'gid_t',
          'dev_t', 'socklen_t'):
    libc_types[t] = t
libc_types['long long'] = 'c_longlong'
libc_types['unsigned long long'] = 'c_ulonglong'

_ident_pat = re.compile(r'^[A-Za-z_][A-Za-z_0-9]*$')

# Taken from https://github.com/rust-lang/rust/blob/master/src/libsyntax/parse/token.rs
rust_keywords = [
    "as", "break", "crate", "else", "enum", "extern", "false", "fn", "for",
    "if", "impl", "in", "let", "loop", "match", "mod", "move", "mut", "pub",
    "ref", "return", "static", "self", "Self", "struct", "super", "true",
    "trait", "type", "unsafe", "use", "while", "continue", "box", "const",
    "where", "virtual", "proc", "alignof", "become", "offsetof", "priv",
    "pure", "sizeof", "typeof", "unsized", "yield", "do", "abstract", "final",
    "override", "macro",
]

_keyword_pat = re.compile(r'^({})$'.format('|'.join(rust_keywords)))

def is_ident(name):
    """Check if the name is a valid Rust identifier.

    Currently, we only regard ASCII identifiers to be valid.
    If someone spots a non-ASCII identifier in GIR, alert the headquarters.
    """
    return bool(_ident_pat.match(name)) and not bool(_keyword_pat.match(name))

def sanitize_ident(name):
    """Modify the name to be a valid Rust identifier.

    :param:`name` must already consist of ASCII alphanumerics and start
    with an ASCII letter or an underscore, otherwise a `ValueError` is
    raised.
    If the name happens to be a Rust keyword, append an underscore.

    This function can be used as a filter in Mako templates.

    :param name: the name string
    :return: a string with the sanitized name
    """
    if not _ident_pat.match(name):
        raise ValueError('the name "{}" is not a valid Rust identifier'.format(name))
    if _keyword_pat.match(name):
        return name + '_'
    return name

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

class ConsistencyError(Exception):
    """Raised when an inconsistency has been found in introspection data.
    """
    pass

class Crate(object):
    """Information for a Rust crate.

    Typically, a crate corresponds to a GObject introspection namespace.
    """

    def __init__(self, name, local_name=None, namespace=None):
        assert is_ident(name), 'crate name "{}" is not an identifier'.format(name)
        self.name = name
        if local_name is not None:
            assert is_ident(local_name), 'crate import name "{}" is not an identifier'.format(local_name)
            self.local_name = local_name
        else:
            self.local_name = name
        self.namespace = namespace

_ptr_const_patterns = (
    re.compile(r'^(?P<deref_type>.*[^ ]) +const *\*$'),
    re.compile(r'^const +(?P<deref_type>.*[^* ]) *\*$')
)
_ptr_mut_pattern = re.compile(r'^(?P<deref_type>.*[^ ]) *\*$')

def _unwrap_pointer_ctype(ctype, allow_const=True):
    if allow_const:
        for pat in _ptr_const_patterns:
            match = pat.match(ctype)
            if match:
                return ('*const ', match.group('deref_type'))
    match = _ptr_mut_pattern.match(ctype)
    if match:
        return ('*mut ', match.group('deref_type'))

    if allow_const:
        message = 'expected pointer syntax in C type "{}"'
    else:
        message = 'expected non-const pointer syntax in C type "{}"'
    raise MappingError(message.format(ctype))

def _normalize_call_signature_ctype(type_container):
    ctype = type_container.type.ctype
    if (isinstance(type_container, ast.Parameter)
        and type_container.direction in (ast.PARAM_DIRECTION_OUT,
                                         ast.PARAM_DIRECTION_INOUT)):
        return _unwrap_pointer_ctype(ctype, allow_const=False)[1]
    return ctype

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
        local_name = sanitize_ident(namespace.name.lower())
        if local_name == 'libc':
            local_name = 'libc_'
        return Crate(name, local_name, namespace)

    def _register_namespace(self, namespace):
        if namespace == self.crate.namespace:
            return
        name = namespace.name
        if name not in self._extern_crates:
            crate = self._create_crate(namespace)
            self._extern_crates[name] = crate

    def resolve_type(self, typedesc, transformer):
        """Resolve type imports for a type description.

        If the type signature refers to a type defined in another
        namespace, this method ensures that an extern crate record
        corresponding to the namespace exists in `self`.

        Most fundamental types are mapped to their namesakes defined
        in crate ``gtypes`` and hence don't need any specific imports,
        provided that the definitions from ``gtypes`` are glob-imported
        in the generated code. However, some exotic types,
        such as the Rust representation of ``long long``,
        are imported from ``libc`` as they don't have a conventional
        GLib name that would rule out potential name conflicts.

        This method is not suitable for type descriptions in function
        parameters or return values due to dependency on the context
        present there. Use method:`resolve_call_signature_type` with
        type container objects in the signature of a function.

        :param typedesc: an instance of :class:`ast.Type`
        :param transformer: the `grust.gi.Transformer` holding the parsed GIR
        """
        return self._resolve_type_internal(typedesc, typedesc.ctype,
                                           transformer)

    def resolve_call_signature_type(self, type_container, transformer):
        """Resolve type imports for a function parameter or a return value.

        This works like :method:`resolve_type`, with the difference that
        the C type attribute of the GIR typenode may need to be
        parsed to get at the actual value type. This is the case when the
        type is given for an output or an inout parameter.

        :param type_container: an instance of :class:`ast.TypeContainer`
        :param transformer: the `grust.gi.Transformer` holding the parsed GIR
        """
        actual_ctype = _normalize_call_signature_ctype(type_container)
        return self._resolve_type_internal(type_container.type, actual_ctype,
                                           transformer)

    def _resolve_type_internal(self, typedesc, actual_ctype, transformer):
        if actual_ctype in ffi_basic_types:
            return

        if isinstance(typedesc, ast.Array):
            self._resolve_array(typedesc, transformer)
        elif isinstance(typedesc, ast.List):
            self._resolve_giname(typedesc.name, transformer)
        elif isinstance(typedesc, ast.Map):
            self._resolve_giname('GLib.HashTable', transformer)
        elif typedesc.target_fundamental:
            self._resolve_fundamental_type(typedesc.target_fundamental,
                                           actual_ctype)
        elif typedesc.target_giname:
            self._resolve_giname(typedesc.target_giname, transformer)
        else:
            raise MappingError("can't represent type {}".format(typedesc))

    def _resolve_fundamental_type(self, typename, ctype):
        if self._crate_libc is not None:
            return
        if ctype in libc_types:
            self._crate_libc = Crate('libc')

    def _resolve_giname(self, name, transformer):
        typenode = transformer.lookup_giname(name)
        if not typenode:
            raise ConsistencyError('reference to undefined type {}'.format(name))
        self._register_namespace(typenode.namespace)

    def _resolve_array(self, typedesc, transformer):
        if typedesc.array_type == ast.Array.C:
            self.resolve_type(typedesc.element_type, transformer)
        else:
            self._resolve_giname(typedesc.array_type, transformer)

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

    def _map_type(self, typedesc, actual_ctype=None):
        if actual_ctype is None:
            actual_ctype = typedesc.ctype

        if actual_ctype in ffi_basic_types:
            # If the C type for anything is usable directly in FFI,
            # that's all we need
            return ffi_basic_types[actual_ctype];

        if isinstance(typedesc, ast.Array):
            return self._map_array(typedesc, actual_ctype)
        elif isinstance(typedesc, ast.List):
            return self._map_list_type(typedesc.name, actual_ctype)
        elif isinstance(typedesc, ast.Map):
            return self._map_hash_table(actual_ctype)
        elif typedesc.target_fundamental:
            return self._map_fundamental_type(typedesc.target_fundamental,
                                              actual_ctype)
        elif typedesc.target_giname:
            return self._map_introspected_type(typedesc.target_giname,
                                               actual_ctype)
        else:
            raise MappingError('cannot represent type {}'.format(typedesc))

    def _map_fundamental_type(self, typename, ctype):
        if ctype in libc_types:
            assert self._libc_crate, 'the fundamental type "{}" should have been resolved first'.format(typename)
            return '{crate}::{name}'.format(
                    crate=self._libc_crate.local_name,
                    name=libc_types[ctype])
        elif typename in ffi_basic_types:
            return ffi_basic_types[typename]
        elif typename in ('utf8', 'filename'):
            return '*mut gchar'
        else:
            raise MappingError('unsupported fundamental type "{}"'.format(typename))

    def _map_introspected_type(self, giname, ctype):
        if ctype.endswith('*'):
            (ptr_prefix, value_ctype) = _unwrap_pointer_ctype(ctype)
        else:
            ptr_prefix = ''
            value_ctype = ctype
        if not is_ident(value_ctype):
            raise MappingError('C type "{}" does not map to a valid Rust identifier'.format(ctype))
        if '.' not in giname:
            crate = self.crate
        else:
            ns_name = giname.split('.', 1)[0]
            if ns_name == self.crate.namespace.name:
                crate = self.crate
            elif ns_name in self._extern_crates:
                crate = self._extern_crates[ns_name]
            else:
                assert False, '{} does not refer to a defined namespace; has the type been resolved?'.format(giname)
        if crate == self.crate:
            return '{ptr}{name}'.format(
                    ptr=ptr_prefix, name=value_ctype)
        else:
            return '{ptr}{crate}::{name}'.format(
                    ptr=ptr_prefix, crate=crate.local_name, name=value_ctype)

    def _map_array(self, array, actual_ctype):
        if array.array_type == ast.Array.C:
            (rust_ptr, element_ctype) = _unwrap_pointer_ctype(actual_ctype)
            return (rust_ptr +
                    self._map_type(array.element_type, element_ctype))
        else:
            (rust_ptr, array_ctype) = _unwrap_pointer_ctype(actual_ctype)
            assert (array.array_type.startswith('GLib.')
                    and array_ctype.startswith('G')
                    and array.array_type[5:] == array_ctype[1:]), \
                    'the array GI type "{}" and C type "{}" do not match'.format(
                        array.array_type, array_ctype)
            return (rust_ptr +
                    self._map_introspected_type(array.array_type, array_ctype))

    def _map_list_type(self, typename, ctype):
            (rust_ptr, item_ctype) = _unwrap_pointer_ctype(ctype)
            assert (typename.startswith('GLib.')
                    and item_ctype.startswith('G')
                    and typename[5:] == item_ctype[1:]), \
                    'the list GI type "{}" and C type "{}" do not match'.format(
                        typename, item_ctype)
            return (rust_ptr +
                    self._map_introspected_type(typename, item_ctype))

    def _map_hash_table(self, ctype):
            (rust_ptr, deref_ctype) = _unwrap_pointer_ctype(ctype)
            assert deref_ctype == 'GHashTable'
            return (rust_ptr +
                    self._map_introspected_type('GLib.HashTable', deref_ctype))

    def map_aliased_type(self, alias):
        """Return the Rust FFI type for the target type of an alias.

        :param alias: an object of :class:`ast.Alias`
        :return: a string with Rust syntax referring to the type
        """
        return self._map_type(alias.target)