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

import calllib
import cloud
import exception
import flags
import node
import test


FLAGS = flags.FLAGS


class CloudTestCase(test.BaseTestCase):
    def setUp(self):
        super(CloudTestCase, self).setUp()
        FLAGS.fake_libvirt = False
        FLAGS.fake_rabbit = False

        self.conn = calllib.Connection.instance()

        logging.getLogger().setLevel(logging.INFO)

        # set up our cloud
        self.cloud = cloud.CloudController()
        self.cloud_consumer = calllib.AdapterConsumer(connection=self.conn,
                                                      topic=FLAGS.cloud_topic,
                                                      proxy=self.cloud)
        self.injected.append(self.cloud_consumer.attach_to_tornado(self.ioloop))
        
        # set up a node
        self.node = node.Node()
        self.node_consumer = calllib.AdapterConsumer(connection=self.conn,
                                                     topic=FLAGS.node_topic,
                                                     proxy=self.node)
        self.injected.append(self.node_consumer.attach_to_tornado(self.ioloop))

    def test_console_output(self):
        instance_id = 'foo'
        inst = yield self.node.run_instance(instance_id)

        output = yield self.cloud.get_console_output(None, [instance_id])
        self.assert_(output)

    def test_run_instances(self):
        image_id = FLAGS.default_image
        instance_type = FLAGS.default_instance_type
        max_count = 2
        kwargs = {'image_id': image_id,
                  'instance_type': instance_type,
                  'max_count': max_count}
        rv = yield self.cloud.run_instances(None, **kwargs)
        # TODO: check for proper response
        self.assert_(rv)
