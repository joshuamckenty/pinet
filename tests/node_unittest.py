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
import test


FLAGS = flags.FLAGS


class InstanceXmlTestCase(test.BaseTestCase):
    def setUp(self):
        super(InstanceXmlTestCase, self).setUp()
        FLAGS.fake_libvirt = True
    
    def test_serialization(self):
        instance_id = 'foo'
        first_node = node.Node()
        inst = yield first_node.run_instance(instance_id)
        
        # force the state so that we can verify that it changes
        inst._s['state'] = node.Instance.NOSTATE
        xml = inst.toXml()
        self.assert_(ElementTree.parse(StringIO.StringIO(xml)))
        
        # spawn the instance to push its state along, so that we can test
        # that state is being set to the new state after fromXml
        # TODO(termie): this will probably break if inst.spawn() gets
        #               much smarter
        self.assertEqual(inst.state, node.Instance.NOSTATE)
        yield inst.spawn()
        self.assertEqual(inst.state, node.Instance.RUNNING)

        second_node = node.Node()
        new_inst = node.Instance.fromXml(second_node._conn, xml)
        self.assertEqual(new_inst.state, node.Instance.RUNNING)
        

class NodeFakeConnectionTestCase(test.BaseTestCase):
    def setUp(self):
        super(NodeFakeConnectionTestCase, self).setUp()
        FLAGS.fake_libvirt = True
        self.node = node.Node()
        logging.getLogger().setLevel(logging.DEBUG)
    
    def test_run_describe_terminate(self):
        instance_id = 'foo'

        rv = yield self.node.run_instance(instance_id)
        
        rv = yield self.node.describe_instances()
        self.assertEqual(rv, [instance_id])

        rv = yield self.node.terminate_instance(instance_id)

        rv = yield self.node.describe_instances()
        self.assertEqual(rv, [])

    def test_reboot(self):
        instance_id = 'foo'

        yield self.node.run_instance(instance_id)
        
        rv = yield self.node.describe_instances()
        self.assertEqual(rv, [instance_id])
        
        yield self.node.reboot_instance(instance_id)

        rv = yield self.node.describe_instances()
        self.assertEqual(rv, [instance_id])

    def test_console_output(self):
        instance_id = 'foo'
        rv = yield self.node.run_instance(instance_id)
        
        console = yield self.node.get_console_output(instance_id)
        self.assert_(console)

    def test_run_instance_existing(self):
        instance_id = 'foo'
        yield self.node.run_instance(instance_id)

        rv = yield self.node.describe_instances()
        self.assertEqual(rv, [instance_id])
        
        self.assertRaises(exception.Error, self.node.run_instance, instance_id)

if __name__ == '__main__':
    unittest.main()
