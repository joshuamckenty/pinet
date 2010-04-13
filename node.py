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

try:
    import libvirt
except Exception, e:
    logging.warning('no libvirt found')

import exception
import fakevirt
import flags
import partition2disk
import storage

from utils import runthis


import calllib

from tornado import ioloop
from twisted.internet import defer


FLAGS = flags.FLAGS
flags.DEFINE_string('node_topic', 'node', 'the topic nodes listen on')
flags.DEFINE_bool('fake_libvirt', False,
                  'whether to use a fake libvirt or not')
flags.DEFINE_string('instances_path', '/root/pinet/instances',
                    'where instances are stored on disk')
flags.DEFINE_string('images_path', '/root/pinet/images',
                    'where images are stored on disk')
flags.DEFINE_string('bridge_dev', 'virbr0',
                    'network bridge for nodes')
flags.DEFINE_string('libvirt_xml_template', 'libvirt.xml.template',
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


INSTANCE_TYPES = {}
INSTANCE_TYPES['m1.small'] = {'memory_mb': 1024, 'vcpus': 1, 'disk_mb': 4096}
INSTANCE_TYPES['m1.medium'] = {'memory_mb': 2048, 'vcpus': 2, 'disk_mb': 4096}
INSTANCE_TYPES['m1.large'] = {'memory_mb': 4096, 'vcpus': 4, 'disk_mb': 4096}
INSTANCE_TYPES['c1.medium'] = {'memory_mb': 1024, 'vcpus': 1, 'disk_mb': 4096}


class Node(object):
    """ The node is in charge of running instances.  """

    def __init__(self):
        """ load configuration options for this node and connect to libvirt """
        self._instances = {}
        self._conn = self._get_connection()

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
    
    @exception.wrap_exception
    def adopt_instances(self):
        """ if there are instances already running, adopt them """
        instance_names = [self._conn.lookupByID(x).name
                          for x in self._conn.listDomainsID()]
        for name in instance_names:
            new_inst = Instance.fromName(name)
            self._instances[name] = new_inst
        return defer.succeed(len(self._instances))
    
    @defer.inlineCallbacks
    def report_state(self):
        logging.debug("Reporting State")
        instances = []
        rv = yield self.describe_instances()

        if rv:
            for instance in rv:
                instances.append(
                    {"item": 
                       {"reservation_id": "foo",
                        "ownerId" : "tim",
                        "groupSet" : {"item" : {"groupId": "default"}},
                        "instancesSet" : {
                            "item": {"instanceId" : instance,
                                     "imageId" : "emi-foo",
                                     "instanceState" : {"code": 0,
                                                        "name" : "pending"}
                                     }
                            }
                        }
                    })
        instances = {"reservationSet" : instances}
        calllib.cast("cloud",  
                            {"method": "update_state",
                             "args" : {"topic": "instances",
                                       "value": instances
                                       }
                             })
    
    def noop(self):
        return defer.succeed('PONG')
    
    @exception.wrap_exception
    def describe_instances(self):
        """ return a list of instances on this node """
        return defer.succeed([x.describe() for x in self._instances.values()])
    
    @exception.wrap_exception
    def run_instance(self, instance_id, **kwargs):
        """ launch a new instance with specified options """
        logging.debug("Starting instance %s..." % (instance_id))
        if instance_id in self._instances:
            raise exception.Error(
                    'attempting to use existing instance_id: %s' % instance_id)

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
    def detach_volume(self, instance_id, volume_id):
        """ detach a volume from an instance """


class Instance(object):
    NOSTATE = 0x00
    RUNNING = 0x01
    BLOCKED = 0x02
    PAUSED = 0x03
    SHUTDOWN = 0x04
    SHUTOFF = 0x05
    CRASHED = 0x06

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
        self._s['mac_address'] = kwargs.get(
                'mac_address', self.generate_mac())
        self._s['basepath'] = kwargs.get(
                'basepath', os.path.join(FLAGS.instances_path, self.name))
        self._s['memory_kb'] = int(self._s['memory_mb']) * 1024
        self._s['bridge_dev'] = kwargs.get('bridge_dev', FLAGS.bridge_dev)
        self._s['image_id'] = kwargs.get('image_id', FLAGS.default_image)
        self._s['kernel'] = kwargs.get('kernel', FLAGS.default_kernel)
        self._s['ramdisk'] = kwargs.get('ramdisk', FLAGS.default_ramdisk)
        self._s['state'] = Instance.NOSTATE

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
        basepath = os.path.join(FLAGS.instances_path, name)
        libvirt_xml = open(os.path.join(basepath, 'libvirt.xml')).read()
        return cls.fromXml(conn, xml)

    def _createImage(self, libvirt_xml):
        """ create libvirt.xml and copy files into instance path """
        
        d = defer.Deferred()
        if not FLAGS.fake_libvirt:
            # TODO(termie): what to do when this already exists?
            # TODO(termie): clean up on exit?
            
            os.makedirs(self._s['basepath'])
            
            def _out_of_band(deferred):
                logging.info('Creating image for: %s', self.name)
                f = open(self.basepath('libvirt.xml'), 'w')
                f.write(libvirt_xml)
                f.close()
                
                shutil.copyfile(self.imagepath(self._s['kernel']),
                                self.basepath('kernel'))
                shutil.copyfile(self.imagepath(self._s['ramdisk']),
                                self.basepath('ramdisk'))
                partition2disk.convert(self.imagepath(self._s['image_id']),
                                       self.basepath('disk'))

                logging.info('Done create image for: %s', self.name)
                
                deferred.callback(True)
                
            proc = multiprocessing.Process(target=_out_of_band, args=(d,))
            proc.start()
        else:
            d.callback(True)
        
        return d

    @property
    def state(self):
        return self._s['state']

    @property
    def name(self):
        return self._s['name']

    def basepath(self, s=''):
        return os.path.join(self._s['basepath'], s)

    def imagepath(self, s=''):
        return os.path.join(FLAGS.image_path, s)

    def is_pending(self):
        return self.state == Instance.NOSTATE

    def is_destroyed(self):
        return self.state == Instance.SHUTOFF

    def is_running(self):
        return self.state == Instance.RUNNING

    def describe(self):
        return self.name

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
        d = self._createImage(xml)

        def _launch(_):
            self._conn.createXML(self.toXml(), 0)
            # TODO(termie): this should actually register a callback to check
            #               for successful boot
            self._s['state'] = Instance.RUNNING

        d.addCallback(_launch)
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
