from __future__ import (absolute_import, division, generators, nested_scopes, print_function,
                        unicode_literals, with_statement)

import json
import os

import docker
import shutil
from pants.backend.python.tasks.pex_build_util import has_resources
from pants.task.task import Task
from pants.util.dirutil import safe_mkdtemp

from pants.contrib.docker.targets.docker_image import DockerImage


class BuildDockerImages(Task):
    @classmethod
    def product_types(cls):
        return ['docker_images']

    @classmethod
    def prepare(cls, options, round_manager):
        round_manager.require_data('deployable_archives')

    @staticmethod
    def is_docker_image(target):
        return isinstance(target, DockerImage)

    def execute(self):
        images = self.context.targets(self.is_docker_image)
        docker_client = docker.from_env()
        python_deployable_archive = self.context.products.get('deployable_archives')
        for image_target in images:
            docker_dir = safe_mkdtemp()

            dockerfile_path = os.path.join(docker_dir, os.path.basename(image_target.dockerfile_path))
            shutil.copy(image_target.dockerfile_path, dockerfile_path)
            resource_targets = []
            binary_targets = []
            for tgt in image_target.closure():
                if has_resources(tgt):
                    resource_targets.append(tgt)
                elif python_deployable_archive.has(tgt):
                    binary_targets.append(tgt)
            self.copy_resources(docker_dir, resource_targets)
            self.copy_products(binary_targets, docker_dir, python_deployable_archive)
            for line in docker_client.api.build(path=os.path.dirname(dockerfile_path), rm=True,
                                                tag=image_target.full_tag,
                                                buildargs=image_target.build_args):
                line_output = json.loads(line)
                if "stream" in line_output:
                    line_output = line_output["stream"].strip("\n")
                self.context.log.debug(str(line_output))
                # if "FAILURE" in line_output:
                #     raise Exception("Failed to build image")

            self.context.log.info('Built {}'.format(image_target.full_tag))
            if image_target.push:
                docker_client.images.push(image_target.full_tag)
                self.context.log.info('Pushed {} to {}'.format(image_target.full_tag, image_target.repository))

    @staticmethod
    def copy_products(binary_targets, docker_dir, products):
        for bin_tgt in binary_targets:
            product_mapping = products.get(bin_tgt)
            for basedir, product_paths in product_mapping.items():
                for path in product_paths:
                    shutil.copy(os.path.join(basedir, path), docker_dir)

    @staticmethod
    def copy_resources(docker_dir, resource_targets):
        for source_tgt in resource_targets:
            for src_path in source_tgt.sources_relative_to_buildroot():
                shutil.copy(src_path, docker_dir)
