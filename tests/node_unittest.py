# vim: tabstop=4 shiftwidth=4 softtabstop=4
import logging
import unittest
import time

import contrib
import libvirt
import mox
from tornado import ioloop
from twisted.internet import defer

import exception
import node
import test

class NodeTestCase(mox.MoxTestBase):
    def setUp(self):
        super(NodeTestCase, self).setUp()

        # we aren't going to actually use libvirt's connection
        self.mox.StubOutWithMock(libvirt, 'openAuth')
        self.conn = self.mox.CreateMockAnything()
        
    def expectOpenAuth(self):
        """ usual boilerplate expecting node.Node to be created """
        libvirt.openAuth(mox.IgnoreArg(), mox.IgnoreArg(), mox.IgnoreArg()
                ).AndReturn(self.conn)

    def test_basic(self):
        """ test that we can instantiate a node """
        self.expectOpenAuth()
        self.mox.ReplayAll()
        my_node = node.Node()

    def test_describe_instances_basic(self):
        """ test that describe_instances does anything """
        self.expectOpenAuth()
        self.conn.listDomainsID().AndReturn([])

        self.mox.ReplayAll()
        my_node = node.Node()
        instances = my_node.describe_instances()

    def test_run_instance_basic(self):
        """ test that run_instance does something """
        instance_id = 'foo'
        self.mox.StubOutWithMock(node, 'Instance', use_mock_anything=True)

        self.expectOpenAuth()
        node.Instance(self.conn, instance_id, options=None)

        self.mox.ReplayAll()
        my_node = node.Node()
        my_node.run_instance(instance_id)

    def test_run_instance_instance_errors(self):
        instance_id = 'foo'

        self.mox.StubOutWithMock(node, 'Instance', use_mock_anything=True)
        self.expectOpenAuth()
        node.Instance(self.conn, instance_id, options=None).AndRaise(
                Exception('I Should Be Turned Into An exception.Error'))

        self.mox.ReplayAll()
        my_node = node.Node()
        self.assertRaises(exception.Error, my_node.run_instance, instance_id)

    def test_run_instance_setup_errors(self):
        instance_id = 'foo'

        self.mox.StubOutWithMock(node.Instance, 'setup')
        self.expectOpenAuth()
        node.Instance.setup().AndRaise(
                Exception('I Should Be Turned Into An exception.Error'))

        self.mox.ReplayAll()
        my_node = node.Node()
        self.assertRaises(exception.Error, my_node.run_instance, instance_id)

    def test_run_instance_connection_errors(self):
        instance_id = 'foo'

        self.mox.StubOutWithMock(node.Instance, 'setup')
        self.expectOpenAuth()
        node.Instance.setup().AndReturn('xml')
        self.conn.createXML('xml', 0).AndRaise(
                Exception('I Should Be Turned Into An exception.Error'))

        self.mox.ReplayAll()
        my_node = node.Node()
        self.assertRaises(exception.Error, my_node.run_instance, instance_id)

    def test_terminate_instance_basic(self):
        """ test that terminate_instance does something """
        instance_id = 'foo'
        
        mock_instance = self.mox.CreateMockAnything()
        self.expectOpenAuth()
        self.conn.lookupByName(instance_id).AndReturn(mock_instance)
        mock_instance.destroy()

        self.mox.ReplayAll()
        my_node = node.Node()
        my_node.terminate_instance(instance_id)


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
