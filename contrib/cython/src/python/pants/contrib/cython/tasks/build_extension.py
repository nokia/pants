from __future__ import (absolute_import, division, generators, nested_scopes, print_function,
                        unicode_literals, with_statement)

import logging
import multiprocessing
import os
import shutil
from distutils.core import setup

from pants.backend.python.targets.python_library import PythonLibrary
from pants.task.simple_codegen_task import SimpleCodegenTask
from pants.util.dirutil import safe_walk, safe_mkdir
from pex.compatibility import to_bytes

from pants.contrib.cython.gen_utils import copy_package_structure, chdir, make_temp_dir, PROCESS_COUNT
from pants.contrib.cython.python_extension_artifact import ReadableExtension
from pants.contrib.cython.targets.extension_module import ExtensionModuleLibrary
from pants.contrib.cython.targets.wheel_library import WheelLibrary

logger = logging.getLogger(__name__)


class BuildExtension(SimpleCodegenTask):
  class InvalidModuleExtension(Exception):
    pass

  def __init__(self, *args, **kwargs):
    super(BuildExtension, self).__init__(*args, **kwargs)
    self.no_package_ext_modules = []

  def synthetic_target_type(self, target):
    return WheelLibrary

  def is_gentarget(self, target):
    return isinstance(target, ExtensionModuleLibrary) or self.is_extension_artifact(target)

  def is_extension_artifact(self, target):
    return isinstance(target, PythonLibrary) and target.provides and len(
      target.provides.setup_py_keywords.get("ext_modules", [])) > 0

  def execute_codegen(self, target, target_workdir):
    ext_modules, include_dirs = self._get_extensions_and_include_dirs(target, target_workdir)
    self.no_package_ext_modules = [ext for ext in ext_modules if "." not in ext.name]
    if self.no_package_ext_modules:
      if not target.provides:
        raise BuildExtension.InvalidModuleExtension("The target {} contains a module that is not in a package, "
                                                    "but it does not have a 'provides' block, thus it is not possible to build this extension")
      self.prepare_extensions(target, target_workdir, include_dirs)
    else:
      self.build_extensions(ext_modules, target, target_workdir)

    def iter_py_sources():
      for source in target.sources_relative_to_source_root():
        if source.endswith(".py"):
          yield source

    self.copy_source_files(target, target_workdir, iter_py_sources())

  def _inject_synthetic_target(self, target, target_workdir, fingerprint):
    # this part has to run for every target (invalid or not), so it can't go in execute_codegen, which only is
    # called for invalid targets
    if self.no_package_ext_modules:
      target.provides.setup_py_keywords["ext_modules"] = self.no_package_ext_modules
    return super(BuildExtension, self)._inject_synthetic_target(target, target_workdir, fingerprint)

  def _get_extensions_and_include_dirs(self, target, target_workdir):
    ext_sources, include_dirs = self._get_target_relative_extension_sources(target, target_workdir)
    ext_modules = self.create_extensions(target, target_workdir, ext_sources, include_dirs)
    return ext_modules, include_dirs

  def prepare_extensions(self, target, target_workdir, include_dirs):
    """
    Add extensions to the provide block (as ext_modules) so that the build_wheel stage can build them
    Copy code to the target workdir

    """
    self.context.log.info('Preparing extensions for {}'.format(target))
    target_sources = set(self._get_all_target_sources(target))
    target_sources |= set(self._get_include_sources(target, include_dirs))
    self.copy_source_files(target, target_workdir, target_sources)

  def copy_source_files(self, target, target_workdir, target_sources):
    with chdir(target.target_base):
      for src in target_sources:
        safe_mkdir(os.path.join(target_workdir, os.path.dirname(src)))
        shutil.copy(src, os.path.join(target_workdir, src))

  def build_extensions(self, ext_modules, target, target_workdir):
    self.context.log.info('Building extensions for {} in {} processes'.format(target, PROCESS_COUNT))
    with make_temp_dir(dir=target.target_base) as temp_dir:
      script_args = ['build_ext', '--build-temp', to_bytes(temp_dir), '--build-lib', str(target_workdir)]
      with chdir(target.target_base):
        pool = multiprocessing.Pool(processes=PROCESS_COUNT)
        pool.map(_build_ext, [(ext, script_args) for ext in ext_modules])

  def create_extensions(self, target, target_workdir, target_relative_sources, include_dirs):
    if self.is_extension_artifact(target):
      ext_modules = target.provides.ext_modules
    elif target.module_name:
      ext_modules = [self._make_extension(target, target.module_name, target_relative_sources, include_dirs)]
    else:
      ext_modules = [self._make_extension(target, self._get_ext_name(src, target_workdir), [src], include_dirs)
                     for src in target_relative_sources]
    return ext_modules

  def _get_include_sources(self, target, include_dirs):
    includes = []
    ext_module_includes = set()
    for ext_module in target.provides.ext_modules:
      for additional_dir in ext_module.include_dirs:
        ext_module_includes.add(additional_dir)
    for include_dir in include_dirs | ext_module_includes:
      for root, _, files in safe_walk(os.path.join(target.target_base, include_dir)):
        includes.extend([os.path.join(os.path.relpath(root, target.target_base), f) for f in files])
    return includes

  def _get_target_relative_extension_sources(self, target, target_workdir):
    target_sources = target.sources_relative_to_buildroot()
    sources = []
    include_dirs = set()
    for source in target_sources:
      source_rel_path = os.path.relpath(copy_package_structure(target_workdir, source, target.target_base),
                                        target_workdir)
      if os.path.splitext(source_rel_path)[1].lower() in [".c", ".cpp"]:
        sources.append(to_bytes(source_rel_path))
        include_dirs.add(to_bytes(os.path.dirname(source_rel_path)))
    return sources, include_dirs

  def _get_all_target_sources(self, target):
    target_sources = list(target.sources_relative_to_source_root())
    for ext_module in target.provides.ext_modules:
      target_sources.extend(ext_module.sources)
    return target_sources

  def _make_extension(self, target, module_name, sources, include_dirs):
    return ReadableExtension(name=to_bytes(module_name), sources=sources, extra_compile_args=["-Os"],
                             include_dirs=list(include_dirs), define_macros=target.define_macros,
                             libraries=target.libraries)

  def _get_ext_name(self, source_rel_path, target_workdir):
    file_name, package_path = self._get_package_path(source_rel_path, target_workdir)
    module_name = os.path.splitext(file_name)[0]
    return ".".join(package_path.split(os.sep) + [module_name]) if package_path else module_name

  def _get_package_path(self, source_rel_path, target_workdir):
    package_path, file_name = os.path.split(source_rel_path)
    while package_path and not self._is_package(os.path.join(target_workdir, package_path)):
      package_path, _ = os.path.split(package_path)
    return file_name, package_path

  def _do_validate_sources_present(self, target):
    if self.is_extension_artifact(target):
      return True
    else:
      return super(BuildExtension, self)._do_validate_sources_present(target)

  @classmethod
  def _is_package(cls, path):
    return path != "" and "__init__.py" in os.listdir(path)


def _build_ext(args):
  ext, script_args = args
  setup(
    script_name="setup.py",
    script_args=script_args,
    ext_modules=[ext]
  )
