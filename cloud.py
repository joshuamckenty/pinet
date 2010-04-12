# vim: tabstop=4 shiftwidth=4 softtabstop=4
import logging
import anyjson
CLOUD_TOPIC='cloud'

class CloudController(object):
    def __init__(self, options):
        self.volumes = None
        self.instances = None
        self.images = None
        self.options = options
        pass

    def describe_volumes(self, request_id, **kwargs):
        return self.volumes

    def describe_instances(self, request_id, **kwargs):
        return self.instances

    def describe_images(self, request_id, **kwargs):
        return self.images

    def update_state(self, topic, value):
        logging.debug("Updating state for %s" % (topic))
        setattr(self, topic, value)



