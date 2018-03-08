from __future__ import (absolute_import, division, generators, nested_scopes, print_function,
                        unicode_literals, with_statement)

from pants.backend.python.targets.python_target import PythonTarget
from pants.base.exceptions import TargetDefinitionException


class WheelLibrary(PythonTarget):
  """A python library that must be built into a wheel before including in a PEX file"""
  def __init__(self, provides=None, *args, **kwargs):
    super(WheelLibrary, self).__init__(provides=provides, *args, **kwargs)
    if not provides:
        raise TargetDefinitionException(self, "Target must provide a valid pants setup_py object in the "
                                              "'provides' field.")
