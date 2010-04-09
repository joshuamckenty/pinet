import libvirt
import sys

class Node(object):
    """ The node is in charge of running instances.  """
  
    def initialize(self):
        """ load configuration options for this node """
        self._conn = libvirt.openReadOnly(None)
        if self._conn == None:
            print 'Failed to open connection to the hypervisor'
            sys.exit(1)
  
    def describe_instances(self):
        """ return a list of instances on this node """
        return self._conn.listDomainsID()

    def run_instance(self):
        """ launch a new instance with specified options """

    def terminate_instance(self):
        """ terminate an instance on this machine """

    def get_console_output(self, instance_id):
        """ send the console output for an instance """

    def reboot_instance(self, instance_id):
        """ reboot an instance on this server """

    def attach_volume(self, instance_id, volume_id, device):
        """ attach a volume to an instance """

    def detach_volume(self, instance_id, volume_id):
        """ detach a volume from an instance """

    def power_down(self):
        """ turn off this node """

    def start_network(self):
        pass

    def describe_node(self):
        """ return information about the state of this node """


if __name__ == '__main__':
    node = Node()
    node.describe_instances()