contrib_plugin(
    name='cython',
    dependencies=[
      'contrib/cython/src/python/pants/contrib/cython/subsystems',
      'contrib/cython/src/python/pants/contrib/cython/targets',
      'contrib/cython/src/python/pants/contrib/cython/tasks',
      'src/python/pants/goal:task_registrar'
    ],
    distribution_name='paantsbuild.pants.contrib.cython',
    description='Cython Pants plugin',
    build_file_aliases=True,
    register_goals=True
)

python_library(
    name='gen_utils',
    sources=['gen_utils.py'],
    dependencies=['src/python/pants/util']
)

python_library(
    name="python_extension_artifact',
    sources=['python_extension_artifact.py'],
    dependencies=['src/python/pants/backend/python:python_artifact']
)
