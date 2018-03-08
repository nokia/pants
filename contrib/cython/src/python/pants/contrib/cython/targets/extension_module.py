from __future__ import (absolute_import, division, generators, nested_scopes, print_function,
                        unicode_literals, with_statement)

from pants.backend.python.targets.python_target import PythonTarget


class ExtensionModuleLibrary(PythonTarget):
  def __init__(self, module_name=None, define_macros=None, libraries=None, *args, **kwargs):
    super(ExtensionModuleLibrary, self).__init__(*args, **kwargs)

    self.module_name = module_name
    self.define_macros = define_macros
    self.libraries = libraries
