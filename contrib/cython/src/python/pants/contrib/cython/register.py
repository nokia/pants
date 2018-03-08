from __future__ import (absolute_import, division, generators, nested_scopes, print_function,
                        unicode_literals, with_statement)

from pants.build_graph.build_file_aliases import BuildFileAliases
from pants.goal.task_registrar import TaskRegistrar as task

from pants.contrib.cython.python_extension_artifact import PythonExtensionArtifact
from pants.contrib.cython.targets.cython_library import CythonLibrary
from pants.contrib.cython.targets.extension_module import ExtensionModuleLibrary
from pants.contrib.cython.targets.wheel_library import WheelLibrary
from pants.contrib.cython.tasks.build_extension import BuildExtension
from pants.contrib.cython.tasks.build_wheel import BuildWheel
from pants.contrib.cython.tasks.cythonize import CythonizeSources
from pants.contrib.cython.tasks.package_wheel import PackageWheel


def build_file_aliases():
  return BuildFileAliases(
    targets={
      'cython_library': CythonLibrary,
      'extension_library': ExtensionModuleLibrary,
      'wheel_library': WheelLibrary
    },
    objects={
      'setup_py': PythonExtensionArtifact,
    },
  )


def register_goals():
  # Generate C sources
  task(name='cythonize', action=CythonizeSources).install('gen')
  task(name='buildext', action=BuildExtension).install('gen')
  task(name='build-wheel', action=BuildWheel).install('gen')
  task(name='setup-py', action=PackageWheel).install(replace=True)
