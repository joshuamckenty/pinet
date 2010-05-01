# vim: tabstop=4 shiftwidth=4 softtabstop=4
import logging
import StringIO
import time
import unittest
from xml.etree import ElementTree

import contrib
import mox
from tornado import ioloop
from twisted.internet import defer

import exception
import flags
from nova.compute import node
from nova.auth import users
from nova.compute import network
import test
from IPy import IP


FLAGS = flags.FLAGS


class NetworkTestCase(unittest.TestCase):
    def setUp(self):
        logging.getLogger().setLevel(logging.DEBUG)
        super(NetworkTestCase, self).setUp()
        self.network = network.NetworkController()
        
        # self.instance_id = "network-test"
        # rv = self.node.run_instance(self.instance_id)
        
    def test_network_serialization(self):
        net1 = network.Network(vlan=100, network="192.168.100.0/24", conn=None)
        address = net1.allocate_ip("fake", "01:24:55:36:f2:a0")
        net_json = str(net1)
        net2 = network.Network.from_json(net_json)
        self.assertEqual(net_json, str(net2))
        self.assertTrue(IP(address) in net2.network)
    
    def test_allocate_deallocate_address(self):
        (address, net_name) = self.network.allocate_address("fake", "01:24:55:36:f2:a0")
        logging.debug("Was allocated %s" % (address))
        self.assertEqual(True, address in self._get_user_addresses("fake"))
        rv = self.network.deallocate_address(address)
        self.assertEqual(False, address in self._get_user_addresses("fake"))

    def test_range_allocation(self):
        (address, net_name) = self.network.allocate_address("bill", "01:24:55:36:f2:a0")
        (secondaddress, net_name) = self.network.allocate_address("sally", "01:24:55:36:f2:a0")
        self.assertEqual(True, address in self._get_user_addresses("bill"))
        self.assertEqual(True, secondaddress in self._get_user_addresses("sally"))
        self.assertEqual(False, address in self._get_user_addresses("sally"))
        rv = self.network.deallocate_address(address)
        self.assertEqual(False, address in self._get_user_addresses("bill"))
        rv = self.network.deallocate_address(secondaddress)
        self.assertEqual(False, secondaddress in self._get_user_addresses("sally"))
        
        
    def test_subnet_edge(self):
        (secondaddress, net_name) = self.network.allocate_address("sally")
        for user in range(1,5):
            user_id = "user%s" % (user)
            (address, net_name) = self.network.allocate_address(user_id, "01:24:55:36:f2:a0")
            (address2, net_name) = self.network.allocate_address(user_id, "01:24:55:36:f2:a0")
            (address3, net_name) = self.network.allocate_address(user_id, "01:24:55:36:f2:a0")
            self.assertEqual(False, address in self._get_user_addresses("sally"))
            self.assertEqual(False, address2 in self._get_user_addresses("sally"))
            self.assertEqual(False, address3 in self._get_user_addresses("sally"))
            rv = self.network.deallocate_address(address)
            rv = self.network.deallocate_address(address2)
            rv = self.network.deallocate_address(address3)
        rv = self.network.deallocate_address(secondaddress)
        
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
        
