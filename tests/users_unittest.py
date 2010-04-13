import unittest
import flags

from users import UserManager

FLAGS = flags.FLAGS
FLAGS.fake_libvirt = True
FLAGS.fake_users = True

class UserTests(unittest.TestCase):
    users = UserManager()
    
    def test_001_can_create_user(self):
        self.users.create('test1', 'access', 'secret')

    def test_002_can_get_keys(self):
        keys = self.users.keys('test1')
        self.assertEqual(len(keys), 2)

    def test_003_can_retreive_secret(self):
        self.assertEqual('secret', self.users.get_secret_from_access('access'))

    def test_004_signature_is_valid(self):
        #self.assertTrue(self.users.authenticate( **boto.generate_url ... ? ? ? ))
        raise NotImplementedError

    def test_005_can_download_credentials(self):
        raise NotImplementedError

    def test_006_can_delete_user(self):
        self.users.delete('test1')


        
if __name__ == "__main__":
    # TODO: Implement use_fake as an option
    unittest.main()
