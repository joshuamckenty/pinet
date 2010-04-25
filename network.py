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
from node import GenericNode, Node
import utils
from utils import runthis

import contrib
import flags
import anyjson
import IPy
from IPy import IP
from twisted.internet import defer


FLAGS = flags.FLAGS
flags.DEFINE_bool('fake_network', False, 'should we use fake network devices and addresses')
flags.DEFINE_string('net_libvirt_xml_template',
                    utils.abspath('net.libvirt.xml.template'),
                    'Template file for libvirt networks')
flags.DEFINE_string('networks_path', utils.abspath('../networks'),
                    'Location to keep network config files')
flags.DEFINE_integer('public_vlan', 2000, 'VLAN for public IP addresses')
KEEPER = datastore.keeper(prefix="net")

logging.getLogger().setLevel(logging.DEBUG)


class Network(object):
    def __init__(self, *args, **kwargs):
        self._s = {}
        self.network_str = kwargs.get('network', "192.168.100.0/24")
        self.network = IP(self.network_str)
        self._conn = kwargs.get('conn', None)
        self.vlan = kwargs.get('vlan', 100)
        self.name = "pinet-%s" % (self.vlan)
        self.gateway = self.network[1]
        self.netmask = self.network.netmask()
        self.broadcast = self.network.broadcast()
        self.bridge_name =  "br%s" % (self.vlan)
        self.bridge_gets_ip = False
        try:
            os.makedirs(FLAGS.networks_path)
        except Exception, err:
            pass
        self.hosts = kwargs.get('hosts', {})
    
    def to_dict(self):
        obj = {}
        obj['vlan'] = self.vlan
        obj['network'] = self.network_str
        obj['hosts'] = self.hosts
        return obj
        
    def __str__(self):
        return anyjson.serialize(self.to_dict())
        
    def __unicode__(self):
        return anyjson.serialize(self.to_dict())
    
    @classmethod
    def from_dict(cls, args, conn=None):
        for arg in args.keys():
            value = args[arg]
            del args[arg]
            args[str(arg)] = value
        self = cls(conn=conn, **args)
        return self
    
    @classmethod
    def from_json(cls, json_string, conn=None):
        parsed = anyjson.deserialize(json_string)
        return cls.from_dict(parsed, conn=conn)
    
    def range(self):
        for idx in range(2, len(self.network)-2):
            yield self.network[idx]
    
    def allocate_ip(self, user_id, mac):
        for ip in self.range():
            address = str(ip)
            if not address in self.hosts.keys():
                logging.debug("Allocating IP %s to %s" % (address, user_id))
                self.hosts[address] = {
                    "address" : address, "user_id" : user_id, 'mac' : mac
                }
                self.express()
                return address
        raise NoMoreAddresses
    
    def deallocate_ip(self, ip_str):
        if not ip_str in self.hosts.keys():
            raise NotAllocated
        del self.hosts[ip_str]
        # TODO(joshua) SCRUB from the leases file somehow
        self.express()
    
    def list_addresses(self):
        for address in self.hosts.values():
            yield address

    def express(self):
        pass


class Vlan(Network):
    def __init__(self, *args, **kwargs):
        super(Vlan, self).__init__(*args, **kwargs)
    
    def express(self):
        super(Vlan, self).express()
        try:                    
            logging.debug("Starting VLAN inteface for %s network" % (self.vlan))
            runthis("Configuring VLAN type: %s", "sudo vconfig set_name_type VLAN_PLUS_VID_NO_PAD")
            runthis("Adding VLAN %s: %%s" % (self.vlan) , "sudo vconfig add %s %s" % (FLAGS.bridge_dev, self.vlan))
            runthis("Bringing up VLAN interface: %s", "sudo ifconfig vlan%s up" % (self.vlan))
        except:
            pass   

 
class VirtNetwork(Vlan):
    def __init__(self, *args, **kwargs):
        super(VirtNetwork, self).__init__(*args, **kwargs)
    
    def virtXML(self):
        libvirt_xml = open(FLAGS.net_libvirt_xml_template).read()
        xml_info = {'name' : self.name, 
                    'bridge_name' : self.bridge_name, 
                    'device' : "vlan%s" % (self.vlan),
                    'gateway' : self.gateway,
                    'netmask' : self.netmask,
                   }
        libvirt_xml = libvirt_xml % xml_info
        return libvirt_xml
    
    def express(self):
        super(VirtNetwork, self).express()
        if FLAGS.fake_network:
            return  
        try:                    
            logging.debug("Starting Bridge inteface for %s network" % (self.vlan))
            runthis("Adding Bridge %s: %%s" % (self.vlan) , "sudo brctl addbr %s" % (self.bridge_name))
            runthis("Adding Bridge Interface %s: %%s" % (self.vlan) , "sudo brctl addif %s vlan%s" % (self.bridge_name, self.vlan))
            if self.bridge_gets_ip:
                runthis("Bringing up Bridge interface: %s", "sudo ifconfig %s %s broadcast %s netmask %s up" % (self.bridge_name, self.gateway, self.broadcast, self.netmask))
            else:
                runthis("Bringing up Bridge interface: %s", "sudo ifconfig %s up" % (self.bridge_name))
        except:
            pass      
    
class DHCPNetwork(VirtNetwork):
    def __init__(self, *args, **kwargs):
        super(DHCPNetwork, self).__init__(*args, **kwargs)
        logging.debug("Initing DHCPNetwork object...")
        self.bridge_gets_ip = True
    
    def hostDHCP(self, host):
        idx = host['address'].split(".")[-1] # Logically, the idx of instances they've launched in this net
        return "%s,%s.pinetlocal,%s" % \
            (host['mac'], "%s-%s-%s" % (host['user_id'], self.vlan, idx), host['address'])
    
    def dnsmasq_cmd(self, conf_file):
        cmd = "sudo dnsmasq --strict-order --bind-interfaces --pid-file=%s/pinet-%s.pid" % (FLAGS.networks_path, self.vlan)
        cmd += " --conf-file=  --listen-address %s --except-interface lo" % (str(self.network[1]))
        cmd += " --dhcp-range %s,%s,120s --dhcp-lease-max=61 " % (str(self.network[2]), str(self.network[-2]))
        cmd += " --dhcp-hostsfile=%s --dhcp-leasefile=%s/pinet-%s.leases" % (conf_file, FLAGS.networks_path, self.vlan)
        return cmd
    
    def start_dnsmasq(self):
        conf_file = "%s/pinet-%s.conf" % (FLAGS.networks_path, self.vlan)
        conf = open(conf_file, "w")
        conf.write("\n".join(map(self.hostDHCP, self.hosts.values())))
        conf.close()
        
        pid_file = "%s/pinet-%s.pid" % (FLAGS.networks_path, self.vlan)
        if os.path.exists(pid_file):
            try:
                os.kill(int(open(pid_file).read()), signal.SIGHUP)
                return
            except Exception, err:
                logging.debug("Killing dnsmasq threw %s" % str(err))
        try:
            os.unlink("%s/pinet-%s.leases" % (FLAGS.networks_path, self.vlan))
        except:
            pass
        cmd = self.dnsmasq_cmd(conf_file)
        subprocess.Popen(str(cmd).split(" "))
    
    def express(self):
        if FLAGS.fake_network:
            return
        super(DHCPNetwork, self).express()
        self.start_dnsmasq()     
        

class PrivateNetwork(DHCPNetwork):
    def __init__(self, conn=None, **kwargs):
        super(PrivateNetwork, self).__init__(conn=conn, **kwargs)
        self.express()
        
class PublicNetwork(Network):
    def __init__(self, conn=None, network="192.168.216.0/24", **kwargs):
        super(PublicNetwork, self).__init__(network=network, conn=conn, **kwargs)
        self.express()
    
    def express(self):
        logging.debug("Todo - need to create IPTables natting entries for this net.")


class NetworkPool(object):
    # TODO - Allocations need to be system global
    
    def __init__(self, netsize=64, network="192.168.0.0/17"):
        self.network = IP(network)
        if not netsize in [4,8,16,32,64,128,256,512,1024]:
            raise NotValidNetworkSize
        self.netsize = netsize
        self.allocations = []
    
    def next(self):
        start = len(self.allocations) * self.netsize
        net_str = "%s-%s" % (self.network[start], self.network[start + self.netsize - 1])
        self.allocations.append(net_str)
        logging.debug("Allocating %s" % net_str)
        return net_str

class VlanPool(object):
    def __init__(self, **kwargs):
        self.next_vlan = kwargs.get('start', 1000)
        self.end = kwargs.get('end', 4095)
        self.vlans = kwargs.get('vlans', {})
    
    def to_dict(self):
        obj = {}
        obj['vlans'] = self.vlans
        obj['start'] = self.next_vlan
        obj['end'] = self.end
        return obj
        
    def __str__(self):
        return anyjson.serialize(self.to_dict())
        
    def __unicode__(self):
        return anyjson.serialize(self.to_dict())
    
    @classmethod
    def from_dict(cls, args, conn=None):
        for arg in args.keys():
            value = args[arg]
            del args[arg]
            args[str(arg)] = value
        self = cls(conn=conn, **args)
        return self
    
    @classmethod
    def from_json(cls, json_string, conn=None):
        parsed = anyjson.deserialize(json_string)
        return cls.from_dict(parsed, conn=conn)
    
    def next(self, user_id):
        if self.next_vlan == self.end:
            raise NotAllocated
        self.vlans[user_id] = self.next_vlan
        self.next_vlan += 1
        return self.vlans[user_id]

class NetworkController(GenericNode):
    """ The network controller is in charge of network connections  """

    def __init__(self, **kwargs):
        logging.debug("Starting up the network controller.")
        super(NetworkController, self).__init__(**kwargs)
        self._conn = self._get_connection()
        self.netsize = kwargs.get('netsize', 64)
        self.private_pool = kwargs.get('private_pool', NetworkPool(netsize=self.netsize))
        self.private_nets = kwargs.get('private_nets', {})
        if not KEEPER['private']:
            KEEPER['private'] = {'networks' :[]}
        for net in KEEPER['private']['networks']:
                self.get_users_network(net['user_id'])
        if not KEEPER['vlans']:
            KEEPER['vlans'] = {'start' : 3200, 'end' : 3299}
        vlan_dict = kwargs.get('vlans', KEEPER['vlans'])
        self.vlan_pool = VlanPool.from_dict(vlan_dict)
        public_dict = kwargs.get('public', {'vlan': FLAGS.public_vlan })
        self.public_net = PublicNetwork.from_dict(public_dict, conn=self._conn)

    def reset(self):
        KEEPER['public'] = {'vlan': FLAGS.public_vlan }
        KEEPER['private'] = {}
        KEEPER['vlans'] = {}

    def get_network_from_name(self, network_name):
        net_dict = KEEPER[network_name]
        if net_dict:
            network_str = self.private_pool.next() # TODO, block allocations
            return PrivateNetwork.from_dict(net_dict)
        return None
    
    def get_users_network(self, user_id):
        if not self.private_nets.has_key(user_id):
            self.private_nets[user_id] = self.get_network_from_name("%s-default" % user_id)
            if not self.private_nets[user_id]:
                network_str = self.private_pool.next()
                vlan = self.vlan_pool.next(user_id)
                logging.debug("Constructing network %s and %s for %s" % (network_str, vlan, user_id))
                self.private_nets[user_id] = PrivateNetwork(network = network_str, vlan = self.vlan_pool.vlans[user_id], conn = self._conn)
                KEEPER["%s-default" % user_id] = self.private_nets[user_id].to_dict()
        return self.private_nets[user_id]
        
    def allocate_address(self, user_id, mac=None, type=PrivateNetwork):
        ip = None
        net_name = None
        if type == PrivateNetwork:
            net = self.get_users_network(user_id)
            ip = net.allocate_ip(user_id, mac)
            net_name = net.name
        else:
            ip = self.public_net.allocate_ip(user_id, mac)
            net_name = self.public_net.name
        self._save()
        return (ip, net_name)
        
    def deallocate_address(self, address):
        if address in self.public_net.network:
            rv = self.public_net.deallocate_ip(address)
            self._save()
            return rv
        for user_id in self.private_nets.keys(): 
            if address in self.get_users_network(user_id).network:
                rv = self.get_users_network(user_id).deallocate_ip(address)
                self._save()
                return rv
        raise NotAllocated

    def describe_addresses(self, type=PrivateNetwork):
        if type == PrivateNetwork:
            addresses = []
            for user_id in self.private_nets.keys(): 
                addresses.extend(self.get_users_network(user_id).list_addresses())
            return addresses
        return self.public_net.list_networks()
        
    def associate(self, address, instance_id):
        pass
        
    def _save(self):
        obj = {}
        obj['networks'] = []
        for user_id in self.private_nets.keys():
            network = self.private_nets[user_id]
            vlan = self.vlan_pool.vlans[user_id]
            obj['networks'].append({'user_id': user_id, 
                                    'network': str(network), 
                                    'vlan': vlan })
        KEEPER['private'] = obj
        KEEPER['vlans'] = self.vlan_pool.to_dict()

    def express(self):
        return
        # TODO - use a separate connection for each node?
        for user_id in self._private.keys(): 
            self.get_users_network(user_id).express(self._conn)
        self._public.express(self._conn)
        
    def report_state(self):
        pass



class NetworkNode(Node):
    def __init__(self, **kwargs):
        super(NetworkNode, self).__init__(**kwargs)
        self.vlans = {}
        self.virtNets = {}
        
    def add_network(self, net_dict):
        net = VirtNetwork(conn=self._conn, ** net_dict)
        self.virtNets[net.name] = net
        self.virtNets[net.name].express()
        return defer.succeed({'retval': 'network added'})
        
    def express_all_networks(self):
        for vlan in self.vlans.values():
            vlan.express()
        for virtnet in self.virtNets.values():
            virtnet.express()

        output = {'retval' : 'okay'}
        return defer.succeed(output)
        
    @exception.wrap_exception
    def run_instance(self, instance_id, **kwargs):
        net_dict = kwargs.get('network_str', {})
        self.add_network(net_dict)
        return super(NetworkNode, self).run_instance(instance_id, **kwargs)
