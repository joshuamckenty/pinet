# COPYRIGHT NASA

import os, re, unittest, sys
from commands import getstatusoutput
from paramiko import SSHClient, WarningPolicy, SSHException

BUCKET_NAME = 'smoketest'

from nova.auth.users import UserManager
admin = UserManager().get_user('admin')
if admin is None:
    print 'Unable to load credentials for admin user'
    sys.exit(2)

from nova.adminclient import NovaAdminClient
admin = NovaAdminClient(access_key=admin.access, secret_key=admin.secret)

class NovaTestCase(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def connect_ssh(self, ip, key_name):
        # TODO: set a more reasonable connection timeout time
        client = SSHClient()
        client.load_system_host_keys()
        client.set_missing_host_key_policy(WarningPolicy())
        return client.connect(ip, key_filename='/tmp/%s.pem' % key_name)

    def can_ping(self, ip):
        return getstatusoutput('ping -c 1 %s' % ip)[0] == 0

    def connection_for(self, username):
        return admin.connection_for(username)

    def create_user(self, username):
        return admin.create_user(username)

    def delete_user(self, username):
        return admin.delete_user(username)

    def get_signed_zip(self, username):
        return admin.get_zip(username)

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
