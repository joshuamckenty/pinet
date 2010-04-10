"""
Pinet Storage manages creating, attaching, detaching, and destroying persistent storage volumes, ala EBS.
Currently uses iSCSI.
"""

import libvirt
import os
import settings
import subprocess



class BlockStore(object):
    """ The BlockStore is in charge of iSCSI volumes and exports."""

    def __init__(self):
        """ Connect to queues and listen for requests for actions. """
        pass

    def create_volume(self, size):
        return Volume(size)

    def attach_volume(self, volume_id, instance_id, mountpoint):
        pass

    def detach_volume(self, volume_id):
        pass



class Volume(object):
    """Volumes represent a single logical persistent iSCSI target.
    """
    
    def __init__(self, volume_id = None, size = None):
        if volume_id:
            pass
        else if size > 0:
            self.setup(size)
    
    def setup(self, size):
        lvname = ''.join([random.choice('ABCDEFGHIJKLMNOPQRSTUVWXYZ') for x in xrange(6)])
        self._create_volume(lvname, size)
    
    def _create_volume_group(self):
        # pvcreate is idempotent
        # for pv in Popen(["pvs", "--nosuffix", "--noheadings", "--units", "g", "--separator", ",", "-o", "+pv_pe_count,pv_pe_alloc_count", ], stdout=PIPE).communicate()[0].split("\n"):
        #    if pv == settings.storage_dev:
        #        found = True
        #if not found:
        #    subprocess.call(["pvcreate", settings.storage_dev])
        
        subprocess.call(["pvcreate", settings.storage_dev])
        subprocess.call(['vgcreate', settings.volume_group, settings.storage_dev])

    def _create_volume(self, lvname, size):
        self._create_volume_group()
        subprocess.call(['lvcreate', '-L', size, '-n', lvname, settings.volume_group])
        

if __name__ == "__main__":
    print "Creating volume..."
    bs = BlockStore()
    volume = bs.create_volume("10G")