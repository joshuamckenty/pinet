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
test_bucket = '%s_bucket' % test_prefix
test_key = '%s_key' % test_prefix

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

    def test_001_admin_can_bundle_image(self):
        self.assertTrue(self.bundle_image(IMAGE_FILENAME))

    def test_002_admin_can_upload_image(self):
        self.assertTrue(self.upload_image(test_bucket, IMAGE_FILENAME))

    def test_003_admin_can_register_image(self):
        image_id = self.register_image(test_bucket, IMAGE_FILENAME)
        self.assert_(image_id is not None)
        data['image_id'] = image_id

    def test_004_admin_can_bundle_kernel(self):
        self.assertTrue(self.bundle_image(KERNEL_FILENAME, kernel=True))

    def test_005_admin_can_upload_kernel(self):
        self.assertTrue(self.upload_image(test_bucket, KERNEL_FILENAME))

    def test_006_admin_can_register_kernel(self):
        # FIXME: registeration should verify that bucket/manifest exists before returning successfully!
        kernel_id = self.register_image(test_bucket, KERNEL_FILENAME)
        self.assert_(kernel_id is not None)
        data['kernel_id'] = kernel_id

    def test_007_admin_images_are_available_within_10_seconds(self):
        for i in xrange(10):
            image = self.admin.get_image(data['image_id'])
            if image and image.state == 'available':
                break
            time.sleep(1)
        else:
            print image.state
            self.assert_(False) # wasn't available within 10 seconds
        self.assert_(image.type == 'machine')

        for i in xrange(10):
            kernel = self.admin.get_image(data['kernel_id'])
            if kernel and kernel.state == 'available':
                break
            time.sleep(1)
        else:
            self.assert_(False) # wasn't available within 10 seconds
        self.assert_(kernel.type == 'kernel')

    def test_008_images_not_public_by_default(self):
        conn = self.connection_for(test_username)
        images = conn.get_all_images(image_ids=[data['image_id']])
        self.assertEqual(len(images), 0)
        images = conn.get_all_images(image_ids=[data['kernel_id']])
        self.assertEqual(len(images), 0)

    def test_009_images_can_be_made_public(self):
        userconn = self.connection_for(test_username)

        self.admin.modify_image_attribute(image_id=data['image_id'],
                                          operation='add',
                                          attribute='launchPermission',
                                          groups='all')

        image = userconn.get_image(data['image_id'])
        self.assertEqual(image.id, data['image_id'])

        self.admin.modify_image_attribute(image_id=data['kernel_id'],
                                          operation='add',
                                          attribute='launchPermission',
                                          groups='all')

        image = userconn.get_image(data['kernel_id'])
        self.assertEqual(image.id, data['kernel_id'])

    # FIXME: add tests that user can launch image

#     def test_010_user_can_launch_admin_public_image(self):
#         # TODO: Use openwrt kernel instead of default kernel
#         conn = self.connection_for(test_username)
#         reservation = conn.run_instances(data['image_id'])
#         self.assertEqual(len(reservation.instances), 1)
#         data['my_instance_id'] = reservation.instances[0].id

#     def test_011_instances_launch_within_30_seconds(self):
#         pass

#     def test_012_user_can_terminate(self):
#         conn = self.connection_for(test_username)
#         terminated = conn.terminate_instances(instance_ids=[data['my_instance_id']])
#         self.assertEqual(len(terminated), 1)

    def test_013_admin_can_deregister_kernel(self):
        self.assertTrue(self.admin.deregister_image(data['kernel_id']))

    def test_014_admin_can_deregister_image(self):
        self.assertTrue(self.admin.deregister_image(data['image_id']))

    def test_015_admin_can_delete_bundle(self):
        self.assertTrue(self.delete_bundle_bucket(test_bucket))

    def test_999_tearDown(self):
        data = {}
        self.delete_user(test_username)


# Test key pairs and security groups
class SecurityTests(NovaTestCase):
    def test_000_setUp(self):
        self.create_user(test_username + '_me')
        self.create_user(test_username + '_you')
        data['kernel_id'] = 'aki-EAB510D9'
        data['image_id'] = 'ami-25CB1213'

    def test_001_me_can_create_keypair(self):
        conn = self.connection_for(test_username + '_me')
        key = self.create_key_pair(conn, test_key)
        self.assertEqual(key.name, test_key)

    def test_002_you_can_create_keypair(self):
        conn = self.connection_for(test_username + '_you')
        key = self.create_key_pair(conn, test_key+ 'yourkey')
        self.assertEqual(key.name, test_key+'yourkey')

    def test_003_me_can_create_instance_with_keypair(self):
        conn = self.connection_for(test_username + '_me')
        reservation = conn.run_instances(data['image_id'], kernel_id=data['kernel_id'], key_name=test_key)
        self.assertEqual(len(reservation.instances), 1)
        data['my_instance_id'] = reservation.instances[0].id

    def test_004_me_can_obtain_private_ip_within_60_seconds(self):
        conn = self.connection_for(test_username + '_me')
        reservations = conn.get_all_instances([data['my_instance_id']])
        instance = reservations[0].instances[0]
        # allow 60 seconds to exit pending with IP
        for x in xrange(60):
            instance.update()
            if instance.state != u'pending':
                 break
            time.sleep(1)
        else:
            self.assert_(False)
        # self.assertEqual(instance.state, u'running')
        ip = reservations[0].instances[0].private_dns_name
        self.failIf(ip == '0.0.0.0')
        data['my_private_ip'] = ip
        print data['my_private_ip'],

    def test_005_can_ping_private_ip(self):
        # allow 30 seconds for PING to work
        print "ping -c1 -w1 %s" % data['my_private_ip']
        for x in xrange(120):
            # ping waits for 1 second
            status, output = getstatusoutput("ping -c1 -w1 %s" % data['my_private_ip'])
            if status == 0:
                 break
        else:
            self.assert_(False)
    #def test_005_me_cannot_ssh_when_unauthorized(self):
    #    self.assertRaises(SSHException, self.connect_ssh, data['my_private_ip'], 'mykey')

    #def test_006_me_can_authorize_ssh(self):
    #    conn = self.connection_for(test_username + '_me')
    #    self.assertTrue(
    #        conn.authorize_security_group(
    #            'default',
    #            ip_protocol='tcp',
    #            from_port=22,
    #            to_port=22,
    #            cidr_ip='0.0.0.0/0'
    #        )
    #    )

    def test_007_me_can_ssh_when_authorized(self):
        # Wait for the instance to ACTUALLY have ssh ru/nning
        for x in xrange(120):
            try:
                conn = self.connect_ssh(data['my_private_ip'], test_key)
                conn.close()
                break
            except:
                time.sleep(1)
        else:
            self.assertTrue(False)

    #def test_008_me_can_revoke_ssh_authorization(self):
    #    conn = self.connection_for('me')
    #    self.assertTrue(
    #        conn.revoke_security_group(
    #            'default',
    #            ip_protocol='tcp',
    #            from_port=22,
    #            to_port=22,
    #            cidr_ip='0.0.0.0/0'
    #        )
    #    )

    #def test_009_you_cannot_ping_my_instance(self):
        # TODO: should ping my_private_ip from with an instance started by "you"
        #self.assertFalse(self.can_ping(data['my_private_ip']))

    def test_010_you_cannot_ssh_to_my_instance(self):
        try:
            conn = self.connect_ssh(data['my_private_ip'], test_key + 'yourkey')
            conn.close()
        except SSHException:
            pass
        else:
            fail("expected SSHException")

    def test_999_tearDown(self):
        conn = self.connection_for(test_username + '_me')
        self.delete_key_pair(conn, test_key)
        if data.has_key('my_instance_id'):
            conn.terminate_instances([data['my_instance_id']])

        conn = self.connection_for(test_username + '_you')
        self.delete_key_pair(conn, test_key + 'yourkey')

        conn = self.connection_for('admin')
        self.delete_user(test_username + '_me')
        self.delete_user(test_username + '_you')
        #self.tearDown_test_image(conn, data['image_id'])
        #self.tearDown_test_image(conn, data['kernel_id'])

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
        data['kernel_id'] = 'aki-EAB510D9'
        data['image_id'] = 'ami-25CB1213' # A7370FE3
        #data['kernel_id'] = self.setUp_test_image(KERNEL_FILENAME, kernel=True)
        #data['image_id'] = self.setUp_test_image(IMAGE_FILENAME)

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
        #self.tearDown_test_image(conn, data['image_id'])
        #self.tearDown_test_image(conn, data['kernel_id'])
        data = {}

ZONE = 'nova'
DEVICE = '/dev/vdb'
vol_key = test_key + 'volumekey'
# Test iscsi volumes
class VolumeTests(NovaTestCase):
    def test_000_setUp(self):
        self.create_user('me')
        data['kernel_id'] = 'aki-EAB510D9'
        data['image_id'] = 'ami-25CB1213' # A7370FE3

        conn = self.connection_for('me')
        self.create_key_pair(conn, vol_key)
        reservation = conn.run_instances(data['image_id'], key_name=vol_key)
        data['my_instance_id'] = reservation.instances[0].id
        data['my_private_ip'] = reservation.instances[0].private_dns_name

        # wait for instance to show up
        for x in xrange(120):
            # ping waits for 1 second
            status, output = getstatusoutput("ping -c1 -w1 %s" % data['my_private_ip'])
            if status == 0:
                 break
        else:
            self.assertTrue(False)

    def test_001_me_can_create_volume(self):
        conn = self.connection_for('me')
        volume = conn.create_volume(1, ZONE)
        self.assertEqual(volume.size, 1)
        data['volume_id'] = volume.id

    def test_002_me_can_attach_volume(self):
        # Wait for the volume to be reported to cloud

        conn = self.connection_for('me')
        for x in xrange(20):
            try:
                conn.attach_volume(
                    volume_id = data['volume_id'],
                    instance_id = data['my_instance_id'],
                    device = DEVICE
                )
                break
            except:
                time.sleep(1)
        else:
            self.assertTrue(False)

    # fixme: test cannot delete attached volume!

    def test_003_me_can_mount_volume(self):
        # Wait for the instance to ACTUALLY have ssh running
        for x in xrange(5):
            try:
                conn = self.connect_ssh(data['my_private_ip'], vol_key)
                break
            except:
                time.sleep(5)
        else:
            conn.close()
            self.assertTrue(False)
            return
        stdin, stdout, stderr = conn.exec_command('sudo bash -c "mkdir -p /mnt/vol && mkfs.ext3 %s && mount %s /mnt/vol && echo success"' % (DEVICE, DEVICE))
        out = stdout.read()
        conn.close()
        if not out.strip().endswith('success'):
            self.fail('Unable to mount: %s %s' % (out, stderr.read()))

    def test_004_me_can_write_to_volume(self):
        conn = self.connect_ssh(data['my_private_ip'], vol_key)
        # FIXME: This doesn't fail if the volume hasn't been mounted
        stdin, stdout, stderr = conn.exec_command('sudo bash -c "echo hello > /mnt/vol/test.txt"')
        err = stderr.read()
        conn.close()
        if len(err) > 0:
            self.fail('Unable to write to mount: %s' % (err))

    def test_005_me_can_umount_volume(self):
        conn = self.connect_ssh(data['my_private_ip'], vol_key)
        stdin, stdout, stderr = conn.exec_command('sudo umount /mnt/vol')
        err = stderr.read()
        conn.close()
        if len(err) > 0:
            self.fail('Unable to unmount: %s' % (err))

    def test_006_me_can_detach_volume(self):
        conn = self.connection_for('me')
        self.assertTrue(conn.detach_volume(volume_id = data['volume_id']))

    def test_007_me_can_delete_volume(self):
        conn = self.connection_for('me')
        self.assertTrue(conn.delete_volume(data['volume_id']))

    def test_999_tearDown(self):
        global data
        conn = self.connection_for('me')
        self.delete_key_pair(conn, vol_key)
        if data.has_key('my_instance_id'):
            conn.terminate_instances([data['my_instance_id']])
        self.delete_user('me')
        data = {}

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
