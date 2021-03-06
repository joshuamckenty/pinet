# vim: tabstop=4 shiftwidth=4 softtabstop=4
import contrib
import socket

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

if not FLAGS.has_key('verbose'):
    DEFINE_string('compute_topic', 'compute', 'the topic compute nodes listen on')
    DEFINE_string('storage_topic', 'storage', 'the topic storage nodes listen on')
    DEFINE_bool('fake_libvirt', False,
                      'whether to use a fake libvirt or not')
    DEFINE_bool('verbose', False, 'show debug output')
    DEFINE_boolean('fake_rabbit', False, 'use a fake rabbit')
    DEFINE_bool('fake_network', False, 'should we use fake network devices and addresses')
    DEFINE_bool('fake_users', False, 'use fake users')  
    DEFINE_string('rabbit_host', 'localhost', 'rabbit host')
    DEFINE_integer('rabbit_port', 5672, 'rabbit port')
    DEFINE_string('rabbit_userid', 'guest', 'rabbit userid')
    DEFINE_string('rabbit_password', 'guest', 'rabbit password')
    DEFINE_string('rabbit_virtual_host', '/', 'rabbit virtual host')
    DEFINE_string('control_exchange', 'nova', 'the main exchange to connect to')
    DEFINE_string('ec2_url',
                    'http://10.255.255.1:8773/services/Cloud',
                    'Url to ec2 api server')
                                           
    DEFINE_string('default_image',
                        'ami-25CB1213',
                        'default image to use, testing only')
    DEFINE_string('default_kernel',
                        'aki-EAB510D9',
                        'default kernel to use, testing only')
    DEFINE_string('default_ramdisk',
                        'ari-22F211EF',
                        'default ramdisk to use, testing only')
    DEFINE_string('default_instance_type',
                        'm1.small',
                        'default instance type to use, testing only')
                        
    # UNUSED                        
    DEFINE_string('node_availability_zone',
                        'nova',
                        'availability zone of this node')
    DEFINE_string('node_name',
                        socket.gethostname(),
                        'name of this node')

    DEFINE_string('vpn_image_id', 'ami-A7370FE3', 'AMI for cloudpipe vpn server')
