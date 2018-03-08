from __future__ import (absolute_import, division, generators, nested_scopes, print_function,
                        unicode_literals, with_statement)

import os

from pants.backend.python.targets.python_library import PythonLibrary
from pants.backend.python.tasks.setup_py import SetupPy
from pants.base.build_environment import get_buildroot
from pants.build_graph.address import Address
from pants.build_graph.resources import Resources
from pants.util.dirutil import safe_open, safe_rmtree, safe_walk, fast_relpath, safe_mkdir, safe_concurrent_rename
from pex.compatibility import to_bytes
from pex.installer import WheelInstaller
from twitter.common.collections import OrderedSet

from pants.contrib.cython.python_extension_artifact import ReadableExtension
from pants.contrib.cython.targets.wheel_library import WheelLibrary


class BuildWheel(SetupPy):
  """
  Builds an unzipped wheel with a .dist-info directory as well as the packages and modules.
  Any extensions are built as well

  This class is a horrible mash-up of SetupPy and SimpleCodegenTask
  """
  SOURCE_ROOT = b'.'
  WHEEL_ARCHIVES = "wheel_archives"
  C_SOURCE_EXTENSIONS = [".c", ".h", ".cpp", ".hpp", ".pyx"]

  @property
  def cache_target_dirs(self):
    return True

  @classmethod
  def is_wheel_library(cls, target):
    return isinstance(target, WheelLibrary)

  @classmethod
  def prepare(cls, options, round_manager):
    pass

  @classmethod
  def product_types(cls):
    return [cls.WHEEL_ARCHIVES]

  @classmethod
  def find_packages(cls, chroot, log=None):
    packages, namespace_packages, resources = super(BuildWheel, cls).find_packages(chroot, log=log)
    # kind of a hack to filter out extension source files from the resources dict
    new_resources = {}
    for pkg, file_list in resources.items():
      new_file_list = [fname for fname in file_list if
                       os.path.splitext(fname)[1].lower() not in cls.C_SOURCE_EXTENSIONS]
      if new_file_list:
        new_resources[pkg] = new_file_list
    resources = new_resources
    return packages, namespace_packages, resources

  def exported_targets(self):
    # Copied from an inline method (ugh...) in SetupPy.execute

    preliminary_targets = set(t for t in self.context.targets(self.has_provides))
    targets = set(preliminary_targets)
    for t in self.context.targets():
      # A non-codegen target has derived_from equal to itself, so we check is_original
      # to ensure that the synthetic targets take precedence.
      # We check that the synthetic target has the same "provides" as the original, because
      # there are other synthetic targets in play (e.g., resources targets) to which this
      # substitution logic must not apply.
      if (t.derived_from in preliminary_targets and not t.is_original and
          self.has_provides(t) and t.provides == t.derived_from.provides):
        targets.discard(t.derived_from)
        targets.add(t)
    return targets

  def execute(self):
    wheel_archives = self.context.products.get_data(self.WHEEL_ARCHIVES, lambda: {})
    with self.invalidated(self.exported_targets(), invalidate_dependents=True) as invalidation_check:
      for vt in invalidation_check.all_vts:
        if not vt.valid:
          self.context.log.debug('cache for {} is invalid, rebuilding'.format(vt.target))
          wheel_name = self.run_bdist_wheel(vt.target, vt.results_dir)
          vt.update()
        else:
          wheel_name = os.listdir(vt.results_dir)[0]
        wheel_path = os.path.join(vt.results_dir, wheel_name)
        wheel_archives[vt.target] = (wheel_name, wheel_path)
        self._inject_synthetic_dependency(vt.target, wheel_path)

  def run_bdist_wheel(self, target, target_workdir):
    using_dummy = self._add_dummy_extension(target)
    setup_dir, reduced_deps = self.create_setup_py(target, target_workdir)
    self._add_extension_import(setup_dir)
    output_dir = os.path.join(target_workdir, "temp")
    safe_mkdir(output_dir)
    # if using a dummy extension, pass a dummy directory as the build_ext bdist-dir so that the dummy .so file
    # will get routed there
    setup_runner = ExplodedWheelInstaller(setup_dir,
                                          bdist_dir=output_dir,
                                          install_dir=os.path.join(setup_dir, "dist"),
                                          build_ext_bdist_dir="dummy" if using_dummy else None)
    self.context.log.info('Running bdist_wheel against {}'.format(setup_dir))
    setup_runner.run()
    wheel_name = os.path.splitext(os.path.basename(setup_runner.find_distribution()))[0]
    new_output_dir = os.path.join(target_workdir, wheel_name)
    safe_concurrent_rename(output_dir, new_output_dir)
    safe_rmtree(setup_dir)
    return wheel_name

  def _add_dummy_extension(self, target):
    """
    Adds a dummy extension if compiled libraries are found but no extensions are specified

    :param target: the target to add the extension for
    :return: True if a dummy extension was added
    """
    using_dummy = False
    c_libs = []
    top_level_package = None
    for src in target.sources_relative_to_source_root():
      ext = os.path.splitext(src)[1]
      if ext in [".so", ".a"]:
        c_libs.append((to_bytes(os.path.basename(src)), {}))
      elif top_level_package is None and os.path.basename(src) == "__init__.py":
        top_level_package = os.path.split(src)[0]
    if c_libs and not target.provides.setup_py_keywords["ext_modules"]:
      # Insane hack to work around the fact that we can't just tell bdist wheel that the wheel is not pure. We
      # ensure that the wheel is platform specific by including a dummy c extension. The extension is given the
      # name of (one of) the existing top level packages so that the "top_level.txt" file will not contain the
      # name of the dummy library
      target.provides.setup_py_keywords["ext_modules"] = [
        ReadableExtension(name=to_bytes(top_level_package or "dummy"), sources=[])]
      using_dummy = True
    return using_dummy

  def _add_extension_import(self, setup_dir):
    with safe_open(os.path.join(setup_dir, "setup.py"), "r+") as f:
      content = f.read()
      f.seek(0)
      f.write("from setuptools import Extension\n")
      f.write(content)

  def _add_dist_info_target(self, target, target_workdir):
    dist_base = '{}-{}.dist-info'.format(target.provides.name.replace("-", "_"), target.provides.version)
    dist_info_dir = os.path.join(target_workdir, dist_base)
    dist_info_sources = [os.path.join(dist_base, fname) for fname in self._find_sources_in_workdir(dist_info_dir)]
    target_base = os.path.relpath(target_workdir, get_buildroot())
    addr = Address(target_base, '{}_dist_info'.format(target.id))

    self.context.add_new_target(addr, Resources, derived_from=target,
                                sources=list(dist_info_sources))
    self.context.build_graph.inject_dependency(target.address, addr)
    return self.context.build_graph.get_target(addr)

  def _get_synthetic_address(self, target, target_workdir):
    synthetic_name = target.id
    sources_rel_path = os.path.relpath(target_workdir, get_buildroot())
    synthetic_address = Address(sources_rel_path, synthetic_name)
    return synthetic_address

  def find_sources(self, target, target_workdir):
    """Determines what sources were generated by the target after the fact.

    This is done by searching the directory where this target's code was generated.

    :param Target target: the target for which to find generated sources.
    :param path target_workdir: directory containing sources for the target.
    :return: A set of filepaths relative to the target_workdir.
    :rtype: OrderedSet
    """
    return OrderedSet(self._find_sources_in_workdir(target_workdir, [".py", ".pyc", ".so", ".a"]))

  def _find_sources_in_workdir(self, target_workdir, filter_ext=None):
    """Returns relative sources contained in the given target_workdir."""
    for root, _, files in safe_walk(target_workdir):
      rel_root = fast_relpath(root, target_workdir)
      for name in files:
        if not filter_ext or os.path.splitext(name)[1] in filter_ext:
          yield os.path.join(rel_root, name)

  def _inject_synthetic_dependency(self, target, target_workdir):
    synthetic_target = self.context.add_new_target(
      address=self._get_synthetic_address(target, target_workdir),
      target_type=PythonLibrary,
      sources=list(self.find_sources(target, target_workdir)),
      dependencies=[self._add_dist_info_target(target, target_workdir)],
      derived_from=target,
      provides=target.provides,
      tags=target.tags,
      scope=target.scope
    )
    build_graph = self.context.build_graph
    # NB(pl): This bypasses the convenience function (Target.inject_dependency) in order
    # to improve performance.  Note that we can walk the transitive dependee subgraph once
    # for transitive invalidation rather than walking a smaller subgraph for every single
    # dependency injected.
    for dependent_address in build_graph.dependents_of(target.address):
      build_graph.inject_dependency(
        dependent=dependent_address,
        dependency=synthetic_target.address,
      )

    build_graph.walk_transitive_dependee_graph(
      build_graph.dependencies_of(target.address),
      work=lambda t: t.mark_transitive_invalidation_hash_dirty(),
    )

    if target in self.context.target_roots:
      self.context.target_roots.append(synthetic_target)

    return synthetic_target

  class DependencyCalculator(SetupPy.DependencyCalculator):

    @classmethod
    def _find_original_target(cls, target):
      original = target
      while original.derived_from != original:
        original = original.derived_from
      return original

    def reduced_dependencies(self, exported_target):
      # SetupPy's reduced dependency calculator does not support gen targets- it thinks dependencies of the
      # generated target are owned by the original target, not the generated target
      # so replace any codegen targets with their synthetic ones
      original_target = self._find_original_target(exported_target)
      # use original target here so that we find any targets that are owned by the original target
      reduced_deps = super(BuildWheel.DependencyCalculator, self).reduced_dependencies(original_target)
      if original_target != exported_target:
        reduced_deps |= super(BuildWheel.DependencyCalculator, self).reduced_dependencies(exported_target)
        if original_target in reduced_deps:
          reduced_deps.remove(original_target)
        remove_deps = OrderedSet()
        for dep in reduced_deps:
          orig_dep = self._find_original_target(dep)
          if orig_dep != dep and orig_dep in reduced_deps:
            remove_deps.add(dep)
        reduced_deps -= remove_deps
      return reduced_deps


class ExplodedWheelInstaller(WheelInstaller):
  """Builds an unzipped (i.e. exploded) wheel file"""

  def __init__(self, source_dir, strict=True, interpreter=None, install_dir=None, bdist_dir=None,
               build_ext_bdist_dir=None):
    """
    :param source_dir:
    :param strict:
    :param interpreter:
    :param install_dir:
    :param bdist_dir:
    :param build_ext_bdist_dir: If set, the build_ext command will be called first with the specified bdist-dir flag set.
                                This can be used to send the build products to a different directory outside the wheel
    """
    super(ExplodedWheelInstaller, self).__init__(source_dir, strict, interpreter, install_dir)
    self.build_ext_bdist_dir = build_ext_bdist_dir
    self.bdist_dir = bdist_dir

  def _setup_command(self):
    cmd = []
    if self.build_ext_bdist_dir:
      cmd.extend(['build_ext', "-b", self.build_ext_bdist_dir])
    cmd.extend(['bdist_wheel', "-b", self.bdist_dir, "-k", "--dist-dir", self._install_tmp])
    return cmd
