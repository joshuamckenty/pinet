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
DEFINE_boolean('fake_rabbit', False, 'use a fake rabbit')
DEFINE_string('rabbit_host', 'localhost', 'rabbit host')
DEFINE_integer('rabbit_port', 5672, 'rabbit port')
DEFINE_string('rabbit_userid', 'guest', 'rabbit userid')
DEFINE_string('rabbit_password', 'guest', 'rabbit password')
DEFINE_string('rabbit_virtual_host', '/', 'rabbit virtual host')
DEFINE_string('control_exchange', 'nova', 'the main exchange to connect to')
