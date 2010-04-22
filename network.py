# vim: tabstop=4 shiftwidth=4 softtabstop=4
import logging
import os
import subprocess
import signal
import copy

# TODO(termie): clean up these imports
import datastore
import exception
from exception import *
import node
from node import GenericNode
import utils
from utils import runthis

import contrib
import flags
import anyjson
import IPy
from IPy import IP


FLAGS = flags.FLAGS
flags.DEFINE_bool('fake_network', False, 'should we use fake network devices and addresses')
flags.DEFINE_string('net_libvirt_xml_template',
                    utils.abspath('net.libvirt.xml.template'),
                    'Template file for libvirt networks')
flags.DEFINE_string('networks_path', utils.abspath('../networks'),
                    'Location to keep network XML files')
flags.DEFINE_integer('public_vlan', 2000, 'VLAN for public IP addresses')
KEEPER = datastore.keeper(prefix="net")

logging.getLogger().setLevel(logging.DEBUG)

class SecurityGroup(object):
    def __init__(self, **kwargs):
        pass
        

class Network(object):
    def __init__(self, vlan, network="192.168.100.0/24", conn=None):
        self._s = {}
        self.network_str = network
        self.network = IP(network)
        self._conn = conn
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
        self.name = self._s['name']
        self.dnsmasq = None
        try:
            os.makedirs(FLAGS.networks_path)
        except Exception, err:
            pass
            # logging.debug("Couldn't make directory, b/c %s" % (str(err)))
        
        # Do we want these here, or in the controller?
        self.allocations = [{'address' : str(self.network[0]), 'user_id' : 'net', 'mac' : '00:00:00:00:00:00'}, 
                            {'address' : str(self.network[1]), 'user_id' : 'gateway', 'mac' : '00:00:00:00:00:00'},
                            {'address' : str(self.network[-1]), 'user_id' : 'broadcast', 'mac' : '00:00:00:00:00:00'},]
        self.load()
        self.express()
    
    def __repr__(self):
        obj = {}
        obj['_s'] = copy.deepcopy(self._s)
        obj['vlan'] = self.vlan
        obj['network'] = self.network_str
        obj['hosts'] = self.allocations
        return obj

    def save(self):
        KEEPER[self.network_str] = self.__repr__()

    def load(self):
        state = KEEPER[self.network_str]
        if state:
            self.vlan = state['vlan']
            self.allocations = state['hosts']
            self.assigned = []
            for address in self.allocations:
                self.assigned.append(IP(address['address']))
            self._s = state['_s']

    def allocate_ip(self, user_id, mac):
        for ip in self.network:
            if not ip in self.assigned:
                self.assigned.append(ip)
                # logging.debug("Allocating IP %s" % (ip))
                self.allocations.append( {
                    "address" : str(ip), "user_id" : user_id, 'mac' : mac
                })
                self.save()
                self.express()
                return str(ip)
        raise NoMoreAddresses
    
    def deallocate_ip(self, ip_str):
        ip = IP(ip_str)
        if not ip in self.assigned:
            raise NotAllocated
        idx = self.assigned.index(ip)
        self.assigned.pop(idx)
        self.allocations.pop(idx)
        self.save()
        self.express()
        
    def list_addresses(self):
        for index, item in enumerate(self.assigned):
            yield self.allocations[index]
            
    def hostXml(self, allocation):
        idx = self.allocations.index(allocation) - 2 # Logically, the idx of instances they've launched in this net
        mac = allocation['mac']
        ip = allocation['address']
        user_id = allocation['user_id']
        return "      <host mac=\"%s\" name=\"%s.pinetlocal\" ip=\"%s\" />" % (mac, "%s-%s-%s" % (user_id, self.vlan, idx), ip)
    
    def hostDHCP(self, allocation):
        idx = self.allocations.index(allocation) - 2 # Logically, the idx of instances they've launched in this net
        mac = allocation['mac']
        ip = allocation['address']
        user_id = allocation['user_id']
        return "%s,%s.pinetlocal,%s" % (mac, "%s-%s-%s" % (user_id, self.vlan, idx), ip)
    
    def toXml(self):
        #self._s['hosts'] = "\n".join(map(self.hostXml, self.allocations))
        self._s['hosts'] = "\n"
        libvirt_xml = open(FLAGS.net_libvirt_xml_template).read()
        xml_info = self._s.copy()
        libvirt_xml = libvirt_xml % xml_info
        return libvirt_xml

    # NEED A FROMXML for roundtripping?
    # TODO - Need to be able to remove interfaces when they're not needed
    def start_dnsmasq(self):
        conf_file = "/var/pinet/run/pinet-%s.conf" % (self.vlan)
        conf = open(conf_file, "w")
        conf.write("\n".join(map(self.hostDHCP, self.allocations[2:])))
        conf.close()

        cmd = "sudo dnsmasq --strict-order --bind-interfaces --pid-file=/var/pinet/run/pinet-%s.pid" % (self.vlan)
        cmd += " --conf-file=  --listen-address %s --except-interface lo" % (self._s['gateway'])
        cmd += " --dhcp-range %s,%s,120s --dhcp-lease-max=61 " % (self._s['rangestart'], self._s['rangeend'])
        cmd += " --dhcp-hostsfile=%s --dhcp-leasefile=/var/pinet/run/pinet-%s.leases" % (conf_file, self.vlan)
        pid_file = "/var/pinet/run/pinet-%s.pid" % (self.vlan)
        #if self.dnsmasq:
        #    self.dnsmasq.send_signal("SIGHUP")
        if os.path.exists(pid_file):
            try:
                os.kill(int(open(pid_file).read()), signal.SIGHUP)
                return
            except Exception, err:
                logging.debug("Killing dnsmasq threw %s" % str(err))
        subprocess.Popen(str(cmd).split(" "))
            
    def express(self):

        xml = self.toXml()
        f = open(os.path.join(FLAGS.networks_path, self._s['name']), 'w')
        f.write(xml)
        f.close()
        
        if FLAGS.fake_network:
            return

        self.start_dnsmasq()        

        if not self._s['name'] in self._conn.listNetworks():
            logging.debug("Starting VLAN inteface for %s network" % (self._s['name']))
            if not FLAGS.fake_network:
                try:
                    runthis("Configuring VLAN type: %s", "sudo vconfig set_name_type VLAN_PLUS_VID_NO_PAD")
                    runthis("Adding VLAN %s: %%s" % (self.vlan) , "sudo vconfig add %s %s" % (FLAGS.bridge_dev, self.vlan))
                    runthis("Bringing up VLAN interface: %s", "sudo ifconfig vlan%s up" % (self.vlan))
                except:
                    pass
                try:
                    self._conn.networkDefineXML(xml)
                    net = self._conn.networkLookupByName(self._s['name'])
                    net.connect()
                    net.create()
                except Exception, err:
                    logging.debug("libvirt threw %s" % str(err))
                    pass
        else:
            pass


class PrivateNetwork(Network):
    def __init__(self, vlan, network=None, conn=None):
        super(PrivateNetwork, self).__init__(vlan=vlan, network=network, conn=conn)
        self.natted = False
        self.proxyarp = False

        
class PublicNetwork(Network):
    def __init__(self, vlan=None, network="192.168.216.0/24", conn=None):
        super(PublicNetwork, self).__init__(vlan=vlan, network=network, conn=conn)
        self.natted = True
        self.proxyarp = False
    
    def adopt(self):
        pass
    
    def write_iptables(self):
        pass


class NetworkPool(object):
    # TODO - Allocations need to be system global
    
    def __init__(self, netsize=64, network="192.168.0.0/17", vlan=2000, conn=None):
        #super(NetworkPool, self).__init__(vlan=vlan, network=network)
        self.network = IP(network)
        self.vlan = vlan
        if not netsize in [4,8,16,32,64,128,256,512,1024]:
            raise NotValidNetworkSize
        self.netsize = netsize
        self.allocations = []
        self.vlans = []
        self.next_vlan = vlan+1
        self.conn = conn

    # THIS CODE IS SHIT.


    def get(self, network_str, vlan):
        net = IP(network_str)
        self.allocations.append(net[0])
        self.vlans.append(vlan)
        self.next_vlan +=1
        return Network(vlan=vlan, network=network_str, conn=self.conn)
    
    def next(self):
        start = len(self.allocations) * self.netsize
        vlan = self.next_vlan
        self.allocations.append(self.network[start])
        self.vlans.append(vlan)
        self.next_vlan += 1
        logging.debug("Constructing network with vlan %s" % (vlan))
        return Network(vlan=vlan, network="%s-%s" % (self.network[start], self.network[start + self.netsize - 1]), conn=self.conn)
        

class NetworkController(GenericNode):
    """ The network node is in charge of network connections  """

    def __init__(self, private=None, sizeof=64, public=None):
        """ load configuration options for this node and connect to libvirt """
        super(NetworkController, self).__init__(private=private, sizeof=sizeof, public=public)
        self._conn = self._get_connection()
        if not private:
            private = NetworkPool(sizeof, conn=self._conn)
        if not public:
            public = PublicNetwork(vlan=FLAGS.public_vlan, conn=self._conn)
        self._public = public
        self._private_pool = private
        self._private = {}
        self._load()
    
    def get_users_network(self, user_id):
        if not self._private.has_key(user_id):
            self._private[user_id] = self._private_pool.next()
        return self._private[user_id]
    
    def init_gateways(self):
        self.public_gateway = self._public.network[1]
        for user_id in self._private.keys():
            self._gateway[user_id] = self._private[user_id].network[1]
        
    def allocate_address(self, user_id, mac=None, type=PrivateNetwork):
        ip = None
        net_name = None
        if type == PrivateNetwork:
            net = self.get_users_network(user_id)
            ip = net.allocate_ip(user_id, mac)
            net_name = net.name
        else:
            ip = self._public.allocate_ip(user_id, mac)
            net_name = self._public.name
        self._save()
        return (ip, net_name)
        
    def deallocate_address(self, address):
        if address in self._public.network:
            rv = self._public.deallocate_ip(address)
            self._save()
            return rv
        for user_id in self._private.keys(): 
            if address in self.get_users_network(user_id).network:
                rv = self.get_users_network(user_id).deallocate_ip(address)
                self._save()
                return rv
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
        state = KEEPER['private']
        if state:
            for net in state['networks']:
                self._private[net['user_id']] = self._private_pool.get(net['network'], net['vlan'])
    
    def _save(self):
        obj = {}
        obj['networks'] = []
        for user_id in self._private.keys():
            network = self._private[user_id]
            obj['networks'].append({'user_id': user_id, 
                                    'network': network.network_str, 
                                    'vlan': network.vlan })
        KEEPER['private'] = obj

    def express(self):
        return
        # TODO - use a separate connection for each node?
        for user_id in self._private.keys(): 
            self.get_users_network(user_id).express(self._conn)
        self._public.express(self._conn)
        
    def report_state(self):
        pass



class NetworkNode(node.Node):
    pass
