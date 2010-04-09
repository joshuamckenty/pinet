"""
Pinet Storage manages creating, attaching, detaching, and destroying persistent storage volumes, ala EBS.
Currently uses iSCSI.
"""

import libvirt
import os
import settings



Class BlockStore(object):
    """ The BlockStore is in charge of iSCSI volumes and exports."""

    def __init__(self):
        """ Connect to queues and listen for requests for actions. """

    def create_volume(self, size):
        pass

    def attach_volume(self, volume_id, instance_id, mountpoint):
        pass

    def detach_volume(self, volume_id):
        pass

