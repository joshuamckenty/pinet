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

class NotValidNetworkSize(exception.Error):
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
    
    def list_addresses(self):
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

class NetworkPool(Network):
    # TODO - Allocations need to be system global
    
    def __init__(self, netsize=64, network="10.0.0.0/8", vlan="1000"):
        super(NetworkPool, self).__init__(network, vlan)
        if not netsize in [4,8,16,32,64,128,256,512,1024]:
            raise NotValidNetworkSize
        self.netsize = netsize
        self.allocations = []
    
    def next(self):
        start = len(self.allocations) * self.netsize
        self.allocations.append(self.network[start])
        return Network("%s-%s" % (self.network[start], self.network[start + self.netsize - 1]))
        

class NetworkNode(object):
    """ The network node is in charge of network connections  """

    def __init__(self, private=None, sizeof=64, public=None):
        """ load configuration options for this node and connect to libvirt """
        if not private:
            private = NetworkPool(sizeof)
        if not public:
            public = PublicNetwork()
        self._public = public
        self._private_pool = private
        self._private = {}
        self.init_gateways()
    
    def get_users_network(self, user_id):
        if not self._private.has_key(user_id):
            self._private[user_id] = self._private_pool.next()
        return self._private[user_id]
    
    def create_network(self, user_id):
        # ON ALL THE NODES:
        # Create VLAN interface
        # create virsh interface to bridge to the vlan interface
        # Setup DHCP server for private addressing
        pass
    
    def init_gateways(self):
        self.public_gateway = self._public.network[1]
        for user_id in self._private.keys():
            self._gateway[user_id] = self._private[user_id].network[1]
        
    def allocate_address(self, user_id, type=PrivateNetwork):
        if type == PrivateNetwork:
            return self.get_users_network(user_id).allocate_ip(user_id)
        return self._public.allocate_ip(user_id)
        
    def deallocate_address(self, address):
        if address in self._public.network:
            return self._public.deallocate_ip(address)
        for user_id in self._private.keys(): 
            if address in self.get_users_network(user_id).network:
                return self.get_users_network(user_id).deallocate_ip(address)
        raise NotAllocated

    def describe_addresses(self, type=PrivateNetwork):
        if type == PrivateNetwork:
            addresses = []
            for user_id in self._private.keys(): 
                addresses.extend(self.get_users_network(user_id).list_addresses())
            logging.debug("Full addresses list is: %s" % (addresses))
            return addresses
        return self._public.list_networks()
        
    def associate(self, address, instance_id):
        pass
        
    def _load(self):
        pass
        
    def report_state(self):
        pass