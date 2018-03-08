from __future__ import (absolute_import, division, generators, nested_scopes, print_function,
                        unicode_literals, with_statement)

import os

from pants.base.exceptions import TargetDefinitionException
from pants.base.payload import Payload
from pants.base.payload_field import PrimitiveField
from pants.build_graph.target import Target
from twitter.common.collections import maybe_list


class DockerImage(Target):
    @classmethod
    def alias(cls):
        return "docker_image"

    def __init__(self,
                 address=None,
                 payload=None,
                 source=None,
                 tag=None,
                 repository=None,
                 image_name=None,
                 build_args=None,
                 push=False,
                 **kwargs):
        payload = payload or Payload()
        if not source or not os.path.basename(source) == "Dockerfile":
            raise TargetDefinitionException(self, "'source' must specify a path to a Dockerfile")
        sources = [source]
        payload.add_fields({
            'sources': self.create_sources_field(sources, address.spec_path, key_arg='sources'),
            'tag': PrimitiveField(tag),
            'build_args': PrimitiveField(self._parse_build_args(build_args)),
            'push': PrimitiveField(push),
            'repository': PrimitiveField(repository),
            'image_name': PrimitiveField(image_name)
        })
        super(DockerImage, self).__init__(address=address, payload=payload, **kwargs)

    @property
    def full_tag(self):
        args = []
        if self.repository:
            args.append(self.repository)
        args.append(self.image_name)
        image_name = "/".join(args)
        if self.image_tag:
            image_name = ":".join([image_name, self.image_tag])
        return image_name

    @property
    def image_name(self):
        return self.payload.image_name or self.name

    @property
    def dockerfile_path(self):
        return list(self.sources_relative_to_buildroot())[0]

    @property
    def push(self):
        return self.payload.push

    @property
    def build_args(self):
        return self.payload.build_args

    @property
    def repository(self):
        return self.payload.repository

    @property
    def image_tag(self):
        return self.payload.tag

    @staticmethod
    def _parse_build_args(build_args):
        build_args = maybe_list(build_args or ())
        args_dict = {}
        for arg in build_args:
            argname, sep, argval = arg.partition("=")
            if not sep:
                raise TargetDefinitionException("Invalid arg {}. Please specify args in the format argname=argvalue")
            args_dict[argname.strip()] = argval.strip()
        return args_dict
