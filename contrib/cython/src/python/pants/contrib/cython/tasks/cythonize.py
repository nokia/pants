from __future__ import (absolute_import, division, generators, nested_scopes, print_function,
                        unicode_literals, with_statement)

import logging
import multiprocessing
import os
import shutil

from Cython.Build import cythonize
from pants.task.simple_codegen_task import SimpleCodegenTask

from pants.contrib.cython.gen_utils import copy_package_structure, PROCESS_COUNT
from pants.contrib.cython.subsystems.cython import Cython
from pants.contrib.cython.targets.cython_library import CythonLibrary
from pants.contrib.cython.targets.extension_module import ExtensionModuleLibrary

logger = logging.getLogger(__name__)


class CythonizeSources(SimpleCodegenTask):
  CYTHON_EXTENSIONS = [".pyx", ".pxd"]

  @classmethod
  def register_options(cls, register):
    super(CythonizeSources, cls).register_options(register)
    register('--compile-python', type=bool, default=False, fingerprint=True,
             help='Compile .py files with Cython. If not compiled, the py files are passed through '
                  'as with a normal python_library.')

  @staticmethod
  def build_task_list(target, target_workdir, extension_set):
    tasks = []
    for source in target.sources_relative_to_buildroot():
      _, ext = os.path.splitext(source)
      if os.path.basename(source) != "__init__.py" and ext in extension_set:
        dest_path = os.path.dirname(copy_package_structure(target_workdir, source, target.target_base))
        tasks.append((dest_path, source))
    return tasks

  @classmethod
  def subsystem_dependencies(cls):
    return super(CythonizeSources, cls).subsystem_dependencies() + (Cython,)

  def synthetic_target_type(self, target):
    return ExtensionModuleLibrary

  def is_gentarget(self, target):
    return isinstance(target, CythonLibrary)

  @property
  def cache_target_dirs(self):
    return True

  def execute_codegen(self, target, target_workdir):
    source_extensions = self.CYTHON_EXTENSIONS
    if self.get_options().compile_python:
      source_extensions += [".py"]
    else:
      # pass the python files through untouched
      for source in target.sources_relative_to_buildroot():
        if source.endswith(".py"):
          dest_path = copy_package_structure(target_workdir, source, target.target_base)
          shutil.copy(source, dest_path)

    tasks = self.build_task_list(target, target_workdir, source_extensions)

    if tasks:
      self.context.log.info('Cythonizing {} in {} processes'.format(target, PROCESS_COUNT))
      pool = multiprocessing.Pool(processes=PROCESS_COUNT)
      pool.map(_cythonize_file, tasks)


def _cythonize_file(args):
  dest_path, source = args
  directives = {"always_allow_keywords": True}  # TODO: get from subsystem config
  cythonize(source, compiler_directives=directives)
  # output_path is ignored when passed to cythonize, so need to copy manually
  c_file = os.path.splitext(source)[0] + ".c"
  dest_file = os.path.join(dest_path, os.path.basename(c_file))
  shutil.move(c_file, dest_file)
