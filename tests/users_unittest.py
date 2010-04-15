import unittest
import flags
import test

from users import UserManager
from M2Crypto import RSA, BIO

FLAGS = flags.FLAGS
FLAGS.fake_libvirt = True
FLAGS.fake_users = True

class UserTests(test.BaseTestCase):
    users = UserManager()
    
    def test_001_can_create_user(self):
        self.users.create_user('test1', 'access', 'secret')

    def test_002_can_get_user(self):
        user = self.users.get_user('test1')

    def test_003_can_retreive_properties(self):
        user = self.users.get_user('test1')
        self.assertEqual('test1', user.id)
        self.assertEqual('access', user.access)
        self.assertEqual('secret', user.secret)

    def test_004_signature_is_valid(self):
        #self.assertTrue(self.users.authenticate( **boto.generate_url ... ? ? ? ))
        raise NotImplementedError

    def test_005_can_download_credentials(self):
        raise NotImplementedError
    
    def test_006_test_key_storage(self):
        user = self.users.get_user('test1')
        user.create_key_pair('public', 'key', 'fingerprint')
        key = user.get_key_pair('public')
        self.assertEqual('key', key.public_key)
        self.assertEqual('fingerprint', key.fingerprint)

    def test_007_test_key_generation(self):
        private_key, fingerprint = self.users.get_user('test1').generate_key_pair('public2')
        key = RSA.load_key_string(private_key, callback=lambda: None)
        bio = BIO.MemoryBuffer()
        key.save_pub_key_bio(bio)
        self.assertEqual(self.users.get_user('test1').get_key_pair('public2').public_key,
                         bio.read())
        data = 'Some Random Text to sign!'
        key.save_pub_key_bio(bio)
        pubkey = RSA.load_pub_key_bio(bio)
        sign = key.sign(data)
        self.assertTrue(pubkey.verify(data, sign))
    
    def test_008_can_list_key_pairs(self):
        keys = self.users.get_user('test1').get_key_pairs()
        self.assertTrue(filter(lambda k: k.name == 'public', keys))
        self.assertTrue(filter(lambda k: k.name == 'public2', keys))

    def test_009_can_delete_key_pair(self):
        self.users.get_user('test1').delete_key_pair('public')
        keys = self.users.get_user('test1').get_key_pairs()
        self.assertFalse(filter(lambda k: k.name == 'public', keys))

    def test_010_can_list_users(self):
        users = self.users.get_users()
        self.assertTrue(filter(lambda u: u.id == 'test1', users))
        
    def test_011_can_delete_user(self):
        self.users.delete_user('test1')
        users = self.users.get_users()
        self.assertFalse(filter(lambda u: u.id == 'test1', users))
        
if __name__ == "__main__":
    # TODO: Implement use_fake as an option
    unittest.main()
