# vim: tabstop=4 shiftwidth=4 softtabstop=4
import logging
import unittest

from nova.flags import FLAGS
from nova.compute import network
from nova.auth import users
from IPy import IP



class NetworkTestCase(unittest.TestCase):
    def setUp(self):
        logging.getLogger().setLevel(logging.DEBUG)
        super(NetworkTestCase, self).setUp()
        self.network = network.NetworkController(netsize=16)
        self.manager = users.UserManager()
        for i in range(0, 6):
            name = 'user%s' % i
            self.manager.create_user(name, name, name)
        # self.instance_id = "network-test"
        # rv = self.node.run_instance(self.instance_id)
    
    def tearDown(self):
        super(NetworkTestCase, self).tearDown()
        for i in range(0, 6):
            name = 'user%s' % i
            self.manager.delete_user(name)

    
    def test_network_serialization(self):
        net1 = network.Network(vlan=100, network="192.168.100.0/24", conn=None)
        address = net1.allocate_ip("user0", "01:24:55:36:f2:a0")
        net_json = str(net1)
        net2 = network.Network.from_json(net_json)
        self.assertEqual(net_json, str(net2))
        self.assertTrue(IP(address) in net2.network)
    
    def test_allocate_deallocate_address(self):
        (address, net_name) = self.network.allocate_address("user0", "01:24:55:36:f2:a0")
        logging.debug("Was allocated %s" % (address))
        self.assertEqual(True, address in self._get_user_addresses("user0"))
        rv = self.network.deallocate_address(address)
        self.assertEqual(False, address in self._get_user_addresses("user0"))

    def test_range_allocation(self):
        (address, net_name) = self.network.allocate_address("user0", "01:24:55:36:f2:a0")
        (secondaddress, net_name) = self.network.allocate_address("user1", "01:24:55:36:f2:a0")
        self.assertEqual(True, address in self._get_user_addresses("user0"))
        self.assertEqual(True, secondaddress in self._get_user_addresses("user1"))
        self.assertEqual(False, address in self._get_user_addresses("user1"))
        rv = self.network.deallocate_address(address)
        self.assertEqual(False, address in self._get_user_addresses("user0"))
        rv = self.network.deallocate_address(secondaddress)
        self.assertEqual(False, secondaddress in self._get_user_addresses("user1"))
        
        
    def test_subnet_edge(self):
        (secondaddress, net_name) = self.network.allocate_address("user0")
        for user in range(1,5):
            user_id = "user%s" % (user)
            (address, net_name) = self.network.allocate_address(user_id, "01:24:55:36:f2:a0")
            (address2, net_name) = self.network.allocate_address(user_id, "01:24:55:36:f2:a0")
            (address3, net_name) = self.network.allocate_address(user_id, "01:24:55:36:f2:a0")
            self.assertEqual(False, address in self._get_user_addresses("user0"))
            self.assertEqual(False, address2 in self._get_user_addresses("user0"))
            self.assertEqual(False, address3 in self._get_user_addresses("user0"))
            rv = self.network.deallocate_address(address)
            rv = self.network.deallocate_address(address2)
            rv = self.network.deallocate_address(address3)
        rv = self.network.deallocate_address(secondaddress)

    def test_too_many_users(self):
        for i in range(0, 30):
            name = 'toomany-user%s' % i
            self.manager.create_user(name, name, name)
            (address, net_name) = self.network.allocate_address(name, "01:24:55:36:f2:a0")
            self.manager.delete_user(name)
        
        
    def test_associate_deassociate_address(self):
        #raise NotImplementedError
        pass

    def _get_user_addresses(self, user_id):
        rv = self.network.describe_addresses()
        user_addresses = []
        for item in rv:
            if item['user_id'] == user_id:
                user_addresses.append(item['address'])
        return user_addresses
