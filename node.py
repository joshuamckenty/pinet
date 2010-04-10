# vim: tabstop=4 shiftwidth=4 softtabstop=4
import logging
import os
import random
import shutil
import StringIO
import sys
import time
from xml.etree import ElementTree

import libvirt

import exception
import fakevirt
import partition2disk
import settings
import storage
from utils import runthis

import calllib



class Node(object):
    """ The node is in charge of running instances.  """

    def __init__(self, options=None):
        """ load configuration options for this node and connect to libvirt """
        self.options = options
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
    
    @exception.wrap_exception
    def describe_instances(self):
        """ return a list of instances on this node """
        return [self._conn.lookupByID(i).name()
                for i in self._conn.listDomainsID()]

    @exception.wrap_exception
    def run_instance(self, instance_id):
        """ launch a new instance with specified options """
        Instance(self._conn, instance_id, options=self.options)
    
    @exception.wrap_exception
    def terminate_instance(self, instance_id):
        """ terminate an instance on this machine """
        self._conn.lookupByName(instance_id).destroy()

    @exception.wrap_exception
    def get_console_output(self, instance_id):
        """ send the console output for an instance """
        return open(settings.instances_path + '/' + instance_id + '/console.log').read()

    @exception.wrap_exception
    def reboot_instance(self, instance_id):
        """ reboot an instance on this server
        KVM doesn't support reboot, so we terminate and restart """
        self._conn.lookupByName(instance_id).destroy()
        xml = open(settings.instances_path + '/' + instance_id + '/libvirt.xml').read()
        self._conn.createXML(xml, 0)

    @exception.wrap_exception
    def attach_volume(self, instance_id = None, volume_id = None, dev = None):
        """ attach a volume to an instance """
        # FIXME - ASSERT the volume_id is valid, etc.
        self._init_aoe() 
        # Use aoetools via system calls
        # find out where the volume is mounted (ip, shelf and blade)
        caller = calllib.synccall()
        aoe = caller.call_sync("storage",  '{"method": "convert_volume_to_aoe", "args" : {"volume_id": "%s"}}' % (volume_id))
        shelf_id = aoe[1]
        blade_id = aoe[3]
        # mount it to a random mount point
        mountpoint = "%s/%s" % (settings.volume_mountpoint, volume_id)
        try:
            os.mkdir(mountpoint) 
        except:
            pass
        runthis("Mounting AoE mount", "sudo mount %s /dev/etherd/e%s.%s -t ext3" % (mountpoint, shelf_id, blade_id ))

    def _init_aoe(self):
        runthis("Doin an AoE discover, returns %s", "sudo aoe-discover")
        runthis("Doin an AoE stat, returns %s", "sudo aoe-stat")
    
    @exception.wrap_exception
    def detach_volume(self, instance_id, volume_id):
        """ detach a volume from an instance """


class Instance(object):

    def __init__(self, conn, name, vcpus=1, memory_mb=1024, options=None):
        """ spawn an instance with a given name """
        self._conn = conn
        self._name = name
        self._vcpus = vcpus
        self._memory_mb = memory_mb
        self._mac  = self.generate_mac()
        self._use_fake = False
        if options and options.use_fake:
            self._use_fake = True

        xml = self.setup()
        self._conn.createXML(xml, 0)

    def generate_mac(self):
        mac = [0x00, 0x16, 0x3e, random.randint(0x00, 0x7f), \
           random.randint(0x00, 0xff), random.randint(0x00, 0xff)]
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
            partition2disk.convert(settings.ami, self._basepath+'/disk')

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


