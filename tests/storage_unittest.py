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


class StorageFakeTestCase(test.BaseTestCase):
    def setUp(self):
        super(StorageFakeTestCase, self).setUp()
        FLAGS.fake_libvirt = True
        FLAGS.fake_storage = True
        self.node = node.Node()
        self.storage = storage.FakeBlockStore()
        logging.getLogger().setLevel(logging.DEBUG)
        # Create one volume and one node to test with
        self.instance_id = "storage-test"
        vol_size = "500"
        self.test_volume = yield self.storage.create_volume(vol_size)
        rv = yield self.node.run_instance(self.instance_id)
    
    def test_run_create_volume(self):
        vol_size = '500'
        volume = yield self.storage.create_volume(vol_size)
        rv = yield self.storage.describe_volumes()
        
        # Volumes have to be sorted by timestamp in order to work here...
        self.assertEqual(volume.volume_id, rv["volumeSet"][-1]["item"]["volumeId"])
        rv = yield self.storage.delete_volume(volume.volume_id)
        self.assertRaises(exception.Error, self.storage.get_volume, volume.volume_id)

    def test_run_attach_detach_volume(self):
        rv = yield self.storage.attach_volume(self.test_volume.volume_id, self.instance_id, "/dev/sdf")
        self.assertEqual(self.test_volume.get_status(), "attached")
        # TODO - assert that it's attached to the right instance
        
        rv = yield self.storage.detach_volume(self.test_volume.volume_id)
        self.assertEqual(self.test_volume.get_status(), "detached")
