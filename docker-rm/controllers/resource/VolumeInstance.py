import logging
from controllers.resource.ResourceInstance import ResourceInstance


class VolumeInstance(ResourceInstance):
    """ Reponsible for running resource instance lifecycles"""

    def __init__(self, network):
        self.logger = logging.getLogger(__name__)
