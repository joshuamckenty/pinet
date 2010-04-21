# vim: tabstop=4 shiftwidth=4 softtabstop=4
import logging
import multiprocessing
import os
import random
import shutil
import base64
import StringIO
import sys
import time
from xml.etree import ElementTree

import contrib
import anyjson
import tornado
from tornado import ioloop
from twisted.internet import defer

try:
    import libvirt
except Exception, e:
    logging.warning('no libvirt found')

import exception
import fakevirt
import flags
import partition2disk
import storage
import utils

from utils import runthis
import calllib

from injectkey import inject_key

FLAGS = flags.FLAGS
flags.DEFINE_string('node_topic', 'node', 'the topic nodes listen on')
flags.DEFINE_bool('fake_libvirt', False,
                  'whether to use a fake libvirt or not')
flags.DEFINE_string('instances_path', utils.abspath('../instances'),
                    'where instances are stored on disk')
flags.DEFINE_string('images_path', utils.abspath('../images'),
                    'where images are stored on disk')
flags.DEFINE_string('bridge_dev', 'eth0',
                    'network device for bridges')
flags.DEFINE_string('libvirt_xml_template',
                    utils.abspath('libvirt.xml.template'),
                    'template file to use for libvirt xml')
flags.DEFINE_string('default_image',
                    'ubuntu-karmic-x86_64.img',
                    'default image to use, testing only')
flags.DEFINE_string('default_kernel',
                    'vmlinuz-karmic-x86_64',
                    'default kernel to use, testing only')
flags.DEFINE_string('default_ramdisk',
                    'initrd-karmic-x86_64',
                    'default ramdisk to use, testing only')
flags.DEFINE_string('default_instance_type',
                    'm1.small',
                    'default instance type to use, testing only')

flags.DEFINE_string('node_name',
                    'node_foo',
                    'name of this node')
flags.DEFINE_string('node_availability_zone',
                    'pinet',
                    'availability zone of this node')


INSTANCE_TYPES = {}
INSTANCE_TYPES['m1.small'] = {'memory_mb': 1024, 'vcpus': 1, 'disk_mb': 4096}
INSTANCE_TYPES['m1.medium'] = {'memory_mb': 2048, 'vcpus': 2, 'disk_mb': 4096}
INSTANCE_TYPES['m1.large'] = {'memory_mb': 4096, 'vcpus': 4, 'disk_mb': 4096}
INSTANCE_TYPES['c1.medium'] = {'memory_mb': 1024, 'vcpus': 1, 'disk_mb': 4096}


class GenericNode(object):
    """ Generic Nodes have a libvirt connection """
    def __init__(self, **kwargs):
        super(GenericNode, self).__init__()
    
    def _get_connection(self):
        # TODO(termie): maybe lazy load after initial check for permissions
        # TODO(termie): check whether we can be disconnected
        if FLAGS.fake_libvirt:
            conn = fakevirt.FakeVirtConnection.instance()
        else:
            auth = [[libvirt.VIR_CRED_AUTHNAME, libvirt.VIR_CRED_NOECHOPROMPT], 
                    'root',
                    None]
            conn = libvirt.openAuth('qemu:///system', auth, 0)
            if conn == None:
                logging.error('Failed to open connection to the hypervisor')
                sys.exit(1)
        return conn

    def noop(self):
        return defer.succeed('PONG')
    

class Node(GenericNode):
    """ The node is in charge of running instances.  """

    def __init__(self):
        super(Node, self).__init__()
        """ load configuration options for this node and connect to libvirt """
        self._instances = {}
        self._conn = self._get_connection()
    
    @exception.wrap_exception
    def adopt_instances(self):
        """ if there are instances already running, adopt them """
        instance_names = [self._conn.lookupByID(x).name()
                          for x in self._conn.listDomainsID()]
        for name in instance_names:
            new_inst = Instance.fromName(self._conn, name)
            self._instances[name] = new_inst
        return defer.succeed(len(self._instances))
    
    @defer.inlineCallbacks
    def report_state(self):
        logging.debug("Reporting State")
        instances = []
        rv = yield self.describe_instances()
        instances = {FLAGS.node_name: rv}
        calllib.cast("cloud",  
                            {"method": "update_state",
                             "args" : {"topic": "instances",
                                       "value": instances
                                       }
                             })
    
    @exception.wrap_exception
    def describe_instances(self):
        """ return a dictionary of instances on this node """
        d = {}
        for i in self._instances.values():
            d[i.name] = i.describe()
        return defer.succeed(d)
    
    @exception.wrap_exception
    def run_instance(self, instance_id, **kwargs):
        """ launch a new instance with specified options """
        logging.debug("Starting instance %s..." % (instance_id))
        if instance_id in self._instances:
            raise exception.Error(
                    'attempting to use existing instance_id: %s' % instance_id)
        # TODO(vish) check to make sure the availability zone matches
        new_inst = Instance(self._conn, name=instance_id, **kwargs)
        self._instances[instance_id] = new_inst
        d = new_inst.spawn()
        d.addCallback(lambda x: new_inst)
        return d
    
    @exception.wrap_exception
    def terminate_instance(self, instance_id):
        """ terminate an instance on this machine """
        if instance_id not in self._instances:
            raise exception.Error(
                    'trying to terminate unknown instance: %s' % instance_id)
        d = self._instances[instance_id].destroy()
        d.addCallback(lambda x: self._instances.pop(instance_id))
        return d

    @exception.wrap_exception
    def reboot_instance(self, instance_id):
        """ reboot an instance on this server
        KVM doesn't support reboot, so we terminate and restart """
        if instance_id not in self._instances:
            raise exception.Error(
                    'trying to reboot unknown instance: %s' % instance_id)
        return self._instances[instance_id].reboot()

    @defer.inlineCallbacks
    @exception.wrap_exception
    def get_console_output(self, instance_id):
        """ send the console output for an instance """
        if instance_id not in self._instances:
            raise exception.Error(
                    'trying to get console log for unknown: %s' % instance_id)
        rv = yield self._instances[instance_id].console_output()
        # TODO(termie): this stuff belongs in the API layer, no need to
        #               munge the data we send to ourselves
        output = {"InstanceId" : instance_id,
                  "Timestamp" : "2",
                  "output" : base64.b64encode(rv)}
        defer.returnValue(output)

    @defer.inlineCallbacks
    @exception.wrap_exception
    def attach_volume(self, instance_id = None, aoe_device = None, mountpoint = None):
        runthis("Attached Volume: %s", "sudo virsh attach-disk %s /dev/etherd/%s %s"
                % (instance_id, aoe_device, mountpoint.split("/")[-1]))

    def _init_aoe(self):
        runthis("Doin an AoE discover, returns %s", "sudo aoe-discover")
        runthis("Doin an AoE stat, returns %s", "sudo aoe-stat")
    
    @exception.wrap_exception
    def detach_volume(self, instance_id, mountpoint):
        """ detach a volume from an instance """
        runthis("Detached Volume: %s", "sudo virsh detach-disk %s %s "
                % (instance_id, mountpoint))

class Group(object):
    def __init__(self, group_id):
        self.group_id = group_id

class ProductCode(object):
    def __init__(self, product_code):
        self.product_code = product_code


class Instance(object):

    NOSTATE = 0x00
    RUNNING = 0x01
    BLOCKED = 0x02
    PAUSED = 0x03
    SHUTDOWN = 0x04
    SHUTOFF = 0x05
    CRASHED = 0x06

    def is_pending(self):
        return self.state == Instance.NOSTATE

    def is_destroyed(self):
        return self.state == Instance.SHUTOFF

    def is_running(self):
        return self.state == Instance.RUNNING
    
    def __init__(self, conn, name, **kwargs):
        """ spawn an instance with a given name """
        self._conn = conn
        
        self._s = {}
        
        # TODO(termie): is instance_type that actual name for this?
        size = kwargs.get('instance_type', FLAGS.default_instance_type)
        if size not in INSTANCE_TYPES:
            raise exception.Error('invalid instance type: %s' % size)

        self._s.update(INSTANCE_TYPES[size])

        self._s['name'] = name
        self._s['instance_id'] = name
        self._s['instance_type'] = size
        self._s['mac_address'] = kwargs.get(
                'mac_address', 'uhoh')
        self._s['basepath'] = kwargs.get(
                'basepath', os.path.abspath(os.path.join(FLAGS.instances_path, self.name)))
        self._s['memory_kb'] = int(self._s['memory_mb']) * 1024
        # TODO - Get this from network controller
        self._s['network_name'] = kwargs.get('network_name', 'virbr0')
        # self._s['bridge_dev'] = kwargs.get('bridge_dev', FLAGS.bridge_dev)
        self._s['image_id'] = kwargs.get('image_id', FLAGS.default_image)
        self._s['kernel_id'] = kwargs.get('kernel_id', FLAGS.default_kernel)
        self._s['ramdisk_id'] = kwargs.get('ramdisk_id', FLAGS.default_ramdisk)
        self._s['owner_id'] = kwargs.get('owner_id', None)
        self._s['user_data'] = kwargs.get('user_data', None)
        self._s['ami_launch_index'] = kwargs.get('ami_launch_index', None)
        self._s['launch_time'] = kwargs.get('launch_time', None)
        self._s['reservation_id'] = kwargs.get('reservation_id', None)
        self._s['state'] = Instance.NOSTATE
        self._s['key_data'] = kwargs.get('key_data', None)

        # TODO: we may not need to save the next few
        self._s['groups'] = kwargs.get('security_group', ['default'])
        self._s['product_codes'] = kwargs.get('product_code', [])
        self._s['key_name'] = kwargs.get('key_name', None)
        self._s['addressing_type'] = kwargs.get('addressing_type', None)
        self._s['availability_zone'] = kwargs.get('availability_zone', None)

        #TODO: put real dns items here
        self._s['dns_name'] = kwargs.get('dns_name', 'fixme')
        self._s['private_dns_name'] = kwargs.get('private_dns_name', 'fixme') 

    def toXml(self):
        # TODO(termie): cache?
        libvirt_xml = open(FLAGS.libvirt_xml_template).read()
        xml_info = self._s.copy()
        #xml_info.update(self._s)

        # TODO(termie): lazy lazy hack because xml is annoying
        xml_info['pinet'] = anyjson.serialize(self._s)
        libvirt_xml = libvirt_xml % xml_info

        return libvirt_xml

    @classmethod
    def fromXml(cls, conn, xml):
        parsed = ElementTree.parse(StringIO.StringIO(xml))
        elem = parsed.find('pinet')
        info = anyjson.deserialize(elem.text)
        self = cls(conn, **info)
        self.update_state()
        return self
    
    @classmethod
    def fromName(cls, conn, name):
        """ find the xml file and return fromXml """
        if FLAGS.fake_libvirt:
            raise Exception('this is a bit useless, eh?')

        # TODO(termie): this code is duplicated in __init__
        basepath = os.path.abspath(os.path.join(FLAGS.instances_path, name))
        libvirt_xml = open(os.path.join(basepath, 'libvirt.xml')).read()
        return cls.fromXml(conn, libvirt_xml)

    def _createImage(self, libvirt_xml, conn):
        """ create libvirt.xml and copy files into instance path """          
        try:
            os.makedirs(self._s['basepath'])
        except:
            pass
        try:
            logging.info('Creating image for: %s', self.name)
            f = open(self.basepath('libvirt.xml'), 'w')
            f.write(libvirt_xml)
            f.close()
            if not FLAGS.fake_libvirt:
                # TODO(termie): what to do when this already exists?
                # TODO(termie): clean up on exit?
                shutil.copyfile(self.imagepath(self._s['kernel_id']),
                                self.basepath('kernel'))
                shutil.copyfile(self.imagepath(self._s['ramdisk_id']),
                               self.basepath('ramdisk'))
                if self._s['key_data']:
                    logging.info('Injecting key data into image')
                    shutil.copyfile(self.imagepath(self._s['image_id']),
                               self.basepath('temp'))
                    inject_key(self._s['key_data'], self.basepath('temp'))
                    partition2disk.convert(self.basepath('temp'),
                               self.basepath('disk'))
                    # os.remove(self.basepath('temp'))
                else:
                    partition2disk.convert(self.imagepath(self._s['image_id']),
                               self.basepath('disk'))
            else:
                pass
            logging.info('Done create image for: %s', self.name)
        except Exception, e:
            # TODO(termie): we should try to actually raise the exception
            #               out of this guy
            logging.exception('something is awry in _createImage')
        conn.send("ready")
        return

    @property
    def state(self):
        return self._s['state']

    @property
    def name(self):
        return self._s['name']

    def basepath(self, s=''):
        return os.path.abspath(os.path.join(self._s['basepath'], s))

    def imagepath(self, s=''):
        return os.path.join(FLAGS.images_path, s)

    def describe(self):
        """<DescribeInstancesResponse xmlns="http://ec2.amazonaws.com/doc/2007-08-29">
      <reservationSet>
        <item>
          <reservationId>r-44a5402d</reservationId>
          <ownerId>UYY3TLBUXIEON5NQVUUX6OMPWBZIQNFM</ownerId>
          <groupSet>
            <item>
              <groupId>default</groupId>
            </item>
          </groupSet>
          <instancesSet>
            <item>
              <instanceId>i-28a64341</instanceId>
              <imageId>ami-6ea54007</imageId>
              <instanceState>
                <code>0</code>
                <name>running</name>
              </instanceState>
              <privateDnsName>domU-12-31-35-00-1E-01.compute-1.internal</privateDnsName>
              <dnsName>ec2-72-44-33-4.compute-1.amazonaws.com</dnsName>
              <keyName>example-key-name</keyName>
              <productCodesSet>
                <item><productCode>774F4FF8</productCode></item>
              </productCodesSet>
              <InstanceType>m1.small</InstanceType>
              <launchTime>2007-08-07T11:54:42.000Z</launchTime>             
            </item>
          </instancesSet>
        </item>
      </reservationSet>
    </DescribeInstancesResponse>"""
        return self._s
        """
               {"reservation_set": [{
                        "reservation_id": self._s['reservation_id'],
                        "owner_id" : self._s['owner_id'],
                        "group_set" : [{
                            "group_id" : self._s['group_id']
                        }],
                        "instances_set" : [{
                                "instance_id" : self.name,
                                "image_id" : self._s['image_id'],
                                "instance_state" : {
                                    "code" : self.state,
                                    "name" : Instance.state_names[self.state]
                                },
                                "private_dns_name": 'fixme',
                                "dns_name": 'fixme',
                                "key_name": self._s['key_name'],
                                "product_codes_set" : [{
                                        "product_code" : 'fixme'
                                }],
                                "instance_type": self._s['instance_type'],
                                "launch_time": self._s['launch_time'],
                        }]
                }]}
        """

    def info(self):
        virt_dom = self._conn.lookupByName(self.name)
        (state, max_mem, mem, num_cpu, cpu_time) = virt_dom.info()
        return {'state': state,
                'max_mem': max_mem,
                'mem': mem,
                'num_cpu': num_cpu,
                'cpu_time': cpu_time}

    def update_state(self):
        info = self.info()
        self._s['state'] = info['state']
    
    @exception.wrap_exception
    def destroy(self):
        if self.is_destroyed():
            raise exception.Error('trying to destroy already destroyed'
                                  ' instance: %s' % self.name)

        self._s['state'] = Instance.SHUTDOWN
        
        virt_dom = self._conn.lookupByName(self.name)
        virt_dom.destroy()
        
        d = defer.Deferred()
        
        # TODO(termie): short-circuit me for tests
        timer = ioloop.PeriodicCallback(callback=None, callback_time=500)
        def _wait_for_shutdown():
            try:
                info = self.info()
                if info['state'] == Instance.SHUTDOWN:
                    self._s['state'] = Instance.SHUTDOWN
                    timer.stop()
            except Exception:
                self._s['state'] = Instance.SHUTDOWN
                timer.stop()
            d.callback(None)
        timer.callback = _wait_for_shutdown
        timer.start()
        return d
    
    @defer.inlineCallbacks
    @exception.wrap_exception
    def reboot(self):
        if not self.is_running():
            raise exception.Error(
                    'trying to reboot a non-running'
                    'instance: %s (state: %s)' % (self.name, self.state))
        
        yield self._conn.lookupByName(self.name).destroy()

        self._s['state'] = Instance.NOSTATE
        self._conn.createXML(self.toXml(), 0)
        # TODO(termie): this should actually register a callback to check
        #               for successful boot
        self._s['state'] = Instance.RUNNING
        defer.returnValue(None)
    
    @exception.wrap_exception
    def spawn(self):
        if not self.is_pending():
            raise exception.Error(
                    'trying to spawn a running or terminated'
                    'instance: %s (state: %s)' % (self.name, self.state))

        xml = self.toXml()
        d = defer.Deferred()

        def _launch(fd,events):
            self.ioloop.remove_handler(fd)
            logging.debug("Arrived in _launch, thanks to callback on deferred.")
            logging.debug("Self is %s" % (self))
            self._conn.createXML(self.toXml(), 0)
            # TODO(termie): this should actually register a callback to check
            #               for successful boot
            self._s['state'] = Instance.RUNNING
            d.callback(True)

        self.ioloop = tornado.ioloop.IOLoop.instance()
        (conn1, conn2) = multiprocessing.Pipe()
        proc = multiprocessing.Process(target=self._createImage,
                                       args=(xml, conn1))
        self.pipe = conn1
        self.ioloop.add_handler(conn2.fileno(), _launch, self.ioloop.READ )
        proc.start()
        return d
    
    @exception.wrap_exception
    def console_output(self):
        if not FLAGS.fake_libvirt:
            console = open(self.basepath('console.log')).read()
        else:
            console = 'FAKE CONSOLE OUTPUT'
        return defer.succeed(console)

    def generate_mac(self):
        mac = [0x00, 0x16, 0x3e, random.randint(0x00, 0x7f),
               random.randint(0x00, 0xff), random.randint(0x00, 0xff)
               ]
        return ':'.join(map(lambda x: "%02x" % x, mac))
