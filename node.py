# vim: tabstop=4 shiftwidth=4 softtabstop=4
import logging
import os
import random
import shutil
import base64
import StringIO
import sys
import time
import contrib
import anyjson
from xml.etree import ElementTree

try:
    import libvirt
except Exception, e:
    pass

import exception
import fakevirt
import partition2disk
import settings

from utils import runthis


import calllib

import contrib
from tornado import ioloop
from twisted.internet import defer

VM_TYPES = {
    "m1.small" : { "ram" : 1024, "cpu" : 1, "disk" : 4096 },
    "m1.medium" : { "ram" : 2048, "cpu" : 2, "disk" : 4096 },
    "m1.large" : { "ram" : 4096, "cpu" : 4, "disk" : 4096 },
    "c1.medium" : { "ram" : 1024, "cpu" : 1, "disk" : 4096 },
        }

class Node(object):
    """ The node is in charge of running instances.  """

    def __init__(self, options=None):
        """ load configuration options for this node and connect to libvirt """
        self.options = options
        self._instances = {}
        self._conn = self._get_connection(options)

    def _get_connection(self, options=None):
        # TODO(termie): maybe lazy load after initial check for permissions
        # TODO(termie): check whether we can be disconnected
        if options and options.use_fake:
            conn = fakevirt.FakeVirtConnection(options)
        else:
            auth = [[libvirt.VIR_CRED_AUTHNAME, libvirt.VIR_CRED_NOECHOPROMPT], 
                    'root',
                    None]
            conn = libvirt.openAuth('qemu:///system', auth, 0)
            if conn == None:
                logging.error('Failed to open connection to the hypervisor')
                sys.exit(1)
        return conn
    
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
    def run_instance(self, instance_id, image_id, instance_type):
        """ launch a new instance with specified options """
        logging.debug("Starting instance %s..." % (instance_id))
        if instance_id in self._instances:
            raise exception.Error(
                    'attempting to use existing instance_id: %s' % instance_id)
        type = VM_TYPES[instance_type]
        new_inst = Instance(self._conn, name=instance_id, vcpus=type['cpu'], memory_mb = type['ram'], image_id = image_id, options=self.options)
        self._instances[instance_id] = new_inst
        rval = new_inst.spawn()
        logging.debug("Start attempt for instance %s returned %s" % (instance_id, rval))
        return rval
    

    @exception.wrap_exception
    def terminate_instance(self, instance_id):
        """ terminate an instance on this machine """
        if instance_id not in self._instances:
            raise exception.Error(
                    'trying to terminate unknown instance: %s' % instance_id)

        d = self._instances[instance_id].destroy()
        d.addCallback(self._instances.pop, instance_id)
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
        rv = yield self._instances[instance_id].console_log()
        output = {"InstanceId" : instance_id, "Timestamp" : "2", "output" : base64.b64encode(rv)}
        defer.returnValue(output)

    @defer.inlineCallbacks
    @exception.wrap_exception
    def attach_volume(self, instance_id = None, volume_id = None, dev = None):
        """ attach a volume to an instance """
        # FIXME - ASSERT the volume_id is valid, etc.
        self._init_aoe() 
        # Use aoetools via system calls
        # find out where the volume is mounted (ip, shelf and blade)
        aoe = yield calllib.call("storage",  
                                 {"method": "convert_volume_to_aoe",
                                  "args" : {"volume_id": (volume_id)}})
        if aoe is None or len(aoe) < 3:
            yield "fail"
        else:
            shelf_id = aoe[1]
            blade_id = aoe[3]
            # mount it to a random mount point
            mountpoint = "%s/%s" % (settings.volume_mountpoint, volume_id)
            try:
                os.mkdir(mountpoint) 
            except:
                pass
            runthis("Mounting AoE mount %s", 
                    "sudo mount /dev/etherd/e%s.%s %s -t ext3" % (shelf_id, blade_id, mountpoint ))

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

    def __init__(self, conn, name, vcpus=1, memory_mb=1024, image_id=None, options=None):
        """ spawn an instance with a given name """
        self._conn = conn
        self._name = name
        self._vcpus = vcpus
        self._memory_mb = memory_mb
        self._mac  = self.generate_mac()
        self._use_fake = False
        self._image_id = image_id 
        if options and options.use_fake:
            self._use_fake = True

        self._state = Instance.NOSTATE

    def is_pending(self):
        return self._state == Instance.NOSTATE

    def is_destroyed(self):
        return self._state == Instance.SHUTOFF

    def is_running(self):
        return self._state == Instance.RUNNING

    def describe(self):
        return self._name

    def info(self):
        virt_dom = self._conn.lookupByName(self._name)
        (state, max_mem, mem, num_cpu, cpu_time) = virt_dom.info()
        return {'state': state,
                'max_mem': max_mem,
                'mem': mem,
                'num_cpu': num_cpu,
                'cpu_time': cpu_time}
    
    @exception.wrap_exception
    def destroy(self):
        if self.is_destroyed():
            raise exception.Error('trying to destroy already destroyed'
                                  ' instance: %s' % self._name)

        self._state = Instance.SHUTDOWN
        
        virt_dom = self._conn.lookupByName(self._name)
        virt_dom.destroy()
        
        d = defer.Deferred()

        timer = ioloop.PeriodicCallback(callback=None, callback_time=500)
        def _wait_for_shutdown():
            try:
                info = self.info()
                if info['state'] == Instance.SHUTDOWN:
                    self._state = Instance.SHUTDOWN
                    timer.stop()
            except Exception:
                self._state = Instance.SHUTDOWN
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
                    'instance: %s (state: %s)' % (self._name, self._state))
        
        yield self._conn.lookupByName(self._name).destroy()

        self._state = Instance.NOSTATE
        self._conn.createXML(self._xml, 0)
        # TODO(termie): this should actually register a callback to check
        #               for successful boot
        self._state = Instance.RUNNING
        defer.returnValue(None)
    
    @exception.wrap_exception
    def spawn(self):
        if not self.is_pending():
            raise exception.Error(
                    'trying to spawn a running or terminated'
                    'instance: %s (state: %s)' % (self._name, self._state))

        self._xml = self.setup()
        self._conn.createXML(self._xml, 0)
        # TODO(termie): this should actually register a callback to check
        #               for successful boot
        self._state = Instance.RUNNING
        return defer.succeed(True)

    def console_log(self):
        return defer.succeed(open('%s/%s/console.log' % (settings.instances_path, self._name)).read())

    def generate_mac(self):
        mac = [0x00, 0x16, 0x3e, random.randint(0x00, 0x7f),
               random.randint(0x00, 0xff), random.randint(0x00, 0xff)
               ]
        return ':'.join(map(lambda x: "%02x" % x, mac))

    # FIXME - we need to be able to do this command async
    def setup(self):
        """ create libvirt.xml and copy files into instance path """
        self._basepath = settings.instances_path + '/' + self._name
        # FIXME - Use Python template module
        libvirt_xml = open('libvirt.xml.template').read() \
            .replace('NAME', self._name) \
            .replace('VCPUS', str(self._vcpus)) \
            .replace('MEMORY', str(self._memory_mb * 1024)) \
            .replace('BASEPATH', self._basepath) \
            .replace('PRIVMACADDR', self._mac) \
            .replace('BRIDGEDEV', settings.bridge)
        
        if not self._use_fake:
            os.makedirs(self._basepath)
            f = open(self._basepath+'/libvirt.xml', 'w')
            f.write(libvirt_xml)
            f.close()

            shutil.copyfile(settings.aki, self._basepath+'/kernel')
            shutil.copyfile(settings.ari, self._basepath+'/ramdisk')
            # TODO: If the disk image isn't on the node, go fetch from S3
            partition2disk.convert("%s/%s.img" % (settings.IMAGES_PATH, self._image_id), self._basepath+'/disk')

        return libvirt_xml


if __name__ == '__main__':
    node = Node()
    print "Existing Instances: ", node.describe_instances()
    for i in node.describe_instances():
        print "terminating %s" % i
        node.terminate_instance(i)
    print "All instances should be terminated: ", node.describe_instances()
    node.run_instance('i-%06d' % random.randint(0,1000000))
    print "New instance: ", node.describe_instances()
    time.sleep(5)
    node.reboot_instance(node.describe_instances()[0])


