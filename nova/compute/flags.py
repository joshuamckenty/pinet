import nova.contrib
from gflags import *
import socket
from nova.utils import abspath


if not FLAGS.has_key('node_topic'):
    DEFINE_string('node_topic', 'node', 'the topic nodes listen on')
    DEFINE_bool('use_s3', True,
                      'whether to get images from s3 or use local copy')
    DEFINE_bool('fake_libvirt', False,
                      'whether to use a fake libvirt or not')
    DEFINE_string('instances_path', abspath('../instances'),
                        'where instances are stored on disk')
    DEFINE_string('bridge_dev', 'eth2',
                        'network device for bridges')
    DEFINE_string('libvirt_xml_template',
                        abspath('compute/libvirt.xml.template'),
                        'template file to use for libvirt xml')
    DEFINE_string('default_image',
                        'ubuntu-karmic-x86_64.img',
                        'default image to use, testing only')
    DEFINE_string('default_kernel',
                        'vmlinuz-karmic-x86_64',
                        'default kernel to use, testing only')
    DEFINE_string('default_ramdisk',
                        'initrd-karmic-x86_64',
                        'default ramdisk to use, testing only')
    DEFINE_string('default_instance_type',
                        'm1.small',
                        'default instance type to use, testing only')

    DEFINE_string('node_name',
                        socket.gethostname(),
                        'name of this node')
    DEFINE_string('node_availability_zone',
                        'nova',
                        'availability zone of this node')
    DEFINE_bool('fake_network', False, 'should we use fake network devices and addresses')
    DEFINE_integer('vlan_start', 2020, 'First VLAN for private networks')
    DEFINE_integer('vlan_end', 2039, 'Last VLAN for private networks')
    DEFINE_integer('network_size', 256, 'Number of addresses in each private subnet') 
    DEFINE_string('public_interface', 'vlan124', 'Interface for public IP addresses')
    DEFINE_string('public_range', '198.10.124.128-198.10.124.191', 'Public IP address block')
    DEFINE_string('private_range', '10.128.0.0/12', 'Private IP address block')
    DEFINE_string('cloudpipe_ami', 'ami-A7370FE3', 'CloudPipe image')
    DEFINE_integer('cloudpipe_start_port', 8000, 'Starting port for mapped CloudPipe external ports')
    