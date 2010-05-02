# COPYRIGHT NASA

import os, re, unittest
from commands import getstatusoutput
from paramiko import SSHClient, WarningPolicy, SSHException
from euca7ools.eucaadmin import Euca

EUCA_CLC_IP = '172.24.4.1'
EUCA_REGION = 'omega'
EUCA_ACCESS_KEY = 'WKy3rMzOWPouVOxK1p3Ar1C2uRBwa2FBXnCw'
EUCA_SECRET_KEY = 'iWEga5A8pYlV01SB469YdHMvs2tQdK8Sf14A6g'

BUCKET_NAME = 'smoketest'

class EucaTestCase(unittest.TestCase):
    def setUp(self):
        self.euca = Euca(
            EUCA_CLC_IP,
            EUCA_REGION,
            EUCA_ACCESS_KEY,
            EUCA_SECRET_KEY
        )
        
    def tearDown(self):
        self.euca = None
        
    def connect_ssh(self, ip, key_name):
        # TODO: set a more reasonable connection timeout time
        client = SSHClient()
        client.load_system_host_keys()
        client.set_missing_host_key_policy(WarningPolicy())
        return client.connect(ip, key_filename='/tmp/%s.pem' % key_name)
        
    def can_ping(self, ip):
        return getstatusoutput('ping -c 1 %s' % ip)[0] == 0
        
    def connection_for(self, username):
        return self.euca.connection_for(username)
        
    def create_user(self, username):
        return self.euca.create_user(username)
        
    def delete_user(self, username):
        return self.euca.delete_user(username)
    
    def create_key_pair(self, conn, key_name):
        try:
            os.remove('/tmp/%s.pem' % key_name)
        except:
            pass
        key = conn.create_key_pair(key_name)
        key.save('/tmp/')
        return key

    def delete_key_pair(self, conn, key_name):
        conn.delete_key_pair(key_name)
        try:
            os.remove('/tmp/%s.pem' % key_name)
        except:
            pass

    def bundle_image(self, image, kernel=False):
        cmd = 'euca-bundle-image -i %s' % image
        if kernel:
            cmd += ' --kernel true'
        status, output = getstatusoutput(cmd)
        print '\n' + output
        if status != 0:
            raise Exception(output)
        return True

    def upload_image(self, image):
        status, output = getstatusoutput('euca-upload-bundle -b %s -m /tmp/%s.manifest.xml' % (BUCKET_NAME, image))
        print '\n' + output
        if status != 0:
            raise Exception(output)
        return True

    def register_image(self, image):
        id = None
        status, output = getstatusoutput('euca-register %s/%s.manifest.xml' % (BUCKET_NAME, image))
        print '\n' + output
        if status == 0: 
            match = re.search('e[mrk]i-\w{8}', output)
            id = match.group(0)
        else:
            raise Exception(output)
        return id
    
    def setUp_test_image(self, image, kernel=False):
        self.bundle_image(image, kernel=kernel)
        self.upload_image(image)
        return self.register_image(image)

    def tearDown_test_image(self, conn, image_id):
        conn.deregister_image(image_id)
