# vim: tabstop=4 shiftwidth=4 softtabstop=4
import logging
import StringIO
import time
import unittest
import hashlib

import nova.contrib
import mox
from tornado import ioloop
from twisted.internet import defer

from nova import rpc
from nova.objectstore import Bucket, Image, Object
from nova.auth import users
import nova.exception
from nova.objectstore.flags import FLAGS
import test
import tempfile
import os

tempdir = tempfile.mkdtemp(prefix='s3-')

FLAGS.fake_users   = True
FLAGS.buckets_path = os.path.join(tempdir, 'buckets')
FLAGS.images_path  = os.path.join(tempdir, 'images')


class ObjectStoreTestCase(test.BaseTestCase):
    def setUp(self):
        super(ObjectStoreTestCase, self).setUp()

        self.conn = rpc.Connection.instance()
        logging.getLogger().setLevel(logging.DEBUG)

        self.um = users.UserManager()

    def test_buckets(self):
        self.um.create_user('user1')
        self.um.create_user('user2')
        self.um.create_user('admin_user', admin=True)
        
        Bucket.create('new_bucket', self.um.get_user('user1'))
        bucket = Bucket('new_bucket')
        
        # creator is authorized to use bucket
        self.assert_(bucket.is_authorized(self.um.get_user('user1')))
        
        # another user is not authorized
        self.assert_(bucket.is_authorized(self.um.get_user('user2')) == False)
        
        # admin is authorized to use bucket
        self.assert_(bucket.is_authorized(self.um.get_user('admin_user')))
        
        # new buckets are empty
        self.assert_(bucket.list_keys()['Contents'] == [])
        
        # storing keys works
        bucket['foo'] = "bar"
        
        self.assert_(len(bucket.list_keys()['Contents']) == 1)
        
        self.assert_(bucket['foo'].read() == 'bar')
        
        # md5 of key works
        self.assert_(bucket['foo'].md5 == hashlib.md5('bar').hexdigest())
        
        # deleting non-empty bucket throws exception
        exception = False
        try:
            bucket.delete()
        except:
            exception = True
        
        self.assert_(exception)
        
        # deleting key
        del bucket['foo']
        
        # deleting empty button
        bucket.delete()
        
        # accessing deleted bucket throws exception
        exception = False
        try:
            s3server.Bucket('new_bucket')
        except:
            exception = True
        
        self.assert_(exception)
        
    def test_images(self):
        # TODO: generate a random image
        # TODO: bundling using euca-bundle-image
        # TODO: upload to bucket
        # TODO: register
        # TODO: verify that md5 and size are same
        # TODO: verify that only user can see it        
        pass
    
    def test_http_api(self):
        pass
        
    # fixme - test boto API of buckets/keys
        
        




