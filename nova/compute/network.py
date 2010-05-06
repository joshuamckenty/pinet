# vim: tabstop=4 shiftwidth=4 softtabstop=4
import logging
import os
import subprocess
import signal

# TODO(termie): clean up these imports
from nova import datastore, exception, contrib
from nova.exception import NotFound, NotAuthorized
from exception import *
from node import GenericNode, Node
from nova import utils
from nova.utils import runthis
from nova.utils import execute

from nova import flags
import anyjson
import IPy
from IPy import IP
from twisted.internet import defer
from nova.auth.users import UserManager

FLAGS = flags.FLAGS
flags.DEFINE_string('net_libvirt_xml_template',
                    utils.abspath('compute/net.libvirt.xml.template'),
                    'Template file for libvirt networks')
flags.DEFINE_string('networks_path', utils.abspath('../networks'),
                    'Location to keep network config files')
flags.DEFINE_integer('public_vlan', 2000, 'VLAN for public IP addresses') # FAKE!!! 
flags.DEFINE_string('bridge_dev', 'eth2',
                        'network device for bridges')
flags.DEFINE_integer('vlan_start', 2020, 'First VLAN for private networks')
flags.DEFINE_integer('vlan_end', 2039, 'Last VLAN for private networks')
flags.DEFINE_integer('network_size', 256, 'Number of addresses in each private subnet') 
flags.DEFINE_string('public_interface', 'vlan124', 'Interface for public IP addresses')
flags.DEFINE_string('public_range', '198.10.124.128-198.10.124.191', 'Public IP address block')
flags.DEFINE_string('private_range', '10.128.0.0/12', 'Private IP address block')
flags.DEFINE_string('cloudpipe_ami', 'ami-A7370FE3', 'CloudPipe image')
flags.DEFINE_integer('cloudpipe_start_port', 8000, 'Starting port for mapped CloudPipe external ports')

KEEPER = datastore.keeper(prefix="net")


logging.getLogger().setLevel(logging.DEBUG)


def confirm_rule(cmd):
    execute("sudo iptables --delete %s" % (cmd))
    execute("sudo iptables -I %s" % (cmd))

def remove_rule(cmd):
    execute("sudo iptables --delete %s" % (cmd))
    pass

class Network(object):
    def __init__(self, *args, **kwargs):
        self._s = {}
        self.network_str = kwargs.get('network', "192.168.100.0/24")
        self.network = IP(self.network_str)
        self._conn = kwargs.get('conn', None)
        self.vlan = kwargs.get('vlan', 100)
        self.name = "nova-%s" % (self.vlan)
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
        return {'vlan': self.vlan,
                'network': self.network_str,
                'hosts': self.hosts}
 
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
        # the .2 address is always CloudPipe
        for idx in range(3, len(self.network)-2):
            yield self.network[idx]
    
    def allocate_ip(self, user_id, mac):
        for ip in self.range():
            address = str(ip)
            if not address in self.hosts.keys():
                logging.debug("Allocating IP %s to %s" % (address, user_id))
                self.hosts[address] = {
                    "address" : address, "user_id" : user_id, 'mac' : mac
                }
                self.express(address=address)
                return address
        raise NoMoreAddresses()
    
    def deallocate_ip(self, ip_str):
        if not ip_str in self.hosts.keys():
            raise AddressNotAllocated()
        del self.hosts[ip_str]
        # TODO(joshua) SCRUB from the leases file somehow
        self.deexpress(address=ip_str)
    
    def list_addresses(self):
        for address in self.hosts.values():
            yield address

    def express(self, address=None):
        pass

    def deexpress(self, address=None):
        pass


class Vlan(Network):
    def __init__(self, *args, **kwargs):
        super(Vlan, self).__init__(*args, **kwargs)
    
    def express(self, address=None):
        super(Vlan, self).express(address=address)
        try:                    
            logging.debug("Starting VLAN inteface for %s network" % (self.vlan))
            execute("sudo vconfig set_name_type VLAN_PLUS_VID_NO_PAD")
            execute("sudo vconfig add %s %s" % (FLAGS.bridge_dev, self.vlan))
            execute("sudo ifconfig vlan%s up" % (self.vlan))
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
    
    def express(self, address=None):
        super(VirtNetwork, self).express(address=address)
        if FLAGS.fake_network:
            return  
        try:                    
            logging.debug("Starting Bridge inteface for %s network" % (self.vlan))
            execute("sudo brctl addbr %s" % (self.bridge_name))
            execute("sudo brctl addif %s vlan%s" % (self.bridge_name, self.vlan))
            if self.bridge_gets_ip:
                execute("sudo ifconfig %s %s broadcast %s netmask %s up" % (self.bridge_name, self.gateway, self.broadcast, self.netmask))
                confirm_rule("FORWARD --in-interface %s -j ACCEPT" % (self.bridge_name))
            else:
                execute("sudo ifconfig %s up" % (self.bridge_name))
        except:
            pass      

    
class DHCPNetwork(VirtNetwork):
    """
    """
    def __init__(self, *args, **kwargs):
        super(DHCPNetwork, self).__init__(*args, **kwargs)
        logging.debug("Initing DHCPNetwork object...")
        self.bridge_gets_ip = True
    
    def hostDHCP(self, host):
        idx = host['address'].split(".")[-1] # Logically, the idx of instances they've launched in this net
        return "%s,%s.novalocal,%s" % \
            (host['mac'], "%s-%s-%s" % (host['user_id'], self.vlan, idx), host['address'])
    
    def dnsmasq_cmd(self, conf_file):
        cmd = "sudo dnsmasq --strict-order --bind-interfaces --pid-file=%s/nova-%s.pid" % (FLAGS.networks_path, self.vlan)
        cmd += " --conf-file=  --listen-address %s --except-interface lo" % (str(self.network[1]))
        cmd += " --dhcp-range %s,%s,120s --dhcp-lease-max=61 " % (str(self.network[3]), str(self.network[-2]))
        cmd += " --dhcp-hostsfile=%s --dhcp-leasefile=%s/nova-%s.leases" % (conf_file, FLAGS.networks_path, self.vlan)
        return cmd
    
    def start_dnsmasq(self):
        conf_file = "%s/nova-%s.conf" % (FLAGS.networks_path, self.vlan)
        conf = open(conf_file, "w")
        conf.write("\n".join(map(self.hostDHCP, self.hosts.values())))
        conf.close()
        
        pid_file = "%s/nova-%s.pid" % (FLAGS.networks_path, self.vlan)
        if os.path.exists(pid_file):
            try:
                os.kill(int(open(pid_file).read()), signal.SIGHUP)
                return
            except Exception, err:
                logging.debug("Killing dnsmasq threw %s" % str(err))
        try:
            os.unlink("%s/nova-%s.leases" % (FLAGS.networks_path, self.vlan))
        except:
            pass
        cmd = self.dnsmasq_cmd(conf_file)
        subprocess.Popen(str(cmd).split(" "))
    
    def express(self, address=None):
        if FLAGS.fake_network:
            return
        super(DHCPNetwork, self).express(address=address)
        if len(self.hosts.values()) > 0:
            logging.debug("Starting dnsmasq server for network with vlan %s" % self.vlan)
            self.start_dnsmasq()     
        else:
            logging.debug("Not launching dnsmasq cause I don't think we have any hosts.")

    def stop_dnsmasq(self):
        pid_file = "%s/nova-%s.pid" % (FLAGS.networks_path, self.vlan)
        if os.path.exists(pid_file):
            try:
                os.kill(int(open(pid_file).read()), signal.SIGTERM)
            except Exception, err:
                logging.debug("Killing dnsmasq threw %s" % str(err))
        try:
            os.unlink("%s/nova-%s.leases" % (FLAGS.networks_path, self.vlan))
        except:
            pass

    def deexpress(self, address=None):
        # if this is the last address, stop dns
        super(DHCPNetwork, self).deexpress(address=address)
        if len(self.hosts.values()) == 0:
            self.stop_dnsmasq()
        
        

class PrivateNetwork(DHCPNetwork):
    def __init__(self, external_vpn_ip, external_vpn_port, conn=None, **kwargs):
        self.external_vpn_ip = external_vpn_ip
        self.external_vpn_port = external_vpn_port
        super(PrivateNetwork, self).__init__(conn=conn, **kwargs)
        self.express()

    def to_dict(self):
        return {'vlan': self.vlan,
                'network': self.network_str,
                'hosts': self.hosts,
                'external_vpn_ip': self.external_vpn_ip,
                'external_vpn_port': self.external_vpn_port}
        
    def express(self, *args, **kwargs):
        super(PrivateNetwork, self).express(*args, **kwargs)
        self.cloudpipe_express()
        
    def get_vpn_ip(self, user_id, mac):
        address = str(self.network[2])
        self.hosts[address] = {
                    "address" : address, "user_id" : user_id, 'mac' : mac
        }
        self.express()
        return address

    def cloudpipe_express(self):
        # TODO: Test and see if the rule is in place
        private_ip = self.network[2]
        confirm_rule("FORWARD -d %s -p udp --dport 1194 -j ACCEPT" % (private_ip, ))
        confirm_rule("PREROUTING -t nat -d %s -p udp --dport %s -j DNAT --to %s:1194" % (self.external_vpn_ip, self.external_vpn_port, private_ip))
    
        
class PublicNetwork(Network):
    def __init__(self, conn=None, network="192.168.216.0/24", **kwargs):
        super(PublicNetwork, self).__init__(network=network, conn=conn, **kwargs)
        self.express()

    def allocate_ip(self, user_id, mac):
        for ip in self.range():
            address = str(ip)
            if not address in self.hosts.keys():
                logging.debug("Allocating IP %s to %s" % (address, user_id))
                self.hosts[address] = {
                    "address" : address, "user_id" : user_id, 'mac' : mac
                }
                self.express(address=address)
                return address
        raise NoMoreAddresses()
    
    def deallocate_ip(self, ip_str):
        if not ip_str in self.hosts:
            raise AddressNotAllocated()
        del self.hosts[ip_str]
        # TODO(joshua) SCRUB from the leases file somehow
        self.deexpress(address=ip_str)

    def associate_address(self, public_ip, private_ip, instance_id):
        if not public_ip in self.hosts:
            raise AddressNotAllocated()
        for addr in self.hosts.values():
            if addr.has_key('private_ip') and addr['private_ip'] == private_ip:
                raise AddressAlreadyAssociated()
        if self.hosts[public_ip].has_key('private_ip'):
            raise AddressAlreadyAssociated()
        self.hosts[public_ip]['private_ip'] = private_ip
        self.hosts[public_ip]['instance_id'] = instance_id
        self.express(address=public_ip)

    def disassociate_address(self, public_ip):
        if not public_ip in self.hosts:
            raise AddressNotAllocated()
        if not self.hosts[public_ip].has_key('private_ip'):
            raise AddressNotAssociated()
        self.deexpress(self.hosts[public_ip])
        del self.hosts[public_ip]['private_ip']
        del self.hosts[public_ip]['instance_id']
        # TODO Express the removal
    
    def deexpress(self, address):
        addr = self.hosts[address]
        public_ip = addr['address']
        private_ip = addr['private_ip']
        remove_rule("PREROUTING -t nat -d %s -j DNAT --to %s" % (public_ip, private_ip))
        remove_rule("POSTROUTING -t nat -s %s -j SNAT --to %s" % (private_ip, public_ip))
        remove_rule("FORWARD -d %s -p icmp -j ACCEPT" % (private_ip))
        for (protocol, port) in [("tcp",80), ("tcp",22), ("udp",1194), ("tcp",443)]:
            remove_rule("FORWARD -d %s -p %s --dport %s -j ACCEPT" % (private_ip, protocol, port))

    def express(self, address=None):
        logging.debug("Todo - need to create IPTables natting entries for this net.")
        addresses = self.hosts.values()
        if address:
            addresses = [self.hosts[address]]
        for addr in addresses:
            if not addr.has_key('private_ip'):
                continue
            public_ip = addr['address']
            private_ip = addr['private_ip']
            runthis("Binding IP to interface: %s", "sudo ip addr add %s dev %s" % (public_ip, FLAGS.public_interface))
            confirm_rule("PREROUTING -t nat -d %s -j DNAT --to %s" % (public_ip, private_ip))
            confirm_rule("POSTROUTING -t nat -s %s -j SNAT --to %s" % (private_ip, public_ip))
            # TODO: Get these from the secgroup datastore entries
            confirm_rule("FORWARD -d %s -p icmp -j ACCEPT" % (private_ip))
            for (protocol, port) in [("tcp",80), ("tcp",22), ("udp",1194), ("tcp",443)]:
                confirm_rule("FORWARD -d %s -p %s --dport %s -j ACCEPT" % (private_ip, protocol, port))


class NetworkPool(object):
    # TODO - Allocations need to be system global
    
    def __init__(self, netsize=256, startvlan=10, network="10.128.0.0/12"):
        self.network = IP(network)
        if not netsize in [4,8,16,32,64,128,256,512,1024]:
            raise NotValidNetworkSize()
        self.netsize = netsize
        self.startvlan = startvlan
    
    def get_from_vlan(self, vlan):
        start = (vlan-self.startvlan) * self.netsize
        net_str = "%s-%s" % (self.network[start], self.network[start + self.netsize - 1])
        logging.debug("Allocating %s" % net_str)
        return net_str

class VlanPool(object):
    def __init__(self, **kwargs):
        self.start = kwargs.get('start', FLAGS.vlan_start)
        self.end = kwargs.get('end', FLAGS.vlan_end)
        self.vlans = kwargs.get('vlans', {})
        self.vlanpool = {}
        self.manager = UserManager()
        for user_id, vlan in self.vlans.iteritems():
            self.vlanpool[vlan] = user_id
    
    def to_dict(self):
        return {'vlans': self.vlans,
                'start': self.start,
                'end':   self.end}
        
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
        def assign_vlan(user_id, vlan):
            self.vlans[user_id] = vlan
            self.vlanpool[vlan] = user_id
            return self.vlans[user_id]
        for old_user_id, vlan in self.vlans.iteritems():
            if not self.manager.get_user(old_user_id):
                KEEPER["%s-default" % old_user_id] = {}
                del KEEPER["%s-default" % old_user_id] 
                return assign_vlan(user_id, vlan)
        vlans = self.vlanpool.keys()
        vlans.append(self.start)
        nextvlan = max(vlans) + 1
        if nextvlan == self.end:
            raise AddressNotAllocated("Out of VLANs")
        return assign_vlan(user_id, nextvlan)

class NetworkController(GenericNode):
    """ The network controller is in charge of network connections  """

    def __init__(self, **kwargs):
        logging.debug("Starting up the network controller.")
        super(NetworkController, self).__init__(**kwargs)
        self.manager = UserManager()
        self._conn = self._get_connection()
        self.netsize = kwargs.get('netsize', FLAGS.network_size)
        if not KEEPER['vlans']:
            KEEPER['vlans'] = {'start' : FLAGS.vlan_start, 'end' : FLAGS.vlan_end}
        vlan_dict = kwargs.get('vlans', KEEPER['vlans'])
        self.vlan_pool = VlanPool.from_dict(vlan_dict)
        self.private_pool = kwargs.get('private_pool', NetworkPool(netsize=self.netsize, startvlan=KEEPER['vlans']['start'], network=FLAGS.private_range))
        self.private_nets = kwargs.get('private_nets', {})
        if not KEEPER['private']:
            KEEPER['private'] = {'networks' :[]}
        for net in KEEPER['private']['networks']:
            if self.manager.get_user(net['user_id']):
                self.get_users_network(net['user_id'])
        if not KEEPER['public']:
            KEEPER['public'] = kwargs.get('public', {'vlan': FLAGS.public_vlan, 'network' : FLAGS.public_range })
        self.public_net = PublicNetwork.from_dict(KEEPER['public'], conn=self._conn)

    def reset(self):
        KEEPER['public'] = {'vlan': FLAGS.public_vlan, 'network': FLAGS.public_range }
        KEEPER['private'] = {}
        KEEPER['vlans'] = {}
        # TODO : Get rid of old interfaces, bridges, and IPTables rules.

    def get_network_from_name(self, network_name):
        net_dict = KEEPER[network_name]
        if net_dict:
            #network_str = self.private_pool.next() # TODO, block allocations
            return PrivateNetwork.from_dict(net_dict)
        return None
        
    def get_public_ip_for_instance(self, instance_id):
        # FIXME: this should be a lookup - iteration won't scale
        for address_record in self.describe_addresses(type=PublicNetwork):
            if address_record.get(u'instance_id', 'free') == instance_id:
                return address_record[u'address']

    def get_users_network(self, user_id):
        user = self.manager.get_user(user_id)
        if not user:
           raise Exception("User %s doesn't exist, uhoh." % user_id)
        #if not self.private_nets.has_key(user_id):
        usernet = self.get_network_from_name("%s-default" % user_id)
        if not usernet:
            vlan = self.vlan_pool.next(user_id)
            network_str = self.private_pool.get_from_vlan(vlan)
            # logging.debug("Constructing network %s and %s for %s" % (network_str, vlan, user_id))
            usernet = PrivateNetwork(
                external_vpn_ip = user.vpn_ip,
                external_vpn_port = user.vpn_port,
                network = network_str,
                vlan = self.vlan_pool.vlans[user_id],
                conn = self._conn)
            KEEPER["%s-default" % user_id] = usernet.to_dict()
        self.private_nets[user_id] = usernet
        return self.private_nets[user_id]

    def get_cloudpipe_address(self, user_id, mac=None):
        net = self.get_users_network(user_id)
        ip = net.get_vpn_ip(user_id, mac)
        self._save()
        return (ip, net.name)
        
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
            if not self.manager.get_user(user_id):
                continue
            if address in self.get_users_network(user_id).network:
                rv = self.get_users_network(user_id).deallocate_ip(address)
                self._save()
                return rv
        raise AddressNotAllocated()

    def describe_addresses(self, type=PrivateNetwork):
        if type == PrivateNetwork:
            addresses = []
            for user_id in self.private_nets.keys(): 
                addresses.extend(self.get_users_network(user_id).list_addresses())
            return addresses
        return self.public_net.list_addresses()
        
    def associate_address(self, address, private_ip, instance_id):
        rv = self.public_net.associate_address(address, private_ip, instance_id)
        self._save()
        return rv
        
    def disassociate_address(self, address):
        rv = self.public_net.disassociate_address(address)
        self._save()
        return rv
        
    def _save(self):
        logging.debug("saving data")
        obj = {}
        obj['networks'] = []
        for user_id in self.private_nets.keys():
            if not self.manager.get_user(user_id):
                continue
            network = self.private_nets[user_id]
            #logging.debug("found private net")
            vlan = self.vlan_pool.vlans[user_id]
            obj['networks'].append({'user_id': user_id, 
                                    'network': str(network), 
                                    'vlan': vlan })
            KEEPER["%s-default" % user_id] = self.private_nets[user_id].to_dict()
        # logging.debug("done private net loop")
        KEEPER['private'] = obj
        KEEPER['public'] = self.public_net.to_dict()
        KEEPER['vlans'] = self.vlan_pool.to_dict()

    def express(self,address=None):
        return
        
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
