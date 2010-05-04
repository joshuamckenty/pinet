# vim: tabstop=4 shiftwidth=4 softtabstop=4
import logging
import unittest
import hashlib

import nova.contrib
import mox
from tornado import ioloop
from twisted.internet import defer

from nova import rpc
from nova.objectstore import Bucket, Image, Object, handler
from nova.auth import users
import nova.exception
from nova.objectstore.flags import FLAGS
import test
import tempfile
import os
import glob
import shutil

tempdir = tempfile.mkdtemp(prefix='test_oss-')

# delete tempdirs from previous runs (we don't delete after test to allow
# checking the contents after running tests)

for path in glob.glob(os.path.abspath(os.path.join(tempdir, '../test_oss-*'))):
    if path != tempdir:
        shutil.rmtree(path)

# create bucket/images path
os.makedirs(os.path.join(tempdir, 'images'))
os.makedirs(os.path.join(tempdir, 'buckets'))

class ObjectStoreTestCase(test.BaseTestCase):
    def setUp(self):
        super(ObjectStoreTestCase, self).setUp()
        FLAGS.fake_users   = True
        FLAGS.buckets_path = os.path.join(tempdir, 'buckets')
        FLAGS.images_path  = os.path.join(tempdir, 'images')
        FLAGS.ca_path = os.path.join(os.path.dirname(__file__), 'CA')

        self.conn = rpc.Connection.instance()
        logging.getLogger().setLevel(logging.DEBUG)

        self.um = users.UserManager()

    def tearDown(self):
        FLAGS.Reset()
        super(ObjectStoreTestCase, self).tearDown()

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

# class ApiObjectStoreTestCase(test.BaseTestCase):
#     def setUp(self):
#         super(ApiObjectStoreTestCase, self).setUp()
#         FLAGS.fake_users   = True
#         FLAGS.buckets_path = os.path.join(tempdir, 'buckets')
#         FLAGS.images_path  = os.path.join(tempdir, 'images')
#         FLAGS.ca_path = os.path.join(os.path.dirname(__file__), 'CA')
#
#         self.users = users.UserManager()
#         self.app  = handler.Application(self.users)
#
#         self.host = '127.0.0.1'
#
#         self.conn = boto.s3.connection.S3Connection(
#             aws_access_key_id=user.access,
#             aws_secret_access_key=user.secret,
#             is_secure=False,
#             calling_format=boto.s3.connection.OrdinaryCallingFormat(),
#             port=FLAGS.s3_port,
#             host=FLAGS.s3_host)
#
#         self.mox.StubOutWithMock(self.ec2, 'new_http_connection')
#
#     def tearDown(self):
#         FLAGS.Reset()
#         super(ApiObjectStoreTestCase, self).tearDown()
#
#     def test_describe_instances(self):
#         self.expect_http()
#         self.mox.ReplayAll()
#
#         self.assertEqual(self.ec2.get_all_instances(), [])
