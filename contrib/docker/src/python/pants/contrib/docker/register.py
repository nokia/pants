from __future__ import (absolute_import, division, generators, nested_scopes, print_function,
                        unicode_literals, with_statement)

from pants.build_graph.build_file_aliases import BuildFileAliases
from pants.goal.task_registrar import TaskRegistrar as task

from pants.contrib.docker.targets.docker_image import DockerImage
from pants.contrib.docker.tasks.build_docker_image import BuildDockerImages


def build_file_aliases():
    return BuildFileAliases(
        targets={
            'docker_image': DockerImage
        }
    )


def register_goals():
    task(name="docker", action=BuildDockerImages).install('container')
