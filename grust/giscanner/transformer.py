# -*- Mode: Python -*-
# GObject-Introspection - a framework for introspecting GObject libraries
# Copyright (C) 2008  Johan Dahlin
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the
# Free Software Foundation, Inc., 59 Temple Place - Suite 330,
# Boston, MA 02111-1307, USA.
#

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import os
import sys
import subprocess

from . import ast
from . import message
from . import utils
from .cachestore import CacheStore
from .girparser import GIRParser


class TransformerException(Exception):
    pass


class Transformer(object):
    namespace = property(lambda self: self._namespace)

    def __init__(self, namespace, accept_unprefixed=False,
                 identifier_filter_cmd='', symbol_filter_cmd=''):
        self._cachestore = CacheStore()
        self._accept_unprefixed = accept_unprefixed
        self._namespace = namespace
        self._pkg_config_packages = set()
        self._typedefs_ns = {}
        self._parsed_includes = {}  # <string namespace -> Namespace>
        self._includepaths = []
        self._passthrough_mode = False
        self._identifier_filter_cmd = identifier_filter_cmd
        self._symbol_filter_cmd = symbol_filter_cmd

        # Cache a list of struct/unions in C's "tag namespace". This helps
        # manage various orderings of typedefs and structs. See:
        # https://bugzilla.gnome.org/show_bug.cgi?id=581525
        self._tag_ns = {}

    def get_pkgconfig_packages(self):
        return self._pkg_config_packages

    def disable_cache(self):
        self._cachestore = None

    def set_passthrough_mode(self):
        self._passthrough_mode = True

    def _append_new_node(self, node):
        original = self._namespace.get(node.name)
        # Special case constants here; we allow duplication to sort-of
        # handle #ifdef.  But this introduces an arch-dependency in the .gir
        # file.  So far this has only come up scanning glib - in theory, other
        # modules will just depend on that.
        if isinstance(original, ast.Constant) and isinstance(node, ast.Constant):
            pass
        elif original is node:
            # Ignore attempts to add the same node to the namespace. This can
            # happen when parsing typedefs and structs in particular orderings:
            #   typedef struct _Foo Foo;
            #   struct _Foo {...};
            pass
        elif original:
            positions = set()
            positions.update(original.file_positions)
            positions.update(node.file_positions)
            message.fatal("Namespace conflict for '%s'" % (node.name, ),
                          positions)
        else:
            self._namespace.append(node)

    def set_include_paths(self, paths):
        self._includepaths = list(paths)

    def register_include(self, include):
        if include in self._namespace.includes:
            return
        self._namespace.includes.add(include)
        filename = self._find_include(include)
        self._parse_include(filename)

    def register_include_uninstalled(self, include_path):
        basename = os.path.basename(include_path)
        if not basename.endswith('.gir'):
            raise SystemExit("Include path '%s' must be a filename path "
                             "ending in .gir" % (include_path, ))
        girname = basename[:-4]
        include = ast.Include.from_string(girname)
        if include in self._namespace.includes:
            return
        self._namespace.includes.add(include)
        self._parse_include(include_path, uninstalled=True)

    def lookup_giname(self, name):
        """Given a name of the form Foo or Bar.Foo,
return the corresponding ast.Node, or None if none
available.  Will throw KeyError however for unknown
namespaces."""
        if '.' not in name:
            return self._namespace.get(name)
        else:
            (ns, giname) = name.split('.', 1)
            if ns == self._namespace.name:
                return self._namespace.get(giname)
            # Fallback to the main namespace if not a dependency and matches a prefix
            if ns in self._namespace.identifier_prefixes and ns not in self._parsed_includes:
                message.warn(("Deprecated reference to identifier " +
                              "prefix %s in GIName %s") % (ns, name))
                return self._namespace.get(giname)
            include = self._parsed_includes[ns]
            return include.get(giname)

    def lookup_typenode(self, typeobj):
        """Given a Type object, if it points to a giname,
calls lookup_giname() on the name.  Otherwise return
None."""
        if typeobj.target_giname:
            return self.lookup_giname(typeobj.target_giname)
        return None

    # Private

    def _get_gi_data_dirs(self):
        data_dirs = utils.get_system_data_dirs()
        return data_dirs

    def _find_include(self, include):
        searchdirs = self._includepaths[:]
        for path in self._get_gi_data_dirs():
            searchdirs.append(os.path.join(path, 'gir-1.0'))

        girname = '%s-%s.gir' % (include.name, include.version)
        for d in searchdirs:
            path = os.path.join(d, girname)
            if os.path.exists(path):
                return path
        sys.stderr.write("Couldn't find include '%s' (search path: '%s')\n" %
                         (girname, searchdirs))
        sys.exit(1)

    @classmethod
    def parse_from_gir(cls, filename, extra_include_dirs=None):
        self = cls(None)
        if extra_include_dirs is not None:
            self.set_include_paths(extra_include_dirs)
        self.set_passthrough_mode()
        parser = self._parse_include(filename)
        self._namespace = parser.get_namespace()
        del self._parsed_includes[self._namespace.name]
        return self

    def _parse_include(self, filename, uninstalled=False):
        parser = None
        if self._cachestore is not None:
            parser = self._cachestore.load(filename)
        if parser is None:
            parser = GIRParser(types_only=not self._passthrough_mode)
            parser.parse(filename)
            if self._cachestore is not None:
                self._cachestore.store(filename, parser)

        for include in parser.get_namespace().includes:
            if include.name not in self._parsed_includes:
                dep_filename = self._find_include(include)
                self._parse_include(dep_filename)

        if not uninstalled:
            for pkg in parser.get_namespace().exported_packages:
                self._pkg_config_packages.add(pkg)
        namespace = parser.get_namespace()
        self._parsed_includes[namespace.name] = namespace
        return parser

    def _iter_namespaces(self):
        """Return an iterator over all included namespaces; the
currently-scanned namespace is first."""
        yield self._namespace
        for ns in self._parsed_includes.values():
            yield ns

    def _sort_matches(self, val):
        """Key sort which ensures items in self._namespace are last by returning
        a tuple key starting with 1 for self._namespace entries and 0 for
        everythin else.
        """
        if val[0] == self._namespace:
            return 1, val[2]
        else:
            return 0, val[2]

    def _split_c_string_for_namespace_matches(self, name, is_identifier=False):
        if not is_identifier and self._symbol_filter_cmd:
            proc = subprocess.Popen(self._symbol_filter_cmd,
                                    stdin=subprocess.PIPE,
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE,
                                    shell=True)
            _name = name
            name, err = proc.communicate(name)
            if proc.returncode:
                raise ValueError('filter: "%s" exited: %d with error: %s' %
                                 (self._symbol_filter_cmd, proc.returncode, err))

        matches = []  # Namespaces which might contain this name
        unprefixed_namespaces = []  # Namespaces with no prefix, last resort
        for ns in self._iter_namespaces():
            if is_identifier:
                prefixes = ns.identifier_prefixes
            elif name[0].isupper():
                prefixes = ns._ucase_symbol_prefixes
            else:
                prefixes = ns.symbol_prefixes
            if prefixes:
                for prefix in prefixes:
                    if (not is_identifier) and (not prefix.endswith('_')):
                        prefix = prefix + '_'
                    if name.startswith(prefix):
                        matches.append((ns, name[len(prefix):], len(prefix)))
                        break
            else:
                unprefixed_namespaces.append(ns)
        if matches:
            matches.sort(key=self._sort_matches)
            return list(map(lambda x: (x[0], x[1]), matches))
        elif self._accept_unprefixed:
            return [(self._namespace, name)]
        elif unprefixed_namespaces:
            # A bit of a hack; this function ideally shouldn't look through the
            # contents of namespaces; but since we aren't scanning anything
            # without a prefix, it's not too bad.
            for ns in unprefixed_namespaces:
                if name in ns:
                    return [(ns, name)]
        raise ValueError("Unknown namespace for %s '%s'"
                         % ('identifier' if is_identifier else 'symbol', name, ))

    def split_ctype_namespaces(self, ident):
        """Given a StudlyCaps string identifier like FooBar, return a
list of (namespace, stripped_identifier) sorted by namespace length,
or raise ValueError.  As a special case, if the current namespace matches,
it is always biggest (i.e. last)."""
        return self._split_c_string_for_namespace_matches(ident, is_identifier=True)

    def split_csymbol_namespaces(self, symbol):
        """Given a C symbol like foo_bar_do_baz, return a list of
(namespace, stripped_symbol) sorted by namespace match probablity, or
raise ValueError."""
        return self._split_c_string_for_namespace_matches(symbol, is_identifier=False)

    def split_csymbol(self, symbol):
        """Given a C symbol like foo_bar_do_baz, return the most probable
(namespace, stripped_symbol) match, or raise ValueError."""
        matches = self._split_c_string_for_namespace_matches(symbol, is_identifier=False)
        return matches[-1]

    def strip_identifier(self, ident):
        if self._identifier_filter_cmd:
            proc = subprocess.Popen(self._identifier_filter_cmd,
                                    stdin=subprocess.PIPE,
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE,
                                    shell=True)
            proc_ident, err = proc.communicate(ident.encode())
            if proc.returncode:
                raise ValueError('filter: "%s" exited: %d with error: %s' %
                                 (self._identifier_filter_cmd, proc.returncode, err))
            ident = proc_ident.decode('ascii')

        hidden = ident.startswith('_')
        if hidden:
            ident = ident[1:]
        try:
            matches = self.split_ctype_namespaces(ident)
        except ValueError as e:
            raise TransformerException(str(e))
        for ns, name in matches:
            if ns is self._namespace:
                if hidden:
                    return '_' + name
                return name
        (ns, name) = matches[-1]
        raise TransformerException(
            "Skipping foreign identifier '%s' from namespace %s" % (ident, ns.name, ))
        return None

    def _strip_symbol(self, symbol):
        ident = symbol.ident
        hidden = ident.startswith('_')
        if hidden:
            ident = ident[1:]
        try:
            (ns, name) = self.split_csymbol(ident)
        except ValueError as e:
            raise TransformerException(str(e))
        if ns != self._namespace:
            raise TransformerException(
                "Skipping foreign symbol from namespace %s" % (ns.name, ))
        if hidden:
            return '_' + name
        return name

    def _enum_common_prefix(self, symbol):
        def common_prefix(a, b):
            commonparts = []
            for aword, bword in zip(a.split('_'), b.split('_')):
                if aword != bword:
                    return '_'.join(commonparts) + '_'
                commonparts.append(aword)
            return min(a, b)

        # Nothing less than 2 has a common prefix
        if len(list(symbol.base_type.child_list)) < 2:
            return None
        prefix = None
        for child in symbol.base_type.child_list:
            if prefix is None:
                prefix = child.ident
            else:
                prefix = common_prefix(prefix, child.ident)
                if prefix == '':
                    return None
        return prefix

    def _create_enum(self, symbol):
        prefix = self._enum_common_prefix(symbol)
        if prefix:
            prefixlen = len(prefix)
        else:
            prefixlen = 0
        members = []
        for child in symbol.base_type.child_list:
            if child.private:
                continue
            if prefixlen > 0:
                name = child.ident[prefixlen:]
            else:
                # Ok, the enum members don't have a consistent prefix
                # among them, so let's just remove the global namespace
                # prefix.
                name = self._strip_symbol(child)
            members.append(ast.Member(name.lower(),
                                      child.const_int,
                                      child.ident,
                                      None))

        enum_name = self.strip_identifier(symbol.ident)
        if symbol.base_type.is_bitfield:
            klass = ast.Bitfield
        else:
            klass = ast.Enum
        node = klass(enum_name, symbol.ident, members=members)
        node.add_symbol_reference(symbol)
        return node

    def _canonicalize_ctype(self, ctype):
        # First look up the ctype including any pointers;
        # a few type names like 'char*' have their own aliases
        # and we need pointer information for those.
        firstpass = ast.type_names.get(ctype)

        # If we have a particular alias for this, skip deep
        # canonicalization to prevent changing
        # e.g. char* -> int8*
        if firstpass:
            return firstpass.target_fundamental

        if not ctype.endswith('*'):
            return ctype

        # We have a pointer type.
        # Strip the end pointer, canonicalize our base type
        base = ctype[:-1]
        canonical_base = self._canonicalize_ctype(base)

        # Append the pointer again
        canonical = canonical_base + '*'

        return canonical

    def _create_bare_container_type(self, base, ctype=None,
                                    is_const=False, complete_ctype=None):
        if base in ('GList', 'GSList', 'GLib.List', 'GLib.SList'):
            if base in ('GList', 'GSList'):
                name = 'GLib.' + base[1:]
            else:
                name = base
            return ast.List(name, ast.TYPE_ANY, ctype=ctype,
                        is_const=is_const, complete_ctype=complete_ctype)
        elif base in ('GArray', 'GPtrArray', 'GByteArray',
                      'GLib.Array', 'GLib.PtrArray', 'GLib.ByteArray',
                      'GObject.Array', 'GObject.PtrArray', 'GObject.ByteArray'):
            if '.' in base:
                name = 'GLib.' + base.split('.', 1)[1]
            else:
                name = 'GLib.' + base[1:]
            return ast.Array(name, ast.TYPE_ANY, ctype=ctype,
                         is_const=is_const, complete_ctype=complete_ctype)
        elif base in ('GHashTable', 'GLib.HashTable', 'GObject.HashTable'):
            return ast.Map(ast.TYPE_ANY, ast.TYPE_ANY, ctype=ctype, is_const=is_const,
                           complete_ctype=complete_ctype)
        return None

    def create_type_from_ctype_string(self, ctype, is_const=False,
                                      is_parameter=False, is_return=False,
                                      complete_ctype=None):
        canonical = self._canonicalize_ctype(ctype)
        base = canonical.replace('*', '')

        # Special default: char ** -> ast.Array, same for GStrv
        if (is_return and canonical == 'utf8*') or base == 'GStrv':
            bare_utf8 = ast.TYPE_STRING.clone()
            bare_utf8.ctype = None
            return ast.Array(None, bare_utf8, ctype=ctype,
                             is_const=is_const, complete_ctype=complete_ctype)

        fundamental = ast.type_names.get(base)
        if fundamental is not None:
            return ast.Type(target_fundamental=fundamental.target_fundamental,
                        ctype=ctype,
                        is_const=is_const, complete_ctype=complete_ctype)
        container = self._create_bare_container_type(base, ctype=ctype, is_const=is_const,
                                                     complete_ctype=complete_ctype)
        if container:
            return container
        return ast.Type(ctype=ctype, is_const=is_const, complete_ctype=complete_ctype)

    def _create_typedef_compound(self, compound_class, symbol, disguised=False):
        name = self.strip_identifier(symbol.ident)
        assert symbol.base_type
        if symbol.base_type.name:
            tag_name = symbol.base_type.name
        else:
            tag_name = None

        # If the struct already exists in the tag namespace, use it.
        if tag_name in self._tag_ns:
            compound = self._tag_ns[tag_name]
            if compound.name:
                # If the struct name is set it means the struct has already been
                # promoted from the tag namespace to the main namespace by a
                # prior typedef struct. If we get here it means this is another
                # typedef of that struct. Instead of creating an alias to the
                # primary typedef that has been promoted, we create a new Record
                # with shared fields. This handles the case where we want to
                # give structs like GInitiallyUnowned its own Record:
                #    typedef struct _GObject GObject;
                #    typedef struct _GObject GInitiallyUnowned;
                # See: http://bugzilla.gnome.org/show_bug.cgi?id=569408
                new_compound = compound_class(name, symbol.ident, tag_name=tag_name)
                new_compound.fields = compound.fields
                new_compound.add_symbol_reference(symbol)
                return new_compound
            else:
                # If the struct does not have its name set, it exists only in
                # the tag namespace. Set it here and return it which will
                # promote it to the main namespace. Essentially the first
                # typedef for a struct clobbers its name and ctype which is what
                # will be visible to GI.
                compound.name = name
                compound.ctype = symbol.ident
        else:
            # Create a new struct with a typedef name and tag name when available.
            # Structs with a typedef name are promoted into the main namespace
            # by it being returned to the "parse" function and are also added to
            # the tag namespace if it has a tag_name set.
            compound = compound_class(name, symbol.ident, disguised=disguised, tag_name=tag_name)
            if tag_name:
                # Force the struct as disguised for now since we do not yet know
                # if it has fields that will be parsed. Note that this is using
                # an erroneous definition of disguised and we should eventually
                # only look at the field count when needed.
                compound.disguised = True
            else:
                # Case where we have an anonymous struct which is typedef'd:
                #   typedef struct {...} Struct;
                # we need to parse the fields because we never get a struct
                # in the tag namespace which is normally where fields are parsed.
                self._parse_fields(symbol, compound)

        compound.add_symbol_reference(symbol)
        return compound

    def _create_tag_ns_compound(self, compound_class, symbol):
        # Get or create a struct from C's tag namespace
        if symbol.ident in self._tag_ns:
            compound = self._tag_ns[symbol.ident]
        else:
            compound = compound_class(None, symbol.ident, tag_name=symbol.ident)

        # Make sure disguised is False as we are now about to parse the
        # fields of the real struct.
        compound.disguised = False
        # Fields may need to be parsed in either of the above cases because the
        # Record can be created with a typedef prior to the struct definition.
        self._parse_fields(symbol, compound)
        compound.add_symbol_reference(symbol)
        return compound

    def _create_member_compound(self, compound_class, symbol):
        compound = compound_class(symbol.ident, symbol.ident)
        self._parse_fields(symbol, compound)
        compound.add_symbol_reference(symbol)
        return compound

    def create_type_from_user_string(self, typestr):
        """Parse a C type string (as might be given from an
        annotation) and resolve it.  For compatibility, we can consume
both GI type string (utf8, Foo.Bar) style, as well as C (char *, FooBar) style.

Note that type resolution may not succeed."""
        if '.' in typestr:
            container = self._create_bare_container_type(typestr)
            if container:
                typeval = container
            else:
                typeval = self._namespace.type_from_name(typestr)
        else:
            typeval = self.create_type_from_ctype_string(typestr)

        self.resolve_type(typeval)
        if typeval.resolved:
            # Explicitly clear out the c_type; there isn't one in this case.
            typeval.ctype = None
        return typeval

    def _resolve_type_from_ctype_all_namespaces(self, typeval, pointer_stripped):
        # If we can't determine the namespace from the type name,
        # fall back to trying all of our includes.  An example of this is mutter,
        # which has nominal namespace of "Meta", but a few classes are
        # "Mutter".  We don't export that data in introspection currently.
        # Basically the library should be fixed, but we'll hack around it here.
        for namespace in self._parsed_includes.values():
            target = namespace.get_by_ctype(pointer_stripped)
            if target:
                typeval.target_giname = '%s.%s' % (namespace.name, target.name)
                return True
        return False

    def _resolve_type_from_ctype(self, typeval):
        assert typeval.ctype is not None
        pointer_stripped = typeval.ctype.replace('*', '')
        try:
            matches = self.split_ctype_namespaces(pointer_stripped)
        except ValueError:
            return self._resolve_type_from_ctype_all_namespaces(typeval, pointer_stripped)
        for namespace, name in matches:
            target = namespace.get(name)
            if not target:
                target = namespace.get_by_ctype(pointer_stripped)
            if target:
                typeval.target_giname = '%s.%s' % (namespace.name, target.name)
                return True
        return False

    def _resolve_type_from_gtype_name(self, typeval):
        assert typeval.gtype_name is not None
        for ns in self._iter_namespaces():
            node = ns.type_names.get(typeval.gtype_name, None)
            if node is not None:
                typeval.target_giname = '%s.%s' % (ns.name, node.name)
                return True
        return False

    def _resolve_type_internal(self, typeval):
        if isinstance(typeval, (ast.Array, ast.List)):
            return self.resolve_type(typeval.element_type)
        elif isinstance(typeval, ast.Map):
            key_resolved = self.resolve_type(typeval.key_type)
            value_resolved = self.resolve_type(typeval.value_type)
            return key_resolved and value_resolved
        elif typeval.resolved:
            return True
        elif typeval.ctype:
            return self._resolve_type_from_ctype(typeval)
        elif typeval.gtype_name:
            return self._resolve_type_from_gtype_name(typeval)

    def resolve_type(self, typeval):
        if not self._resolve_type_internal(typeval):
            return False

        if typeval.target_fundamental or typeval.target_foreign:
            return True

        assert typeval.target_giname is not None

        try:
            type_ = self.lookup_giname(typeval.target_giname)
        except KeyError:
            type_ = None

        if type_ is None:
            typeval.target_giname = None

        return typeval.resolved

    def resolve_aliases(self, typenode):
        """Removes all aliases from typenode, returns first non-alias
        in the typenode alias chain.  Returns typenode argument if it
        is not an alias."""
        while isinstance(typenode, ast.Alias):
            if typenode.target.target_giname is not None:
                typenode = self.lookup_giname(typenode.target.target_giname)
            elif typenode.target.target_fundamental is not None:
                typenode = typenode.target
            else:
                break
        return typenode
