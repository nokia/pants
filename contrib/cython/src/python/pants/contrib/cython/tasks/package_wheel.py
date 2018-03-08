from __future__ import (absolute_import, division, generators, nested_scopes, print_function,
                        unicode_literals, with_statement)

import os

import shutil
from pants.task.task import Task
from wheel.archive import archive_wheelfile

from pants.contrib.cython.tasks.build_wheel import BuildWheel


class PackageWheel(Task):
  PYTHON_DISTS_PRODUCT = 'python_dists'

  @property
  def cache_target_dirs(self):
    return True

  @classmethod
  def prepare(cls, options, round_manager):
    round_manager.require_data(BuildWheel.WHEEL_ARCHIVES)

  def execute(self):
    wheel_archives = self.context.products.get_data(BuildWheel.WHEEL_ARCHIVES)
    python_dists = self.context.products.get_data(self.PYTHON_DISTS_PRODUCT, lambda: {})
    dist_dir = self.get_options().pants_distdir

    def is_wheel_archive(t):
      return t in wheel_archives

    with self.invalidated(self.context.targets(is_wheel_archive), invalidate_dependents=True) as invalidation_check:
      for vt in invalidation_check.all_vts:
        wheel_name, wheel_location = wheel_archives[vt.target]
        wheel_dest = os.path.join(vt.results_dir, wheel_name)
        if not vt.valid:
          archive_wheelfile(wheel_dest, wheel_location)
          vt.update()
        wheel_dist_path = os.path.join(dist_dir, wheel_name + ".whl")
        shutil.copy(wheel_dest + ".whl", wheel_dist_path)
        python_dists[vt.target] = wheel_dist_path
