# vim: tabstop=4 shiftwidth=4 softtabstop=4
import contrib

from gflags import *

#
# __GLOBAL FLAGS ONLY__
# Define any app-specific flags in their own files, docs at:
# http://code.google.com/p/python-gflags/source/browse/trunk/gflags.py#39
#
# You'll likely want to make a "flagfile" to store your frequently used
# local settings in, mine looks like this:
# --fake_libvirt
# --verbose
# --default_image=/home/termie/src/disk_images/karmic-server-uec-amd64.img
# --default_kernel=/home/termie/src/disk_images/vmlinuz-karmic-x86-64
# --default_ramdisk=/home/termie/src/disk_images/initrd.img-karmic-x86_64
# --instances_path=/home/termie/src/disk_images/instances
#
# And I run node_worker.py like this:
# $ python node_worker.py --flagfile flagfile


DEFINE_bool('verbose', False, 'show debug output')
