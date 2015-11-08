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
from .giscanner import ast

ffi_basic_types = {}
for name in ('gpointer', 'gconstpointer', 'gboolean', 'gchar', 'gshort',
             'gushort', 'gint', 'guint', 'glong', 'gulong', 'gsize', 'gssize',
             'gintptr', 'guintptr', 'gfloat', 'gdouble', 'gunichar', 'GType'):
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

unsigned_types = (
    ast.TYPE_USHORT, ast.TYPE_UINT, ast.TYPE_ULONG,
    ast.TYPE_UINT8, ast.TYPE_UINT16, ast.TYPE_UINT32, ast.TYPE_UINT64,
    ast.TYPE_SIZE, ast.TYPE_UINTPTR, ast.TYPE_UNICHAR, ast.TYPE_LONG_ULONG
)

_string_ctypes = set(('gchar*', 'const gchar*', 'char*', 'const char*'))

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
        name += '_'
    return name

_snake_break_pat = re.compile(r'(^|_)([a-zA-Z])')
_digit_letter_pat = re.compile(r'([0-9])([a-z])')

def to_camel_case(name):
    """Converts a snake_case name to CamelCase.

    Also handles some freak cases: "Self" is a Rust keyword, so we get
    "Self_" instead.
    Some enum member names in GIR were converted from prefixed C names
    where the member's own name part starts with a number. These get
    prefixed with an underscore.
    """
    name = _snake_break_pat.sub(
            lambda m: m.group(2).upper(), name)
    name = _digit_letter_pat.sub(
            lambda m: m.group(1) + m.group(2).upper(), name)
    if name[:1].isdigit():
        name = '_' + name
    return sanitize_ident(name)

_nonalpha_pat = re.compile(r'\W')

def _sanitize_crate_name_chars(name):
    return _nonalpha_pat.sub('_', name).lower()

def sys_crate_name(namespace):
    """Generate a conventional ``*_sys`` crate name for a GI namespace.

    The crate name is derived by replacing all non-alphanumeric
    characters in the namespace name and version with underscores
    and converting the name to lowercase, then concatenating the
    resulting strings separated with a ``_`` and appending ``_sys``.

    :param namespace: an instance of :class:`ast.Namespace`.
    :return: a string with the crate name.
    """
    return '{name}_{version}_sys'.format(
            name=_sanitize_crate_name_chars(namespace.name),
            version=_sanitize_crate_name_chars(namespace.version))

_bytestring_escape_pat = re.compile(r'(["\\])')

def escape_bytestring(s):
    """Escape byte string to have valid syntax for Rust bytestring content.
    """
    return _bytestring_escape_pat.sub(r'\\\1', s)

_integer_constant_pat = re.compile(r'-?\d+$')

def validate_integer_value(value):
    """Validate the value of an integer constant.

    The value is expected to be normalized for the GIR format, that is,
    it should be in the decimal base, with an optional minus sign, and no
    whitespace anywhere.

    :param value: constant value as a string
    :raises MappingError: if the value does not follow the format for
                          integer constants
    """
    if not _integer_constant_pat.match(value):
        raise MappingError('Unexpected integer constant value "{}"'
                           .format(value))

class SizedIntTypeInfo(object):
    def __init__(self, bit_width, signed):
        self.bit_width = bit_width
        self.signed = signed

    @classmethod
    def _get_map(cls):
        type_map = {}
        for w in (8, 16, 32, 64):
            suffix = str(w)
            type_map['gint'  + suffix] = cls(bit_width=w, signed=True)
            type_map['guint' + suffix] = cls(bit_width=w, signed=False)
        return type_map

    def fits(self, in_value):
        value = int(in_value)
        w = self.bit_width
        if self.signed:
            return -2**(w - 1) <= value <= 2**(w - 1) - 1
        else:
            return 0 <= value <= 2**w - 1

    def convert(self, in_value):
        value = int(in_value)
        if self.fits(value):
            return in_value
        w = self.bit_width
        if self.signed and value <= 2**w - 1:
            # The value is within the bit width, but out of the range of
            # the target signed type. Do a twos-complement conversion on it.
            value -= 2**w
            return str(value)
        else:
            # The value is out of bit width for the target type.
            # Just emit it as is and hope Rust knows how to deal with it.
            return in_value

sized_int_types = SizedIntTypeInfo._get_map()

def map_constant_value(value_type, value):
    """Return Rust representation of a constant value for a given type.

    The value is as found in the value attribute of a GI constant node.
    :param value_type: an instance of :class:`ast.Type`
    :param value: constant value as a string
    :return: a string with Rust syntax for a constant initializer expression.
    """
    if value_type == ast.TYPE_BOOLEAN:
        if value == 'false':
            return 'FALSE'
        elif value == 'true':
            return 'TRUE'
        else:
            raise MappingError('Unexpected boolean constant value "{}"'
                               .format(value))
    elif value_type.ctype in _string_ctypes:
        return r'b"{}\0"'.format(escape_bytestring(value))
    elif value_type.target_fundamental in sized_int_types:
        validate_integer_value(value)
        typeinfo = sized_int_types[value_type.target_fundamental]
        return typeinfo.convert(value)
    elif value_type in unsigned_types:
        # Sometimes a negative value is given for an unsigned type.
        # This can happen when the value is converted from a bitwise
        # negation of e.g. a combination of flags. Just shoehorn it
        # into the destination type, converting from the largest supported
        # signed integer type for the literal.
        validate_integer_value(value)
        if int(value) < 0:
            return '{}i64 as {}'.format(value, value_type.target_fundamental)
    return value

def node_defines_type(node):
    """Returns true if the AST node defines a type.

    All nodes defining types have attribute ``ctype`` with the
    C language name for the type.
    """
    return isinstance(node, (ast.Alias, ast.Enum, ast.Bitfield, ast.Compound,
                             ast.Class, ast.Interface, ast.Callback))

class MappingError(Exception):
    """Raised when something cannot be represented in Rust.

    This is a soft failure type; it is expected to be handled by
    logging a warning message and culling the top-level node from
    output. Representation failures that occur at the type resolution
    pass, however, can more easily result in inconsistent code and
    tend to indicate serious problems in GIR, so in that pass they
    should be counted as errors, even though the processing may
    continue.
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

class Module(object):
    """Information on a Rust module.

    Module description objects provide a way to segment the crate
    namespace into modules. This is mostly useful for conditional
    compilation of platform-specific symbols.
    """

    def __init__(self,
                 name,
                 cfg=None,
                 ctypes_match=[],
                 symbols_match=[],
                 toplevel_export=True):
        """Construct a module description object.

        :param name: name of the module
        :param cfg: optional content for the ``#[cfg(...)]`` attribute
            of the module
        :param ctypes_match: a :class:`grust.namematch.MatchList` to match
            name patterns of the C type names to export in this module.
        :param symbols_match: a :class:`grust.namematch.MatchList` to match
            name patterns of the C function names to export in this module.
        :param toplevel_export: a flag determining whether the names defined
            in the module should be re-exported at the crate level
        """
        self.name = name
        self.cfg = cfg
        self._ctypes_match = ctypes_match
        self._symbols_match = symbols_match
        self.toplevel_export = toplevel_export
        self.type_defs = []
        self.functions = []
        self.registered_types = []
        self._extern_crates = set()

    extern_crates = property(
            lambda self: iter(self._extern_crates),
            doc="""An iterator over external crates referenced by the module.
                """
        )

    def extract_types(self, nodes, mapper):
        """Extract nodes defining types that belong to this module.

        This method is called with an iterable of AST nodes as the
        first parameter.
        The nodes are filtered accordingly to the construction-time
        parameter ``ctypes_match``. The matching nodes are added to
        the list attribute :attr:`type_defs` of this object.

        :param nodes: an iterable of :class:`ast.Node` objects
        :param mapper: a class:`RawMapper` object to extract information on
                       crate imports
        :return: list of nodes remaining after extraction
        """
        mod_nodes, remainder = self._extract_nodes(
                nodes, self._ctypes_match,
                filter_func=node_defines_type,
                name_func=lambda node: node.ctype)

        for node in mod_nodes:
            self._extern_crates |= mapper.resolve_types_for_node(node)

        self.type_defs.extend(mod_nodes)
        return remainder

    def extract_registered_types(self, nodes):
        """Extract nodes with registered types that belong to this module.

        The nodes defining registered types may or may not be a subset
        of the nodes selected for type definitions.
        This method is called with an iterable of AST nodes as the
        parameter.
        The nodes are filtered accordingly to the construction-time
        parameter ``ctypes_match``. The matching nodes are added to the
        list attribute :attr:`registered_types` of this object.

        :param nodes: an iterable of :class:`ast.Node` objects
        :return: list of nodes remaining after extraction
        """
        mod_nodes, remainder = self._extract_nodes(
                nodes, self._ctypes_match,
                filter_func=lambda node: (
                    isinstance(node, ast.Registered)
                    and hasattr(node, 'ctype')
                ),
                name_func=lambda node: node.ctype)
        self.registered_types.extend(mod_nodes)
        return remainder

    def extract_functions(self, functions, mapper):
        """Extract functions belonging to this module.

        This method is called with an iterable of AST nodes as the
        first parameter.
        The function nodes are filtered accordingly to the
        construction-time parameter ``symbols_match``. The matching
        nodes are added to the list attribute :attr:`functions` of
        this object.

        :param nodes: an iterable of :class:`ast.Node` objects
        :param mapper: a class:`RawMapper` object to extract information on
                       crate imports
        :return: list of nodes remaining after extraction
        """
        mod_functions, remainder = self._extract_nodes(
                functions, self._symbols_match,
                filter_func=lambda node: isinstance(node, ast.Function),
                name_func=lambda node: node.symbol)

        for node in mod_functions:
            self._extern_crates |= mapper.resolve_types_for_node(node)

        self.functions.extend(mod_functions)
        return remainder

    @staticmethod
    def _extract_nodes(nodes, match_list, filter_func, name_func):
        mod_nodes = [node for node in nodes
                     if filter_func(node)
                        and name_func(node) in match_list]
        if len(mod_nodes) == 0:
            remainder = nodes
        else:
            remainder = [node for node in nodes
                         if not filter_func(node)
                            or name_func(node) not in match_list]
        return mod_nodes, remainder

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

_volatile_pattern = re.compile(r'^volatile +(?P<base_type>.*)$')

def _strip_volatile(ctype):
    match = _volatile_pattern.match(ctype)
    if match:
        return match.group('base_type')
    return ctype

def _unwrap_call_signature_ctype(type_container):
    prefix = ''
    ctype = type_container.type.ctype
    if ctype is None:
        raise MappingError('parameter {}: C type attribute is missing'.format(type_container.argname))
    if (isinstance(type_container, ast.Parameter)
        and type_container.direction in (ast.PARAM_DIRECTION_OUT,
                                         ast.PARAM_DIRECTION_INOUT)
        and not type_container.caller_allocates):
        try:
            prefix, ctype = _unwrap_pointer_ctype(ctype, allow_const=False)
        except MappingError as e:
            message = 'parameter {}: {}'.format(type_container.argname, e)
            raise MappingError(message)
    return prefix, _strip_volatile(ctype)

def _is_fixed_size_array(typedesc):
    return (
        isinstance(typedesc, ast.Array)
        and typedesc.array_type == ast.Array.C
        and typedesc.size is not None
    )

class RawMapper(object):
    """State and methods for mapping GI entities to Rust FFI and -sys crates. 

    This class provides a configurable mapping from GObject
    introspection entities to the information on Rust crates, Cargo packages,
    and Rust types generated as FFI bindings for the introspected APIs.

    A mapper object should be used in two passes over the AST: first,
    all types that need to be accounted for in the generated code are
    *resolved* over the associated instance of
    :class:`grust.giscanner.Transformer` with the parsed includes,
    using :meth:`resolve_types_for_node`, :meth:`resolve_type`, or
    :meth:`resolve_call_signature_type`.
    Then, during a code generation pass, *mapping* methods can be called
    to represent the GIR types in Rust syntax, using the cross-crate
    references resolved in the first pass.
    :meth:`extern_crates` provides an iterator over the descriptions
    of ``extern crate`` items that need to be emitted to get the type
    names resolved in the Rust code generated using the mapping methods.
    """

    def __init__(self, transformer):
        self.transformer = transformer
        self.crate = self._create_crate(transformer.namespace)
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
            return set()
        name = namespace.name
        crate = self._extern_crates.get(name)
        if not crate:
            crate = self._create_crate(namespace)
            self._extern_crates[name] = crate
        return {crate}

    def resolve_types_for_node(self, node):
        """Resolve type imports for an AST node.

        If the node definition refers to types defined in other
        namespaces, this method ensures that ``extern crate`` entries
        corresponding to the namespace exist in `self`. The set of
        crates referenced in the node definition is also returned.

        :param node: an instance of :class:`ast.Node`
        :return: Set of :class:`Crate` objects describing the
                 referenced crates.
        """
        if isinstance(node, ast.Callable):
            return self._resolve_callable(node)
        elif isinstance(node, ast.Compound):
            return self._resolve_compound(node)
        elif isinstance(node, ast.Constant):
            return self.resolve_type(node.value_type)
        elif isinstance(node, ast.Alias):
            return self.resolve_type(node.target)
        elif isinstance(node, ast.Interface):
            assert len(node.fields) == 0, \
                'Fields found in interface {}. Strange, huh?'.format(node.name)
        return set()

    def _resolve_callable(self, node):
        if not isinstance(node, (ast.Function, ast.Callback)):
            return set()
        crates = set()
        for param in node.parameters:
            crates |= self.resolve_call_signature_type(param)
        crates |= self.resolve_call_signature_type(node.retval)
        return crates

    def _resolve_compound(self, node):
        crates = set()
        for field in node.fields:
            if field.type is not None:
                crates |= self.resolve_type(field.type)
        return crates

    def resolve_type(self, typedesc):
        """Resolve type imports for a type description.

        If the type signature refers to a type defined in another
        namespace, this method ensures that an ``extern crate`` entry
        corresponding to the namespace exists in `self`. The set of
        crates referenced in the type signature is also returned.

        Most fundamental types are mapped to their namesakes defined
        in crate ``gtypes`` and hence don't need any specific imports,
        provided that the definitions from ``gtypes`` are glob-imported
        in the generated code. However, some exotic types,
        such as the Rust representation of ``long long``,
        are disambiguated with the import path of ``libc``, as they
        don't have a conventional GLib name that would rule out potential
        namespace collisions.

        This method is not suitable for type descriptions in function
        parameters or return values due to dependency on the context
        present there. Use method:`resolve_call_signature_type` with
        type container objects in the signature of a function.

        :param typedesc: an instance of :class:`ast.Type`
        :return: Set of :class:`Crate` objects describing the
                 referenced crates.
        """
        assert isinstance(typedesc, ast.Type)
        actual_ctype = _strip_volatile(typedesc.ctype)
        return self._resolve_type_internal(typedesc, actual_ctype)

    def resolve_call_signature_type(self, type_container):
        """Resolve type imports for a function parameter or a return value.

        This works like :meth:`resolve_type`, with the difference that
        the C type attribute of the GIR typenode may need to be
        parsed to get at the actual value type. This is the case when the
        type is given for an output or an inout parameter.

        :param type_container: an instance of :class:`ast.TypeContainer`
        :return: Set of :class:`Crate` objects describing the
                 referenced crates.
        """
        assert isinstance(type_container, ast.TypeContainer)
        actual_ctype = _unwrap_call_signature_ctype(type_container)[1]
        return self._resolve_type_internal(type_container.type, actual_ctype)

    def _resolve_type_internal(self, typedesc, actual_ctype):
        if actual_ctype in ffi_basic_types:
            return set()

        if isinstance(typedesc, ast.Array):
            return self._resolve_array(typedesc, actual_ctype)
        elif isinstance(typedesc, ast.List):
            return self._resolve_giname(typedesc.name)
        elif isinstance(typedesc, ast.Map):
            return self._resolve_giname('GLib.HashTable')
        elif typedesc.target_fundamental:
            return self._resolve_fundamental_type(typedesc.target_fundamental,
                                                  actual_ctype)
        elif typedesc.target_giname:
            return self._resolve_giname(typedesc.target_giname)
        else:
            raise MappingError("can't represent type {}".format(typedesc))

    def _resolve_fundamental_type(self, typename, ctype):
        crates = set()
        if ctype in libc_types:
            if self._crate_libc is None:
                self._crate_libc = Crate('libc')
            crates.add(self._crate_libc)
        return crates

    def _resolve_giname(self, name):
        typenode = self.transformer.lookup_giname(name)
        if not typenode:
            raise ConsistencyError('reference to undefined type {}'.format(name))
        return self._register_namespace(typenode.namespace)

    def _resolve_array(self, typedesc, actual_ctype):
        if typedesc.array_type == ast.Array.C:
            if typedesc.size is None:
                element_ctype = _unwrap_pointer_ctype(actual_ctype)[1]
            else:
                element_ctype = typedesc.element_type.ctype
            return self._resolve_type_internal(typedesc.element_type,
                                               element_ctype)
        else:
            return self._resolve_giname(typedesc.array_type)

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

    def _lookup_giname(self, giname):
        if '.' in giname:
            ns_name, nqname = giname.split('.', 1)
            if ns_name == self.crate.namespace.name:
                crate = self.crate
            else:
                assert ns_name in self._extern_crates, (
                        '{} refers to an unresolved namespace;'
                        + ' has the type been resolved?'
                        ).format(giname)
                crate = self._extern_crates[ns_name]
        else:
            crate = self.crate
            nqname = giname
        assert nqname in crate.namespace.names, (
                '{} is not found in namespace {}'
                ).format(nqname, crate.namespace.name)
        return (crate, nqname)

    def _map_type(self, typedesc, actual_ctype=None, nullable=False):
        if actual_ctype is None and typedesc.ctype is not None:
            actual_ctype = _strip_volatile(typedesc.ctype)
        assert actual_ctype or typedesc.target_giname, 'C type not found for {!r}'.format(typedesc)

        if (actual_ctype in ffi_basic_types
            and not _is_fixed_size_array(typedesc)):
            # If the C type for anything is usable directly in FFI,
            # that's all we need. The C type is bogus on fixed-size arrays
            # though, see gobject-introspection bug 756122.
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
                                               actual_ctype,
                                               nullable=nullable)
        else:
            raise MappingError('cannot represent type {}'.format(typedesc))

    def _map_fundamental_type(self, typename, ctype):
        if ctype in libc_types:
            assert self._crate_libc, 'the fundamental type "{}" should have been resolved first'.format(typename)
            return '{crate}::{name}'.format(
                    crate=self._crate_libc.local_name,
                    name=libc_types[ctype])
        elif typename in ffi_basic_types:
            return ffi_basic_types[typename]
        elif typename in ('utf8', 'filename'):
            return '*mut gchar'
        else:
            raise MappingError('unsupported fundamental type "{}"'.format(typename))

    def _map_introspected_type(self, giname, ctype, nullable=False):
        crate, name = self._lookup_giname(giname)
        ptr_prefix = ''

        if ctype is None:
            # This must be a node with a generated name, injected by
            # g-ir-scanner ro represent an anonymous struct or union
            # in a structure member definition.
            # The generated name should be prefixed and unique enough to
            # avoid namespace conflicts, so just use it as a stand-in.
            ctype = name
        else:
            # There may be up to two levels of pointer indirection:
            # one when the type value is a pointer, and possibly another
            # one when an output parameter lacks annotation, which is
            # always the case with callbacks.
            for _ in range(2):
                if ctype.endswith('*'):
                    (ptr_layer, ctype) = _unwrap_pointer_ctype(ctype)
                    ptr_prefix += ptr_layer
                else:
                    break
        if not is_ident(ctype):
            raise MappingError(
                'C type "{}" ({}) does not map to a valid Rust identifier'
                .format(ctype, giname))

        if crate == self.crate:
            syntax = '{ptr}{name}'.format(
                    ptr=ptr_prefix, name=ctype)
        else:
            syntax = '{ptr}{crate}::{name}'.format(
                    ptr=ptr_prefix, crate=crate.local_name, name=ctype)

        if nullable:
            # Callbacks need special treatment: C function pointer fields
            # can be NULL while Rust extern fns can't.
            # The trick is to use the null pointer optimization of Option.
            typenode = crate.namespace.names[name]
            if isinstance(typenode, ast.Callback):
                return 'Option<{}>'.format(syntax)
        return syntax

    def _map_array(self, array, actual_ctype):
        if array.array_type == ast.Array.C:
            if array.size is None:
                (rust_ptr, element_ctype) = _unwrap_pointer_ctype(actual_ctype)
                return (rust_ptr +
                        self._map_type(array.element_type, element_ctype))
            else:
                return '[{elem_type}; {size}]'.format(
                        elem_type=self._map_type(array.element_type),
                        size=array.size)
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
        assert isinstance(alias, ast.Alias)
        return self._map_type(alias.target)

    def map_constant(self, constant):
        """Return the Rust syntax for the type and the initializer of a constant.

        :param constant: an object of :class:`ast.Constant`
        :return: a tuple of two strings carrying Rust syntax; the first one
                 describes the type, the second one has the initializer
                 expression.
        """
        assert isinstance(constant, ast.Constant)
        value_type = constant.value_type
        value = map_constant_value(value_type, constant.value)
        if value_type.ctype in _string_ctypes:
            # String constants are only defined for convenience, so they
            # can be Rust bytestrings.
            return ("&'static [u8]", value)
        return (self._map_type(value_type), value)

    def map_field_type(self, field):
        """Return the Rust FFI type for a field in a compound type.

        :param field: an object of :class:`ast.Field`
        :return: a string with Rust syntax referring to the type
        """
        assert isinstance(field, ast.Field)
        if field.bits is not None:
            raise MappingError(
                    'cannot represent bit field {}'.format(field.name))
        # Function pointers in structure fields are always considered
        # nullable. So we pass down the nullable flag both when the field
        # type is a name reference and when it's an anonymous callback.
        if not field.type:
            typenode = field.anonymous_node
            if isinstance(typenode, ast.Callback):
                return self.map_callback(typenode, nullable=True)
            raise MappingError(
                'cannot represent anonymous type of field {} ({})'
                .format(field.name, typenode))
        return self._map_type(field.type, nullable=True)

    def map_parameter_type(self, parameter):
        """Return the Rust FFI type syntax for a function parameter.

        :param parameter: an object of :class:`ast.Parameter`
        :return: a string with Rust syntax describing the type
        """
        assert isinstance(parameter, ast.Parameter)
        ptr_prefix, actual_ctype = _unwrap_call_signature_ctype(parameter)
        return (ptr_prefix +
                self._map_type(parameter.type, actual_ctype,
                               nullable=parameter.nullable))

    def map_return_type(self, retval):
        """Return the Rust FFI type syntax for a function's return value.

        :param retval: an object of :class:`ast.Return`
        :return: a string with Rust syntax describing the type
        """
        assert isinstance(retval, ast.Return)
        return self._map_type(retval.type, nullable=retval.nullable)

    def map_callback(self, callback, nullable=False):
        """Return the Rust FFI type syntax for a callback node.

        :param callback: an object of :class:`ast.Callback`
        :param nullable: True if the callback can be nullable
        :return: a string with Rust syntax describing the type
        """
        assert isinstance(callback, ast.Callback)
        param_list = [self.map_parameter_type(param)
                      for param in callback.parameters]
        syntax = 'extern "C" fn ({})'.format(', '.join(param_list))
        if callback.retval.type != ast.TYPE_NONE:
            syntax += ' -> {}'.format(self.map_return_type(callback.retval))
        if nullable:
            return 'Option<{}>'.format(syntax)
        else:
            return syntax
