# vim: tabstop=4 shiftwidth=4 softtabstop=4
import logging
import unittest
import time

import contrib
import mox
from tornado import ioloop
from twisted.internet import defer

import exception
import node
import test


class FakeOptions(object):
    use_fake = True


class NodeFakeConnectionTestCase(test.BaseTestCase):
    def setUp(self):
        super(NodeFakeConnectionTestCase, self).setUp()

        self.node = node.Node(FakeOptions())
        logging.getLogger().setLevel(logging.DEBUG)
    
    def test_run_describe_terminate(self):
        instance_id = 'foo'

        yield self.node.run_instance(instance_id)
        
        rv = yield self.node.describe_instances()
        self.assertEqual(rv, [instance_id])

        rv = yield self.node.terminate_instance(instance_id)

        rv = yield self.node.describe_instances()
        self.assertEqual(rv, [])

    def test_reboot(self):
        instance_id = 'foo'

        # can't reboot if not running
        #self.assertRaises(exception.Error,
        #                  yield self.node.reboot_instance,
        #                  instance_id)

        yield self.node.run_instance(instance_id)
        
        rv = yield self.node.describe_instances()
        self.assertEqual(rv, [instance_id])
        
        yield self.node.reboot_instance(instance_id)

        rv = yield self.node.describe_instances()
        self.assertEqual(rv, [instance_id])

    def test_run_instance_existing(self):
        instance_id = 'foo'
        yield self.node.run_instance(instance_id)

        rv = yield self.node.describe_instances()
        self.assertEqual(rv, [instance_id])
        
        self.assertRaises(exception.Error, self.node.run_instance, instance_id)

if __name__ == '__main__':
    unittest.main()
