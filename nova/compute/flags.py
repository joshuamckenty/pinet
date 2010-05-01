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
                        abspath('libvirt.xml.template'),
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