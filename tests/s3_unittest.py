# vim: tabstop=4 shiftwidth=4 softtabstop=4
import logging
import StringIO
import time
import unittest
import hashlib
from xml.etree import ElementTree

import contrib
import mox
from tornado import ioloop
from twisted.internet import defer

import calllib
import s3server
import users
import exception
import flags
import test
import tempfile
import os

FLAGS = flags.FLAGS

tempdir = tempfile.mkdtemp(prefix='s3-')

FLAGS.fake_users   = True
FLAGS.buckets_path = os.path.join(tempdir, 'buckets')
FLAGS.images_path  = os.path.join(tempdir, 'images')


class S3TestCase(test.BaseTestCase):
    def setUp(self):
        super(S3TestCase, self).setUp()

        self.conn = calllib.Connection.instance()
        logging.getLogger().setLevel(logging.DEBUG)

        self.um = users.UserManager()
        self.um.create_user('user1')
        self.um.create_user('user2')
        self.um.create_user('admin_user', admin=True)

    def test_buckets(self):
        s3server.Bucket.create('new_bucket', self.um.get_user('user1'))
        bucket = s3server.Bucket('new_bucket')
        
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
        
    # fixme - test boto API of buckets/keys
        
        




