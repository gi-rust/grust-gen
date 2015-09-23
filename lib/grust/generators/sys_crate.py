from grust.gi import ast
from mako.lookup import TemplateLookup

class SysCrateWriter(object):
    """Generator for -sys crates."""

    def __init__(self, transformer, name_mapper, template_lookup, options):
        self._transformer = transformer
        self._name_mapper = name_mapper
        self._lookup = template_lookup
        self._options = options
        self._imports = {}  # name -> ast.Namespace
        self._transformer.namespace.walk(
            lambda node, chain: self._prepare_walk(node, chain))

    def _get_template_lookup(self, template_dir):
        return TemplateLookup(directories=[template_dir],
                              output_encoding='utf-8')

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
