# COPYRIGHT NASA

import os, re, sys, time, unittest, random
from novatestcase import NovaTestCase
from commands import getstatusoutput
from paramiko import SSHException
from zipfile import ZipFile, ZIP_DEFLATED

# TODO: Make endpoint configurable

DEBUG = True

KERNEL_FILENAME = 'openwrt-x86-vmlinuz'
IMAGE_FILENAME = 'openwrt-x86-ext2.image'

ZIP_FILENAME = '/tmp/euca-me-x509.zip'

data = {}

test_prefix = 'test%s' % int(random.random()*1000000)
test_username = '%suser' % test_prefix

# Test admin credentials and user creation
class UserTests(NovaTestCase):
    def test_001_admin_can_connect(self):
        conn = self.connection_for('admin')
        self.assert_(conn)

    def test_002_admin_can_create_user(self):
        userinfo = self.create_user(test_username)
        self.assertEqual(userinfo.username, test_username)

    def test_003_user_can_download_credentials(self):
        buf = self.get_signed_zip(test_username)
        output = open(ZIP_FILENAME, 'w')
        output.write(buf)
        output.close()

        zip = ZipFile(ZIP_FILENAME, 'a', ZIP_DEFLATED)
        bad = zip.testzip()
        zip.close()

        self.failIf(bad)

    def test_999_tearDown(self):
        self.delete_user(test_username)
        user = self.get_user(test_username)
        self.assert_(user is None)
        try:
            os.remove(ZIP_FILENAME)
        except:
            pass

# Test image bundling, registration, and launching
class ImageTests(NovaTestCase):
    def test_000_setUp(self):
        self.create_user(test_username)

    def test_001_admin_can_bundle_kernel(self):
        self.assertTrue(self.bundle_image(KERNEL_FILENAME, kernel=True))

    def test_002_admin_can_upload_kernel(self):
        self.assertTrue(self.upload_image(KERNEL_FILENAME))

    def test_003_admin_can_register_kernel(self):
        id = self.register_image(KERNEL_FILENAME)
        self.assert_(id)
        data['kernel_id'] = id

    def test_004_admin_can_bundle_image(self):
        self.assertTrue(self.bundle_image(IMAGE_FILENAME))

    def test_005_admin_can_upload_image(self):
        self.assertTrue(self.upload_image(IMAGE_FILENAME))

    def test_006_admin_can_register_image(self):
        id = self.register_image(IMAGE_FILENAME)
        self.assert_(id)
        data['image_id'] = id

    def test_007_me_sees_admin_public_kernel(self):
        conn = self.connection_for(test_username)
        image = conn.get_image(data['kernel_id'])
        self.assertEqual(image.id, data['kernel_id'])

    def test_008_me_sees_admin_public_image(self):
        conn = self.connection_for(test_username)
        image = conn.get_image(data['image_id'])
        self.assertEqual(image.id, data['image_id'])

    def test_009_me_can_launch_admin_public_image(self):
        # TODO: Use openwrt kernel instead of default kernel
        conn = self.connection_for(test_username)
        reservation = conn.run_instances(data['image_id'])
        self.assertEqual(len(reservation.instances), 1)
        data['my_instance_id'] = reservation.instances[0].id

    def test_010_me_can_terminate(self):
        conn = self.connection_for(test_username)
        terminated = conn.terminate_instances(instance_ids=[data['my_instance_id']])
        self.assertEqual(len(terminated), 1)

    def test_011_admin_can_deregister_kernel(self):
        conn = self.connection_for('admin')
        self.assertTrue(conn.deregister_image(data['kernel_id']))

    def test_012_admin_can_deregister_image(self):
        conn = self.connection_for('admin')
        self.assertTrue(conn.deregister_image(data['image_id']))

#    def test_010_admin_can_delete_image(self):
#        self.assert_(False)

#    def test_011_admin_can_delete_bucket(self):
#        self.assert_(False)

    def test_999_tearDown(self):
        data = {}
        self.delete_user(test_username)

# Test key pairs and security groups
class SecurityTests(NovaTestCase):
    def test_000_setUp(self):
        self.create_user('me')
        self.create_user('you')
        data['kernel_id'] = self.setUp_test_image(KERNEL_FILENAME, kernel=True)
        data['image_id'] = self.setUp_test_image(IMAGE_FILENAME)

    def test_001_me_can_create_keypair(self):
        conn = self.connection_for('me')
        key = self.create_key_pair(conn, 'mykey')
        self.assertEqual(key.name, 'mykey')

    def test_002_you_can_create_keypair(self):
        conn = self.connection_for('you')
        key = self.create_key_pair(conn, 'yourkey')
        self.assertEqual(key.name, 'yourkey')

    def test_003_me_can_create_instance_with_keypair(self):
        conn = self.connection_for('me')
        reservation = conn.run_instances(data['image_id'], kernel_id=data['kernel_id'], key_name='mykey')
        self.assertEqual(len(reservation.instances), 1)
        data['my_instance_id'] = reservation.instances[0].id

    def test_004_me_can_obtain_private_ip(self):
        time.sleep(3) # allow time for ip to be assigned
        conn = self.connection_for('me')
        reservations = conn.get_all_instances([data['my_instance_id']])
        ip = reservations[0].instances[0].private_dns_name
        self.failIf(ip == '0.0.0.0')
        data['my_private_ip'] = ip
        print data['my_private_ip']

    def test_005_me_cannot_ssh_when_unauthorized(self):
        self.assertRaises(SSHException, self.connect_ssh, data['my_private_ip'], 'mykey')

    def test_006_me_can_authorize_ssh(self):
        conn = self.connection_for('me')
        self.assertTrue(
            conn.authorize_security_group(
                'default',
                ip_protocol='tcp',
                from_port=22,
                to_port=22,
                cidr_ip='0.0.0.0/0'
            )
        )

    def test_007_me_can_ssh_when_authorized(self):
        conn = self.connect_ssh(data['my_private_ip'], 'mykey')
        conn.close()

    def test_008_me_can_revoke_ssh_authorization(self):
        conn = self.connection_for('me')
        self.assertTrue(
            conn.revoke_security_group(
                'default',
                ip_protocol='tcp',
                from_port=22,
                to_port=22,
                cidr_ip='0.0.0.0/0'
            )
        )

    def test_009_you_cannot_ping_my_instance(self):
        # TODO: should ping my_private_ip from with an instance started by "you"
        self.assertFalse(self.can_ping(data['my_private_ip']))

    def test_010_you_cannot_ssh_to_my_instance(self):
        try:
            conn = self.connect_ssh(data['my_private_ip'], 'yourkey')
            conn.close()
        except SSHException:
            pass
        else:
            fail("expected SSHException")

    def test_999_tearDown(self):
        conn = self.connection_for('me')
        self.delete_key_pair(conn, 'mykey')
        if data.has_key('my_instance_id'):
            conn.terminate_instances([data['my_instance_id']])

        conn = self.connection_for('you')
        self.delete_key_pair(conn, 'yourkey')

        conn = self.connection_for('admin')
        self.delete_user('me')
        self.delete_user('you')
        self.tearDown_test_image(conn, data['image_id'])
        self.tearDown_test_image(conn, data['kernel_id'])

# TODO: verify wrt image boots
#       build python into wrt image
#       build boto/m2crypto into wrt image
#       build euca2ools into wrt image
#       build a script to download and unpack credentials
#         - return "ok" to stdout for comparison in self.assertEqual()
#       build a script to bundle the instance
#       build a script to upload the bundle

# status, output = getstatusoutput('cmd')
# if status == 0:
#    print 'ok'
# else:
#    print output

# Testing rebundling
class RebundlingTests(NovaTestCase):
    def test_000_setUp(self):
        self.create_user('me')
        self.create_user('you')
        # TODO: create keypair for me
        #       upload smoketest img
        #       run instance

    def test_001_me_can_download_credentials_within_instance(self):
        conn = self.connect_ssh(data['my_private_ip'], 'mykey')
        stdin, stdout = conn.exec_command('python ~/smoketests/install-credentials.py')
        conn.close()
        self.assertEqual(stdout, 'ok')

    def test_002_me_can_rebundle_within_instance(self):
        conn = self.connect_ssh(data['my_private_ip'], 'mykey')
        stdin, stdout = conn.exec_command('python ~/smoketests/rebundle-instance.py')
        conn.close()
        self.assertEqual(stdout, 'ok')

    def test_003_me_can_upload_image_within_instance(self):
        conn = self.connect_ssh(data['my_private_ip'], 'mykey')
        stdin, stdout = conn.exec_command('python ~/smoketests/upload-bundle.py')
        conn.close()
        self.assertEqual(stdout, 'ok')

    def test_004_me_can_register_image_within_instance(self):
        conn = self.connect_ssh(data['my_private_ip'], 'mykey')
        stdin, stdout = conn.exec_command('python ~/smoketests/register-image.py')
        conn.close()
        if re.matches('emi-{\w+}', stdout):
            data['my_image_id'] = stdout.strip()
        else:
            self.fail('expected emi-nnnnnn, got:\n ' + stdout)

    def test_005_you_cannot_see_my_private_image(self):
        conn = self.connection_for('you')
        image = conn.get_image(data['my_image_id'])
        self.assertEqual(image, None)

#    def test_006_me_can_make_image_public(self):
#        # TODO: research this
#        self.assert_(False)
#
    def test_007_you_can_see_my_public_image(self):
        conn = self.connection_for('you')
        image = conn.get_image(data['my_image_id'])
        self.assertEqual(image.id, data['my_image_id'])

    def test_999_tearDown(self):
        self.delete_user('me')
        self.delete_user('you')

        #if data.has_key('image_id'):
            # deregister rebundled image

            # TODO: tear down instance
            #       delete keypairs
        data = {}

# Test elastic IPs
class ElasticIPTests(NovaTestCase):
    def test_000_setUp(self):
        self.create_user('me')
        conn = self.connection_for('me')
        self.create_key_pair(conn, 'mykey')

        conn = self.connection_for('admin')
        data['kernel_id'] = self.setUp_test_image(KERNEL_FILENAME, kernel=True)
        data['image_id'] = self.setUp_test_image(IMAGE_FILENAME)

    def test_001_me_can_launch_image_with_keypair(self):
        conn = self.connection_for('me')
        reservation = conn.run_instances(data['image_id'], key_name='mykey')
        self.assertEqual(len(reservation.instances), 1)
        data['my_instance_id'] = reservation.instances[0].id

    def test_002_me_can_allocate_elastic_ip(self):
        conn = self.connection_for('me')
        data['my_public_ip'] = conn.allocate_address()
        self.assert_(data['my_public_ip'].public_ip)

    def test_003_me_can_associate_ip_with_instance(self):
        self.assertTrue(data['my_public_ip'].associate(instance_id))

    def test_004_me_can_ssh_with_public_ip(self):
        conn = self.connect_ssh(data['my_public_ip'].public_ip, 'mykey')
        conn.close()

    def test_005_me_can_disassociate_ip_from_instance(self):
        self.assertTrue(data['my_public_ip'].disassociate())

    def test_006_me_can_deallocate_elastic_ip(self):
        self.assertTrue(data['my_public_ip'].delete())

    def test_999_tearDown(self):
        conn = self.connection_for('me')
        self.delete_key_pair(conn, 'mykey')

        conn = self.connection_for('admin')
        self.tearDown_test_image(conn, data['image_id'])
        self.tearDown_test_image(conn, data['kernel_id'])
        data = {}

# Test iscsi volumes
class VolumeTests(NovaTestCase):
    def test_000_setUp(self):
        self.create_user('me')
        data['kernel_id'] = self.setUp_test_image(KERNEL_FILENAME, kernel=True)
        data['image_id'] = self.setUp_test_image(IMAGE_FILENAME)

        conn = self.connection_for('me')
        self.create_key_pair(conn, 'mykey')
        reservation = conn.run_instances(data['image_id'], key_name='mykey')
        data['my_instance_id'] = reservation.instances[0].id
        data['my_private_ip'] = reservation.instances[0].private_dns_name

    def test_001_me_can_create_volume(self):
        conn = self.connection_for('me')
        volume = conn.create_volume(1, ZONE)
        self.assertEqual(volume.size, 1)
        data['volume_id'] = volume.id


    def test_002_me_can_attach_volume(self):
        conn = self.connection_for('me')
        self.assert_(
            conn.attach_volume(
                volume_id = data['volume_id'],
                instance_id = data['my_instance_id'],
                device = '/dev/sdc'
            )
        )

    def test_003_me_can_mount_volume(self):
        conn = self.connect_ssh(data['my_private_ip'], 'mykey')
        stdin, stdout, stderr = conn.exec_command('mkdir -p /mnt/vol; mount /dev/sdc /mnt/vol')
        conn.close()
        if len(stderr > 0) or len(stderr > 0):
            self.fail('Unable to mount:', stdout, stderr)
        print stdout, stderr

    def test_004_me_can_write_to_volume(self):
        conn = self.connect_ssh(data['my_private_ip'], 'mykey')
        stdin, stdout, stderr = conn.exec_command('echo "hello" >> /mnt/vol/test.txt')
        conn.close()
        if len(stderr > 0) or len(stderr > 0):
            self.fail('Unable to write to mount:', stdout, stderr)
        print stdout, stderr

    def test_005_me_can_umount_volume(self):
        conn = self.connect_ssh(data['my_private_ip'], 'mykey')
        stdin, stdout, stderr = conn.exec_command('umount /mnt/vol')
        conn.close()
        if len(stderr > 0) or len(stderr > 0):
            self.fail('Unable to mount:', stdout, stderr)
        print stdout, stderr

    def test_006_me_can_detach_volume(self):
        conn = self.connection_for('me')
        self.assert_(conn.detach_volume(volume_id = data['volume_id']))

    def test_00_me_can_delete_volume(self):
        conn = self.connection_for('me')
        self.assertTrue(conn.delete_volume(data['volume_id']))

    def test_999_tearDown(self):
        conn = self.connection_for('me')
        self.delete_key_pair(conn, 'mykey')
        self.delete_user('me')
        conn = self.connection_for('admin')
        self.tearDown_test_image(conn, data['image_id'])
        self.tearDown_test_image(conn, data['kernel_id'])
        data = dict()

def build_suites():
    return {
        'user': unittest.makeSuite(UserTests),
        'image': unittest.makeSuite(ImageTests),
        'security': unittest.makeSuite(SecurityTests),
        'public_network': unittest.makeSuite(ElasticIPTests),
        'volume': unittest.makeSuite(VolumeTests),
    }

def main(argv=None):
    if len(argv) == 1:
        unittest.main()
    else:
        suites = build_suites()

        try:
            suite = suites[argv[1]]
        except KeyError:
            print >> sys.stderr, 'Available test suites: [user, image, security, public_network, volume]'
            return

        unittest.TextTestRunner(verbosity=2).run(suite)

if __name__ == "__main__":
    sys.exit(main(sys.argv))
