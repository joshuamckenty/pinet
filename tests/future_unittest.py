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

import rpc
import cloud
import exception
import flags
import node
import test


FLAGS = flags.FLAGS


class AdminTestCase(test.BaseTestCase):
    def setUp(self):
        super(AdminTestCase, self).setUp()
        FLAGS.fake_libvirt = True
        FLAGS.fake_rabbit = True

        self.conn = rpc.Connection.instance()

        logging.getLogger().setLevel(logging.INFO)

        # set up our cloud
        self.cloud = cloud.CloudController()
        self.cloud_consumer = rpc.AdapterConsumer(connection=self.conn,
                                                      topic=FLAGS.cloud_topic,
                                                      proxy=self.cloud)
        self.injected.append(self.cloud_consumer.attach_to_tornado(self.ioloop))
        
        # set up a node
        self.node = node.Node()
        self.node_consumer = rpc.AdapterConsumer(connection=self.conn,
                                                     topic=FLAGS.compute_topic,
                                                     proxy=self.node)
        self.injected.append(self.node_consumer.attach_to_tornado(self.ioloop))

    def test_flush_terminated(self):
        # Launch an instance

        # Wait until it's running

        # Terminate it

        # Wait until it's terminated

        # Flush terminated nodes

        # ASSERT that it's gone
        pass
