from __future__ import (absolute_import, division, generators, nested_scopes, print_function,
                        unicode_literals, with_statement)

from pants.subsystem.subsystem import Subsystem


class Cython(Subsystem):
  options_scope = "cython"

  @classmethod
  def register_options(cls, register):
      super(Cython, cls).register_options(register)
