# Cython support for Pants 
This plugin builds cython code and optionally cythonizes python code. It also builds wheel files from python_library and cython_library targets and puts the wheel dist-info folders into the PEX file.

## Prerequisites
You must have a C compiler and appropriate libraries installed. The cython plugin uses the distutils buildext command under the hood, so if that is working you are probably good to go.
## Usage

The cython plugin adds three tasks to the "gen" stage: "cythonize", "buildext", and "build-wheel". In most cases these don't need to be called directly with pants commands, since using "binary" or "test" will call the "gen" stage. It also overwrites the default "setup-py" stage to generate wheel files.
### Compiling python code

The cythonize task has a flag called `--compile-python`. When this flag is specified, plain python files will be cythonized into c files and compiled into objects.
```
./pants --gen-cythonize-compile-python <other options> binary <targets>
```
### Building wheel files

The plugin also overrides the default setup-py goal in order to build wheel files. To build wheel files run:
```
./pants setup-py ::
```
This will build all python_library and cython_library targets into wheel files and put them into the dist/wheelhouse folder.
## Targets

There are three target types added by this plugin: "cython_library", "extension_library", and "wheel_library". The wheel_library and extension_library targets are internal implementation details and should not be used directly.
### cython_library

This target is identical to the python_library target that is built in to Pants, except that it also will compile any cython sources (.pyx or .pyd files) that are specified in the sources field. Additionally, if the `--compile-python` flag is specified, any python files specified in sources will be compiled into C files and then into platform libraries. If that flag is not specified the python files will not be compiled and will just be passed through as python files, same as with the python_library target.