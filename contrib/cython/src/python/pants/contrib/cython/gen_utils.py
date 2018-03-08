from __future__ import (absolute_import, division, generators, nested_scopes, print_function,
                        unicode_literals, with_statement)

import tempfile
from contextlib import contextmanager

import logging

import multiprocessing
import os
import shutil
from pants.util.dirutil import safe_mkdir, safe_rmtree

logger = logging.getLogger(__name__)
PROCESS_COUNT = multiprocessing.cpu_count()


def copy_package_structure(target_workdir, source_path, target_root, copy_init=True):
  source_dir, file_name = os.path.split(source_path)
  source_dir = os.path.relpath(source_dir, target_root)
  path = ""
  for subdir in source_dir.split(os.sep):
    path = os.path.join(path, subdir)
    dest_path = os.path.join(target_workdir, path)
    if not os.path.exists(dest_path):
      safe_mkdir(dest_path, clean=True)
      package_init_path = os.path.join(target_root, path, "__init__.py")
      dest_package_init = os.path.join(dest_path, "__init__.py")
      if copy_init and os.path.exists(package_init_path) and not os.path.exists(dest_package_init):
        shutil.copy(package_init_path, dest_package_init)
  return os.path.join(target_workdir, path, file_name)


@contextmanager
def chdir(path):
  cwd = os.getcwd()
  try:
    os.chdir(path)
    yield
  finally:
    os.chdir(cwd)


@contextmanager
def make_temp_dir(suffix="", prefix="tmp", dir=None):
  temp_dir = os.path.abspath(tempfile.mkdtemp(suffix=suffix, prefix=prefix, dir=dir))
  try:
    yield temp_dir
  finally:
    safe_rmtree(temp_dir)
