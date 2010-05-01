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
from nova.volume import storage
import test


FLAGS = flags.FLAGS


class StorageTestCase(unittest.TestCase):
    def setUp(self):
        logging.getLogger().setLevel(logging.DEBUG)
        super(StorageTestCase, self).setUp()
        self.mynode = node.Node()
        self.mystorage = None
        if FLAGS.fake_storage:
            self.mystorage = storage.FakeBlockStore()
        else:
            self.mystorage = storage.BlockStore()
    
    def test_run_create_volume(self):
        vol_size = '500'
        user_id = 'fake'
        volume = self.mystorage.create_volume(vol_size, user_id)
        rv = self.mystorage.describe_volumes()
        
        # Volumes have to be sorted by timestamp in order to work here...
        self.assertEqual(volume.volume_id, self.mystorage.get_volume(volume.volume_id).volume_id)

        rv = self.mystorage.delete_volume(volume.volume_id)
        self.assertRaises(exception.Error, self.mystorage.get_volume, volume.volume_id)

    def test_run_attach_detach_volume(self):
        # Create one volume and one node to test with
        self.instance_id = "storage-test"
        rv = self.mynode.run_instance(self.instance_id)
        vol_size = "500"
        user_id = "fake"
        self.test_volume = self.mystorage.create_volume(vol_size, user_id)
        rv = self.mystorage.attach_volume(self.test_volume.volume_id, self.instance_id, "/dev/sdf")
        self.assertEqual(self.test_volume.get_status(), "attached")
        # TODO - assert that it's attached to the right instance
        
        rv = self.mystorage.detach_volume(self.test_volume.volume_id)
        self.assertEqual(self.test_volume.get_status(), "available")