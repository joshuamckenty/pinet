"""
Pinet Storage manages creating, attaching, detaching, and destroying persistent storage volumes, ala EBS.
Currently uses iSCSI.
"""

import libvirt
import os
import settings
import subprocess
from subprocess import Popen, PIPE
import random


class BlockStore(object):
    """ The BlockStore is in charge of iSCSI volumes and exports."""

    def __init__(self):
        """ Connect to queues and listen for requests for actions. """
        pass

    def create_volume(self, size):
        return Volume(size = size)

    def delete_volume(self, volume_id):
        return Volume(volume_id = volume_id).delete()

    def attach_volume(self, volume_id, instance_id, mountpoint):
        pass

    def detach_volume(self, volume_id):
        pass

    def list_volumes(self):
        for pv in Popen(["sudo", "lvs", "--noheadings"], stdout=PIPE).communicate()[0].split("\n"):
            if len(pv.split(" ")) > 1:
                yield pv.split(" ")[2]



class Volume(object):
    """Volumes represent a single logical persistent iSCSI target.
    """
    
    def __init__(self, volume_id = None, size = None):
        self.volume_id = None
        if volume_id:
            self.volume_id = volume_id
        if size:
            self.setup(size)

    def delete(self):
        aoe = self._get_aoe_numbers()
        runthis("Destroyed AOE export: %s", "sudo vblade-persist destroy %s %s" % (aoe[1], aoe[3]))
        subprocess.call(["sudo", "lvremove", "-f", "%s/%s" % (settings.volume_group, self.volume_id)])
        

    def setup(self, size):
        lvname = ''.join([random.choice('ABCDEFGHIJKLMNOPQRSTUVWXYZ') for x in xrange(10)])
        print "LVName is %s" % (lvname)
        self._create_volume(lvname, size)
    
    def _create_volume_group(self):
        # pvcreate is idempotent
        # for pv in Popen(["pvs", "--nosuffix", "--noheadings", "--units", "g", "--separator", ",", "-o", "+pv_pe_count,pv_pe_alloc_count", ], stdout=PIPE).communicate()[0].split("\n"):
        #    if pv == settings.storage_dev:
        #        found = True
        #if not found:
        #    subprocess.call(["pvcreate", settings.storage_dev])
        
        print "PVCreate returned: %s" % (subprocess.call(["sudo", "pvcreate", settings.storage_dev]))
        # os.chown("/dev/%s" % (settings.volume_group), os.geteuid(), os.getegid()) 
        print "VGCreate returned: %s" % (subprocess.call(["sudo", "vgcreate", settings.volume_group, settings.storage_dev]))

    def _get_aoe_numbers(self):
        aoes = Popen(["sudo", "ls",  "-al", "/dev/etherd/"], stdout=PIPE).communicate()[0]
        # print "Aoes are %s " % (",".join(aoes))
        for aoe in aoes.strip().split("\n"):
            bits = aoe.split(" ")
            if len(bits) > 11 and bits[12] == "/dev/%s/%s" % (settings.volume_group, self.volume_id):
                return (bits[10])
        


    def _create_volume(self, lvname, size):
        if self.volume_id:
          throw()
        self.volume_id = lvname
        self._create_volume_group()
        subprocess.call(["sudo", "lvcreate", '-L', size, '-n', lvname, settings.volume_group])

    def _get_next_aoe_number(self):
        aoes = Popen(["sudo", "ls",  "-1", "/dev/etherd/"], stdout=PIPE).communicate()[0]
        print "Aoes are %s " % (",".join(aoes))
        last_aoe = aoes.strip().split("\n")[-1]
        print "Last aoe is: '%s'" % (last_aoe)
        return last_aoe

    def _configure_export(self):
        last_aoe = self._get_next_aoe_number()
        shelf_id = int(last_aoe[1])
        blade_id = int(last_aoe[3]) + 1
        if (blade_id > 5):
            shelf_id += 1
            blade_id = 0
        runthis("Creating AOE export: %s", "sudo vblade-persist setup %s %s %s /dev/%s/%s" % (shelf_id, blade_id, settings.aoe_eth_dev, settings.volume_group, self.volume_id))

    def _restart_exports(self):
        runthis("Setting exports to auto: %s", "sudo vblade-persist auto all")
        runthis("Starting all exports: %s", "sudo vblade-persist start all")
        

def runthis(prompt, cmd):
    print "Running %s" % (cmd)
    print prompt % (subprocess.call(cmd.split(" ")))

if __name__ == "__main__":
    bs = BlockStore()
    for vol in bs.list_volumes():
    	print "Deleting volume %s..." % (vol)
        bs.delete_volume(vol)
    volume = bs.create_volume(size = "5G")
    volume._restart_exports()
    volume._configure_export()
    volume._restart_exports()
