# vim: tabstop=4 shiftwidth=4 softtabstop=4
import IPy
from IPy import IP

import datastore
import exception

import contrib
import flags


FLAGS = flags.FLAGS
flags.DEFINE_string('fake_network', False, 'should we use fake network devices and addresses')

KEEPER = datastore.keeper("net-")

class SecurityGroup(object):
    def __init__(self, **kwargs):
        pass
        
class NoMoreAddresses(exception.Error):
    pass

class NotAllocated(exception.Error):
    pass

class Network(object):
    def __init__(self, network="10.0.0.0/8", vlan="1000"):
        self.network = IP(network)
        self.vlan = vlan
        self.assigned = []
    
    def allocate_ip(self):
        for ip in self.network:
            if not ip in self.assigned:
                self.assigned.append(ip)
                return ip
        raise NoMoreAddresses
    
    def deallocate_ip(self, ip):
        if not ip in self.assigned:
            raise NotAllocated
        assigned.remove(ip)
        

class PrivateNetwork(Network):
    pass
        
class PublicNetwork(Network):
    def __init__(self, network="192.168.216.0/24"):
        super(PublicNetwork, self).__init__(self, network)
    
    def adopt(self):
        pass
    
    def write_iptables(self):
        pass

class NetworkNode(object):
    """ The node is in charge of running instances.  """

    def __init__(self, private=None, public=None):
        """ load configuration options for this node and connect to libvirt """
        if not private:
            private = Network()
        if not public:
            public = PublicNetwork()
        self._public = public
        self._private = private
        self.init_gateways()
    
    def init_gateways(self):
        self.public_gateway = self._public.allocate_ip()
        self.private_gateway = self._private.allocate_ip()
        
    def allocate(self, user_id, type=PrivateNetwork):
        if type == PrivateNetwork:
            return self._private.allocate_ip()
        return self._public.allocate_ip()
        
    def deallocate(self, address):
        pass
        
    def associate(self, address, instance_id):
        pass
        
    def _load(self):
        pass
        
    def report_state(self):
        pass