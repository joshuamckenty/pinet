# vim: tabstop=4 shiftwidth=4 softtabstop=4
import IPy
from IPy import IP
import logging

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
        self.assigned = [self.network[0], self.network[1]]
        # Do we want these here, or above?
        self.allocations = [{'address' : self.network[0], 'user_id' : 'pinet'}, 
                            {'address' : self.network[1], 'user_id' : 'pinet'}]
    
    def allocate_ip(self, user_id):
        for ip in self.network:
            if not ip in self.assigned:
                self.assigned.append(ip)
                logging.debug("Allocating IP %s" % (ip))
                self.allocations.append( {
                    "address" : ip, "user_id" : user_id
                })
                return ip
        raise NoMoreAddresses
    
    def deallocate_ip(self, ip):
        if not ip in self.assigned:
            raise NotAllocated
        idx = self.assigned.index(ip)
        self.assigned.pop(idx)
        self.allocations.pop(idx)
        
    def adopt(self):
        pass        
    
    def list_networks(self):
        for index, item in enumerate(self.assigned):
            yield self.allocations[index]

class PrivateNetwork(Network):
    pass
        
class PublicNetwork(Network):
    def __init__(self, network="192.168.216.0/24"):
        super(PublicNetwork, self).__init__(network)
    
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
        self.public_gateway = self._public.network[1]
        self.private_gateway = self._private.network[1]
        
    def allocate_address(self, user_id, type=PrivateNetwork):
        if type == PrivateNetwork:
            return self._private.allocate_ip(user_id)
        return self._public.allocate_ip(user_id)
        
    def deallocate_address(self, address):
        if address in self._public.network:
            return self._public.deallocate_ip(address)
        if address in self._private.network:
            return self._private.deallocate_ip(address)
        raise NotAllocated

    def describe_addresses(self, type=PrivateNetwork):
        if type == PrivateNetwork:
            return self._private.list_networks()
        return self._public.list_networks()
        
    def associate(self, address, instance_id):
        pass
        
    def _load(self):
        pass
        
    def report_state(self):
        pass