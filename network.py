# vim: tabstop=4 shiftwidth=4 softtabstop=4
import logging
import os

import datastore
import exception
from exception import *
import node
from node import GenericNode
from utils import runthis

import contrib
import flags
import anyjson
import IPy
from IPy import IP


FLAGS = flags.FLAGS
flags.DEFINE_string('fake_network', False, 'should we use fake network devices and addresses')
flags.DEFINE_string('net_libvirt_xml_template', 'net.libvirt.xml.template', 'Template file for libvirt networks')
flags.DEFINE_string('networks_path', '../networks', 'Location to keep network XML files')
flags.DEFINE_integer('public_vlan', 2000, 'VLAN for public IP addresses')
KEEPER = datastore.keeper("net-")


class SecurityGroup(object):
    def __init__(self, **kwargs):
        pass
        

class Network(object):
    def __init__(self, vlan, network="192.168.100.0/24"):
        self._s = {}
        self.network = IP(network)
        self.vlan = vlan
        self.assigned = [self.network[0], self.network[1], self.network[-1]]
        self._s['gateway'] = str(self.network[1])
        self._s['netmask'] = str(self.network.netmask())
        self._s['broadcast'] = str(self.network[-1])
        self._s['rangestart'] = str(self.network[2])
        self._s['rangeend'] = str(self.network[-2])
        self._s['bridge_name'] = "br%s" % (self.vlan)
        self._s['device'] = "vlan%s" % (self.vlan)
        self._s['name'] = "pinet-%s" % (self.vlan)
        try:
            os.makedirs(FLAGS.networks_path)
        except Exception, err:
            pass
            # logging.debug("Couldn't make directory, b/c %s" % (str(err)))
        
        # Do we want these here, or in the controller?
        self.allocations = [{'address' : self.network[0], 'user_id' : 'net', 'mac' : '00:00:00:00:00:00'}, 
                            {'address' : self.network[1], 'user_id' : 'gateway', 'mac' : '00:00:00:00:00:00'},
                            {'address' : self.network[-1], 'user_id' : 'broadcast', 'mac' : '00:00:00:00:00:00'},]
    
    def allocate_ip(self, user_id, mac):
        for ip in self.network:
            if not ip in self.assigned:
                self.assigned.append(ip)
                # logging.debug("Allocating IP %s" % (ip))
                self.allocations.append( {
                    "address" : ip, "user_id" : user_id, 'mac' : mac
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
            
    def hostXml(self, allocation):
        mac = allocation['mac']
        ip = allocation['address']
        user_id = allocation['user_id']
        return "      <host mac=\"%s\" name=\"%s.pinetlocal\" ip=\"%s\" />" % (mac, "%s-%s-%s" % (user_id, self.vlan, ip), ip)
    
    def toXml(self):
        self._s['hosts'] = "\n".join(map(self.hostXml, self.allocations))
        libvirt_xml = open(FLAGS.net_libvirt_xml_template).read()
        xml_info = self._s.copy()
        libvirt_xml = libvirt_xml % xml_info
        return libvirt_xml

    # NEED A FROMXML for roundtripping?
    # TODO - Need to be able to remove interfaces when they're not needed
            
    def express(self, conn):
        # ON ALL THE NODES:
        # Create VLAN interface
        
        if self._s['name'] in conn.listNetworks():
            logging.debug("Skipping network %s cause it's already running" % (self._s['name']))
            return # Reboot the network here

        runthis("Configuring VLAN type: %s", "sudo vconfig set_name_type VLAN_PLUS_VID_NO_PAD")
        runthis("Adding VLAN %s: %%s" % (self.vlan) , "sudo vconfig add %s %s" % (FLAGS.bridge_dev, self.vlan))
        runthis("Bringing up VLAN interface: %s", "sudo ifconfig vlan%s up" % (self.vlan))
        #runthis("Bringing up VLAN interface: %s", "sudo ifconfig vlan%s %s netmask %s broadcast %s up" % 
        #          (self.vlan, "192.168.0.%s" % ((self.vlan % 1000)), "255.255.255.0", "192.168.0.255"))
        
        # create virsh interface to bridge to the vlan interface
        xml = self.toXml()
        # logging.debug(xml)                
        f = open(os.path.join(FLAGS.networks_path, self._s['name']), 'w')
        f.write(xml)
        f.close()
        try:
            conn.networkCreateXML(xml)
        except Exception, err:
            logging.debug("libvirt threw %s" % str(err))
            pass

    def is_running(self, conn):
        pass


class PrivateNetwork(Network):
    def __init__(self, vlan, network=None):
        super(PrivateNetwork, self).__init__(vlan=vlan, network=network)
        self.natted = False
        self.proxyarp = False

        
class PublicNetwork(Network):
    def __init__(self, vlan=None, network="192.168.216.0/24"):
        super(PublicNetwork, self).__init__(vlan=vlan, network=network)
        self.natted = True
        self.proxyarp = False
    
    def adopt(self):
        pass
    
    def write_iptables(self):
        pass


class NetworkPool(Network):
    # TODO - Allocations need to be system global
    
    def __init__(self, netsize=64, network="192.168.0.0/17", vlan=2000):
        super(NetworkPool, self).__init__(vlan=vlan, network=network)
        if not netsize in [4,8,16,32,64,128,256,512,1024]:
            raise NotValidNetworkSize
        self.netsize = netsize
        self.allocations = []
        self.vlans = []
        self.next_vlan = vlan+1
    
    def next(self):
        start = len(self.allocations) * self.netsize
        vlan = self.next_vlan
        self.allocations.append(self.network[start])
        self.vlans.append(vlan)
        self.next_vlan += 1
        logging.debug("Constructing network with vlan %s" % (vlan))
        return Network(vlan=vlan, network="%s-%s" % (self.network[start], self.network[start + self.netsize - 1]))
        

class NetworkController(GenericNode):
    """ The network node is in charge of network connections  """

    def __init__(self, private=None, sizeof=64, public=None):
        """ load configuration options for this node and connect to libvirt """
        super(NetworkController, self).__init__(private=private, sizeof=sizeof, public=public)
        self._conn = self._get_connection()
        if not private:
            private = NetworkPool(sizeof)
        if not public:
            public = PublicNetwork(vlan=FLAGS.public_vlan)
        self._public = public
        self._private_pool = private
        self._private = {}
        self._load()
        self.express()
    
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
        
    def allocate_address(self, user_id, mac=None, type=PrivateNetwork):
        if type == PrivateNetwork:
            return self.get_users_network(user_id).allocate_ip(user_id, mac)
        return self._public.allocate_ip(user_id, mac)
        
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
            return addresses
        return self._public.list_networks()
        
    def associate(self, address, instance_id):
        pass
        
    def _load(self):
        pass
        
    def express(self):
        # TODO - use a separate connection for each node?
        for user_id in self._private.keys(): 
            self.get_users_network(user_id).express(self._conn)
        self._public.express(self._conn)
        
    def report_state(self):
        pass

class NetworkNode(node.Node):
    pass
