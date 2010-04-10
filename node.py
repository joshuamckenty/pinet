import libvirt
import os
import random
import shutil
import sys
import time

import partition2disk
import settings

import storage

class Node(object):
    """ The node is in charge of running instances.  """

    def __init__(self):
        """ load configuration options for this node and connect to libvirt """
        auth = [[libvirt.VIR_CRED_AUTHNAME, libvirt.VIR_CRED_NOECHOPROMPT], 'root', None]
        self._conn = libvirt.openAuth('qemu:///system', auth, 0)
        if self._conn == None:
            print 'Failed to open connection to the hypervisor'
            sys.exit(1)

    def describe_instances(self):
        """ return a list of instances on this node """
        return [self._conn.lookupByID(i).name() for i in self._conn.listDomainsID()]

    def run_instance(self, instance_id):
        """ launch a new instance with specified options """
        Instance(self._conn, instance_id)

    def terminate_instance(self, instance_id):
        """ terminate an instance on this machine """
        self._conn.lookupByName(instance_id).destroy()

    def get_console_output(self, instance_id):
        """ send the console output for an instance """
        return open(settings.instances_path + '/' + instance_id + '/console.log').read()

    def reboot_instance(self, instance_id):
        """ reboot an instance on this server
        KVM doesn't support reboot, so we terminate and restart """
        self._conn.lookupByName(instance_id).destroy()
        xml = open(settings.instances_path + '/' + instance_id + '/libvirt.xml').read()
        self._conn.createXML(xml, 0)

    def attach_volume(self, instance_id, volume_id, device):
        """ attach a volume to an instance """
        # Use aoetools via system calls
        # find out where the volume is mounted (ip, shelf and blade)
        # mount it to a random mount point
        pass

    def detach_volume(self, instance_id, volume_id):
        """ detach a volume from an instance """


class Instance(object):

    def __init__(self, conn, name, vcpus=1, memory_mb=1024):
        """ spawn an instance with a given name """
        self._conn = conn
        self._name = name
        self._vcpus = vcpus
        self._memory_mb = memory_mb
        self._mac  = self.generate_mac()

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


