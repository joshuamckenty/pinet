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
import glob

tempdir = tempfile.mkdtemp(prefix='s3-')
# FIXME: delete all the tempdirs with the same prefix besides tempdir

FLAGS.fake_users   = True
FLAGS.buckets_path = os.path.join(tempdir, 'buckets')
FLAGS.images_path  = os.path.join(tempdir, 'images')
FLAGS.ca_path = os.path.join(os.path.dirname(__file__), 'CA')

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
        self.um.create_user('image_creator')
        image_user = self.um.get_user('image_creator')

        # create a bucket for our bundle
        Bucket.create('image_bucket', image_user)
        bucket = Bucket('image_bucket')
        
        # upload an image manifest/parts
        bundle_path = os.path.join(os.path.dirname(__file__), 'bundle')
        print 'bundle_path', bundle_path
        for path in glob.glob(bundle_path + '/*'):
            bucket[os.path.basename(path)] = open(path, 'rb').read()
        
        # register an image
        Image.create('i-testing', 'image_bucket/1mb.manifest.xml', image_user)
        
        # verify image
        my_img = Image('i-testing')
        result_image_file = os.path.join(my_img.path, 'image')
        self.assertEqual(os.stat(result_image_file).st_size, 1048576)
        
        sha = hashlib.sha1(open(result_image_file).read()).hexdigest()
        self.assertEqual(sha, '3b71f43ff30f4b15b5cd85dd9e95ebc7e84eb5a3')
        
        # verify image permissions
        new_user = self.um.get_user('new_user')
        self.assert_(my_img.is_authorized(new_user) == False)

    def test_http_api(self):
        pass
        
    # fixme - test boto API of buckets/keys
        
        




