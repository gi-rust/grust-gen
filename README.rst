The Rust binding generator for GObject introspection is used to produce
mostly-automatically generated code for Rust_ crates that interface with
libraries for which `GObject introspection`_ data is available in GIR XML
format. The generator is written in Python using tools modules developed
in the gobject-introspection project; it uses Mako_ template engine to
generate code from programmable, customizable templates.

Installation requires Python package ``setuptools`` of version 12 or later.
To install the generator from the source tree, change into its root
directory and run ``setup.py``::

  python setup.py install

The ``develop`` command can also be used to set up the tool for in-tree
usage.

.. _Rust: https://www.rust-lang.org/
.. _GObject introspection: https://wiki.gnome.org/Projects/GObjectIntrospection
.. _Mako: http://www.makotemplates.org/
