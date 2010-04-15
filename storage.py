"""
Pinet Storage manages creating, attaching, detaching, and destroying persistent storage volumes, ala EBS.
Currently uses iSCSI.
"""

import logging
import subprocess
import random
import exception

from utils import runthis
import calllib
import datastore

import contrib
import flags

from tornado import ioloop
from twisted.internet import defer

FLAGS = flags.FLAGS
flags.DEFINE_string('storage_dev', '/dev/sdb1', 'Physical device to use for volumes')
flags.DEFINE_string('volume_group', 'pinet-volumes', 'Name for the VG that will contain exported volumes')
flags.DEFINE_string('aoe_eth_dev', 'br0', 'Which device to export the volumes on')
flags.DEFINE_boolean('fake_storage', False, 'Should we make real storage volumes to attach?')

KEEPER = datastore.keeper(prefix="storage")

class BlockStore(object):
    """ The BlockStore is in charge of iSCSI volumes and exports."""

    def __init__(self):
        super(BlockStore, self).__init__()
        self.volume_class = Volume
        if FLAGS.fake_storage:
            self.volume_class = FakeVolume
        self._init_volume_group()
        pass

    def create_volume(self, size):
        logging.debug("Creating volume of size: %s" % (size))
        volume = self.volume_class(size = size)
        self._restart_exports()
        return volume
        
    def get_volume(self, volume_id):
        return self.volume_class(volume_id = volume_id)

    def delete_volume(self, volume_id):
        logging.debug("Deleting volume with id of: %s" % (volume_id))
        return self.get_volume(volume_id).delete()

    def attach_volume(self, volume_id, instance_id, mountpoint):
        self.volume_class(volume_id).attach(instance_id, mountpoint)
        self.report_state()

    def detach_volume(self, volume_id):
        self.volume_class(volume_id).detach()
        self.report_state()

    def describe_volumes(self):
        set = []
        for volume_id in self.loop_volumes():
            vol = self.volume_class(volume_id = volume_id)
            set.append({"item": 
                           {"volumeId": volume_id, 
                            "size" : vol.get_size(), 
                            "aoe_device" : vol.get_aoe_device(),
                            "availabilityZone" : "pinet", 
                            "status" : vol.get_status(), 
                            "createTime" : "1", 
                            "attachmentSet" : []}})
        return {"volumeSet" : set}

    def loop_volumes(self):
        for lv in subprocess.Popen(["sudo", "lvs", "--noheadings"], stdout=subprocess.PIPE).communicate()[0].split("\n"):
            if len(lv.split(" ")) > 1:
                yield lv.split(" ")[2]

    def report_state(self):
        logging.debug("Reporting State")
        calllib.cast("cloud",  {"method": "update_state", "args" : {"topic": "volumes", "value": self.describe_volumes()}}) 

    def _restart_exports(self):
        runthis("Setting exports to auto: %s", "sudo vblade-persist auto all")
        runthis("Starting all exports: %s", "sudo vblade-persist start all")
        
    def _init_volume_group(self):
        runthis("PVCreate returned: %s", "sudo pvcreate %s" % (FLAGS.storage_dev))
        runthis("VGCreate returned: %s", "sudo vgcreate %s %s" % (FLAGS.volume_group, FLAGS.storage_dev))


class FakeBlockStore(BlockStore):
    def __init__(self):
        super(FakeBlockStore, self).__init__()
        self.volumes = []

    def create_volume(self, size):
        volume = super(FakeBlockStore, self).create_volume(size)
        self.volumes.append(volume.volume_id)
        return volume
        
    def delete_volume(self, volume_id):
        rv = super(FakeBlockStore, self).delete_volume(volume_id)
        self.volumes.remove(volume_id)
        return rv
                
    def loop_volumes(self):
        return self.volumes
        
    def _init_volume_group(self):
        pass
    
    def _restart_exports(self):
        pass
    

class Volume(object):
    """Volumes represent a single logical persistent iSCSI target.
    """
    
    def __init__(self, volume_id = None, size = None):
        self.volume_id = None
        self.status = 'unknown'
        self.mountpoint = None
        self.instance_id = None
        self.aoe_device = None
        self.size = 0
        if volume_id:
            self.load(volume_id)
            if self.get_aoe_device() is None:
                # Just make sure there's no data in keeper for dead volumes
                KEEPER[self.volume_id] = None
                raise exception.Error(
                    'Volume does not exist or is not exported: %s' % volume_id)
        if size:
            if self.volume_id:
                raise exception.Error(
                    'Redeclaring size of volume: %s is impossible' % volume_id)
            self._create_volume(size)

    def attach(self, instance_id, mountpoint):
        self.instance_id = instance_id
        self.mountpoint = mountpoint
        self.status = "attached"
        self.save()
        
    def detach(self):
        self.instance_id = None
        self.mountpoint = None
        self.status = "available"
        self.save()

    def save(self):
        KEEPER[self.volume_id] = {'status' : self.get_status(),
                                  'size' : self.size,
                                  'mountpoint' : self.mountpoint,
                                  'instance_id' : self.instance_id,
                                  'aoe_device' : self.aoe_device}

    def load(self, volume_id):
        state = KEEPER[volume_id]
        if state:
            self.status = state['status']
            self.size = state['size']
            self.mountpoint = state['mountpoint']
            self.instance_id = state['instance_id']
            self.aoe_device = state['aoe_device']
            self.volume_id = volume_id

    def get_status(self):
        # TODO: Introspect the etherd data for status re: attached
        self.load(self.volume_id)
        return self.status

    def get_size(self):
        self.load(self.volume_id)
        return self.size

    def delete(self):
        aoe = self.get_aoe_device()
        try:
            self._remove_export()
        except:
            pass
        self._delete_lv()
        
    def get_aoe_device(self):
        for (path, aoe_device) in get_aoe_devices():
            if path == "/dev/%s/%s" % (FLAGS.volume_group, self.volume_id):
                return aoe_device
        return None
        
    def _create_volume(self, size):
        self.size = size
        self.volume_id = 'vol-%s' % (''.join([random.choice('ABCDEFGHIJKLMNOPQRSTUVWXYZ') for x in xrange(10)]))
        self._create_lv(size)
        self._setup_export()
        self.status = "available"
        self.save()

    def _create_lv(self, size):
        runthis("Creating LV: %s", "sudo lvcreate -L %s -n %s %s" % (size, self.volume_id, FLAGS.volume_group))
    
    def _delete_lv(self):
        runthis("Removing LV: %s", "sudo lvremove -f %s/%s" % (FLAGS.volume_group, self.volume_id))

    def _setup_export(self):
        (shelf_id, blade_id) = get_next_aoe_numbers()
        self.aoe_device = "e%s.%s" % (shelf_id, blade_id)
        runthis("Creating AOE export: %s", 
                "sudo vblade-persist setup %s %s %s /dev/%s/%s" % 
                (shelf_id, blade_id, FLAGS.aoe_eth_dev, FLAGS.volume_group, self.volume_id))

    def _remove_export(self):
        runthis("Destroyed AOE export: %s", "sudo vblade-persist destroy %s %s" % (aoe[1], aoe[3]))

class FakeVolume(Volume):
    def delete(self):
        pass
        
    def _create_lv(self, size):
        pass

    def get_aoe_device(self):
        return self.aoe_device
    
    def _setup_export(self):
        # TODO: This may not be good enough?
        self.aoe_device = 'e%s.%s' % (random.choice('0123456'), random.choice('0123456789'))
    

def get_aoe_devices():
    aoes = subprocess.Popen(["sudo", "ls",  "-al", "/dev/etherd/"], stdout=subprocess.PIPE).communicate()[0]
    for aoe in aoes.strip().split("\n"):
        bits = aoe.split(" ")
        yield (bits[-1], bits[-3])

def get_next_aoe_numbers():
    # TODO - Guarantee these are in the right order, and make sure they're only the en.n listings
    aoes = subprocess.Popen(["sudo", "ls",  "-1", "/dev/etherd/"], stdout=subprocess.PIPE).communicate()[0]
    last_aoe = aoes.strip().split("\n")[-1]
    if last_aoe == '':
        last_aoe = 'e0.0'
    shelf_id = int(last_aoe[1])
    blade_id = int(last_aoe[3]) + 1
    if (blade_id > 8):
        shelf_id += 1
        blade_id = 0
    return (shelf_id, blade_id)
        