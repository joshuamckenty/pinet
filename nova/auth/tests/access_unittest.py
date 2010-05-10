import os
import unittest
import flags
import test
from nova.endpoint import cloud
import logging

from nova.auth.users import UserManager

FLAGS = flags.FLAGS

class AccessTestCase(test.BaseTestCase):
    def setUp(self):
        FLAGS.fake_libvirt = True
        FLAGS.fake_storage = True
        self.users = UserManager()
        super(AccessTestCase, self).setUp()
        # Make a test project
        # Make a test user
        self.users.create_user('test1', 'access', 'secret')
        
        # Make the test user a member of the project
        
    def tearDown(self):
        # Delete the test user
        # Delete the test project
        self.users.delete_user('test1')
        pass
    
    def test_001_basic_user_access(self):
        user = self.users.get_user('test1')
        # instance-foo, should be using object and not owner_id
        instance_id = "i-12345678"
        self.assertTrue(user.is_authorized(instance_id, action="describe_instances"))

    def test_002_sysadmin_access(self):
        user = self.users.get_user('test1')
        bucket = "foo/bar/image"
        self.assertFalse(user.is_authorized(bucket, action="register"))
        self.users.add_role(user, "sysadmin")


if __name__ == "__main__":
    # TODO: Implement use_fake as an option
    unittest.main()
