from __future__ import (absolute_import, division, generators, nested_scopes, print_function,
                        unicode_literals, with_statement)

import json
from hashlib import sha1

import copy
from pants.backend.python.python_artifact import PythonArtifact
from setuptools import Extension as setuptools_ext
from distutils.extension import Extension as distutils_ext


class PythonExtensionArtifact(PythonArtifact):
  def __init__(self, **kwargs):
    super(PythonExtensionArtifact, self).__init__(**kwargs)
    self._kw["ext_modules"] = [ReadableExtension.create(ext_module) for ext_module in
                               (self._kw.get("ext_modules", []))]

  @property
  def ext_modules(self):
    return self._kw["ext_modules"]

  def _compute_fingerprint(self):
    kw_dict = copy.copy(self._kw)
    kw_dict["ext_modules"] = []
    for ext_module in self._kw.get("ext_modules", {}):
      if isinstance(ext_module, (setuptools_ext, distutils_ext)):
        kw_dict["ext_modules"].append(repr(ext_module))

    return sha1(json.dumps((kw_dict, self._binaries),
                           ensure_ascii=True,
                           allow_nan=False,
                           sort_keys=True)).hexdigest()


class ReadableExtension(setuptools_ext):
  EXT_ATTRS = ["name", "sources",
               "include_dirs", "define_macros",
               "undef_macros", "library_dirs", "libraries", "runtime_library_dirs",
               "extra_objects", "extra_compile_args", "extra_link_args",
               "export_symbols", "swig_opts", "depends", "language"]

  @classmethod
  def create(cls, ext_module):
    return ReadableExtension(**{attr: getattr(ext_module, attr)
                                for attr in cls.EXT_ATTRS})

  def __init__(self, **kw):
    setuptools_ext.__init__(self, **kw)
    self._set_kw = kw.keys()

  def __repr__(self):
    return "Extension('{name}', **{build_info})".format(name=self.name,
                                                        build_info={attr: getattr(self, attr) for attr in
                                                                    self._set_kw if attr != "name"})
