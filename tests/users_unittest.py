import unittest
import flags

from users import UserManager
from M2Crypto import RSA, BIO

FLAGS = flags.FLAGS
FLAGS.fake_libvirt = True
FLAGS.fake_users = True

class UserTests(unittest.TestCase):
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
        user.create_public_key('public', 'arbitrarykey')
        self.assertEqual('arbitrarykey', user.get_public_key('public'))

    def test_007_test_key_generation(self):
        private_key = self.users.get_user('test1').create_key_pair('public2')
        key = RSA.load_key_string(private_key, callback=lambda: None)
        bio = BIO.MemoryBuffer()
        key.save_pub_key_bio(bio)
        self.assertEqual(self.users.get_user('test1').get_public_key('public2'),
                         bio.read())
        data = 'Some Random Text to sign!'
        key.save_pub_key_bio(bio)
        pubkey = RSA.load_pub_key_bio(bio)
        sign = key.sign(data)
        self.assertTrue(pubkey.verify(data, sign))
    
    def test_008_can_delete_public_key(self):
        self.users.get_user('test1').delete_public_key('public')

    def test_009_can_delete_user(self):
        self.users.delete_user('test1')


        
if __name__ == "__main__":
    # TODO: Implement use_fake as an option
    unittest.main()
