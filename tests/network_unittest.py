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
import node
import users
import network
import test


FLAGS = flags.FLAGS


class NetworkTestCase(unittest.TestCase):
    def setUp(self):
        FLAGS.fake_libvirt = True
        FLAGS.fake_network = True
        FLAGS.fake_rabbit = True
        FLAGS.fake_users = True
        super(NetworkTestCase, self).setUp()
        # self.node = node.Node()
        self.network = network.NetworkNode()
        logging.getLogger().setLevel(logging.DEBUG)
        
        # self.instance_id = "network-test"
        # rv = self.node.run_instance(self.instance_id)
    
    def test_allocate_deallocate_address(self):
        address = self.network.allocate_address("fake")
        logging.debug("Was allocated %s" % (address))
        self.assertEqual(True, address in self._get_user_addresses("fake"))
        rv = self.network.deallocate_address(address)
        self.assertEqual(False, address in self._get_user_addresses("fake"))

    def test_range_allocation(self):
        address = self.network.allocate_address("bill")
        secondaddress = self.network.allocate_address("sally")
        self.assertEqual(True, address in self._get_user_addresses("bill"))
        self.assertEqual(True, secondaddress in self._get_user_addresses("sally"))
        self.assertEqual(False, address in self._get_user_addresses("sally"))
        
    def test_subnet_edge(self):
        secondaddress = self.network.allocate_address("sally")
        for user in range(1,10):
            user_id = "user%s" % (user)
            address = self.network.allocate_address(user_id)
            address = self.network.allocate_address(user_id)
            address = self.network.allocate_address(user_id)
            self.assertEqual(False, address in self._get_user_addresses("sally"))
        
    def test_associate_deassociate_address(self):
        #raise NotImplementedError
        pass
        

    def _get_user_addresses(self, user_id):
        rv = self.network.describe_addresses()
        user_addresses = []
        for item in rv:
            logging.debug(item)
            if item['user_id'] == user_id:
                user_addresses.append(item['address'])
        return user_addresses
        