import unittest
import flags

from users import UserManager

FLAGS = flags.FLAGS
FLAGS.fake_libvirt = True

class UserTests(unittest.TestCase):
    users = UserManager(config={ 'use_fake': FLAGS.fake_libvirt })
    
    def test_001_can_create_user(self):
        self.users.create('test1', 'access', 'secret')

    def test_002_can_get_keys(self):
        keys = self.users.keys('test1')
        self.assertEqual(keys, ('access', 'secret'))

    def test_003_can_retreive_secret(self):
        self.assertEqual('secret', self.users.get_secret_from_access('access'))

    def test_004_signature_is_valid(self):
        #self.assertTrue(self.users.authenticate( **boto.generate_url ... ? ? ? ))
        raise NotImplementedError

    def test_005_can_download_credentials(self):
        raise NotImplementedError
    
    def test_006_can_create_key_pair(self):
        self.private = self.users.create_key_pair_from_access('access', 'public')

    def test_007_can_retrieve_public_key(self):
        self.public = self.users.get_public_key_from_access('access', 'public')

    
    def test_008_public_and_private_keys_match(self):
        raise NotImplementedError
    
    def test_009_can_delete_key_pair(self):
        self.users.delete_key_pair_from_access('access', 'public')

    def test_010_can_delete_user(self):
        self.users.delete('test1')


        
if __name__ == "__main__":
    # TODO: Implement use_fake as an option
    unittest.main()
