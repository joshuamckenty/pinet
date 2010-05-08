import unittest
from nova import flags
import test
from nova.endpoint import cloud
import logging
from nova import utils

from nova.auth.users import UserManager
from M2Crypto import RSA, BIO, X509
from nova import crypto

FLAGS = flags.FLAGS

class UserTestCase(test.BaseTestCase):
    def setUp(self):
        FLAGS.fake_libvirt = True
        FLAGS.fake_storage = True
        self.users = UserManager()
        super(UserTestCase, self).setUp()
    
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
        pass
        #raise NotImplementedError

    def test_005_can_get_credentials(self):
        return
        credentials = self.users.get_user('test1').get_credentials()
        self.assertEqual(credentials,
        'export EC2_ACCESS_KEY="access"\n' +
        'export EC2_SECRET_KEY="secret"\n' +
        'export EC2_URL="http://127.0.0.1:8773/services/Cloud"\n' +
        'export S3_URL="http://127.0.0.1:3333/"\n' +
        'export EC2_USER_ID="test1"\n')

    
    def test_006_test_key_storage(self):
        user = self.users.get_user('test1')
        user.create_key_pair('public', 'key', 'fingerprint')
        key = user.get_key_pair('public')
        self.assertEqual('key', key.public_key)
        self.assertEqual('fingerprint', key.fingerprint)

    def test_007_test_key_generation(self):
        user = self.users.get_user('test1')
        private_key, fingerprint = user.generate_key_pair('public2')
        key = RSA.load_key_string(private_key, callback=lambda: None)
        bio = BIO.MemoryBuffer()
        public_key = user.get_key_pair('public2').public_key
        key.save_pub_key_bio(bio)
        converted = crypto.ssl_pub_to_ssh_pub(bio.read())
        # assert key fields are equal
        self.assertEqual(public_key.split(" ")[1].strip(),
                         converted.split(" ")[1].strip())
    
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

    def test_011_can_generate_x509(self):
        # MUST HAVE RUN CLOUD SETUP BY NOW
        self.cloud = cloud.CloudController()
        self.cloud.setup()
        private_key, signed_cert_string = self.users.get_user('test1').generate_x509_cert()
        logging.debug(signed_cert_string)
        
        # Need to verify that it's signed by the right intermediate CA
        full_chain = self.cloud.fetch_ca(username='test1', chain=True)
        int_cert = self.cloud.fetch_ca(username='test1', chain=False)
        cloud_cert = self.cloud.fetch_ca()
        logging.debug("CA chain:\n\n =====\n%s\n\n=====" % full_chain)
        signed_cert = X509.load_cert_string(signed_cert_string)
        chain_cert = X509.load_cert_string(full_chain)
        int_cert = X509.load_cert_string(int_cert)
        cloud_cert = X509.load_cert_string(cloud_cert)
        self.assertTrue(signed_cert.verify(chain_cert.get_pubkey()))
        self.assertTrue(signed_cert.verify(int_cert.get_pubkey()))
        self.assertFalse(signed_cert.verify(cloud_cert.get_pubkey()))
        
    def test_012_can_delete_user(self):
        self.users.delete_user('test1')
        users = self.users.get_users()
        if users != None:
            self.assertFalse(filter(lambda u: u.id == 'test1', users))
    
        
if __name__ == "__main__":
    # TODO: Implement use_fake as an option
    unittest.main()
