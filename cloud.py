# vim: tabstop=4 shiftwidth=4 softtabstop=4
import logging


class CloudController(object):
    def __init__(self, options):
        self.volumes = None
        self.instances = None
        self.images = None
        self.options = options
        pass

    def list_volumes(self):
        return self.volumes

    def list_instances(self):
        return self.instances

    def list_images(self):
        return self.images

    def update_state(self, topic, value):
        logging.debug("Updating state for %s" % (topic))
        setattr(self, topic, value)



