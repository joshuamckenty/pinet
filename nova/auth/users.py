#!/usr/bin/env python
import logging

try:
    import ldap
except Exception, e:
    import fakeldap as ldap

import fakeldap
from nova import datastore

# TODO(termie): clean up these imports
import os
import sys
import signer
import uuid
from nova import exception
import flags
from nova import crypto
from nova import utils
import datetime
import tempfile
import zipfile
import shutil

FLAGS = flags.FLAGS

flags.DEFINE_string('ldap_url', 'ldap://localhost', 'Point this at your ldap server') 
flags.DEFINE_string('ldap_password',  'changeme', 'LDAP password')
flags.DEFINE_string('user_dn', 'cn=Manager,dc=example,dc=com', 'DN of admin user')
flags.DEFINE_string('user_unit', 'Users', 'OID for Users')
flags.DEFINE_string('ldap_subtree', 'ou=Users,dc=example,dc=com', 'OU for Users')


flags.DEFINE_string('credentials_template',
                    utils.abspath('auth/novarc.template'),
                    'Template for creating users rc file')
flags.DEFINE_string('credential_key_file', 'pk.pem',
                    'Filename of private key in credentials zip')
flags.DEFINE_string('credential_cert_file', 'cert.pem',
                    'Filename of certificate in credentials zip')
flags.DEFINE_string('credential_rc_file', 'novarc',
                    'Filename of rc in credentials zip')

_log = logging.getLogger('auth')
_log.setLevel(logging.WARN)

KEEPER = datastore.keeper(prefix="user")


class UserError(exception.ApiError):
    pass

class InvalidKeyPair(exception.ApiError):
    pass

class User(object):
    def __init__(self, manager, ldap_user_object):
        self.manager = manager
        self.ldap_user_object = ldap_user_object

    @property
    def id(self):
        return self.ldap_user_object[1]['uid'][0]

    @property
    def name(self):
        return self.ldap_user_object[1]['uid'][0]

    @property
    def access(self):
        return self.ldap_user_object[1]['accessKey'][0]

    @property
    def secret(self):
        return self.ldap_user_object[1]['secretKey'][0]

    @property
    def vpn_port(self):
        port_map = KEEPER['vpn_ports']
        if not port_map: port_map = {}
        if not port_map.has_key(self.id):
            ports = port_map.values()
            if len(ports) > 0:
                port_map[self.id] = max(ports) + 1
            else:
                port_map[self.id] = 8000
        KEEPER['vpn_ports'] = port_map
        return KEEPER['vpn_ports'][self.id]

    @property
    def vpn_ip(self):
        return "198.10.124.2"

    def is_admin(self):
        return self.ldap_user_object[1]['isAdmin'][0] == 'TRUE'

    def is_authorized(self, owner_id, action=None):
        return self.is_admin() or owner_id == self.id
         
    def get_credentials(self):
        rc = self.generate_rc()
        private_key, signed_cert = self.generate_x509_cert()
        tmpdir = tempfile.mkdtemp()
        zf = os.path.join(tmpdir, "temp.zip")
        zippy = zipfile.ZipFile(zf, 'w')
        zippy.writestr(FLAGS.credential_rc_file, rc)
        zippy.writestr(FLAGS.credential_key_file, private_key)
        zippy.writestr(FLAGS.credential_cert_file, signed_cert)
        ca_file = os.path.join(FLAGS.ca_path, FLAGS.ca_file) 
        zippy.write(ca_file, FLAGS.ca_file)
        zippy.close()
        with open(zf, 'rb') as f:
            buffer = f.read()
         
        shutil.rmtree(tmpdir)
        return buffer


    def generate_rc(self):
        rc = open(FLAGS.credentials_template).read()
        rc = rc % { 'access': self.access,
                    'secret': self.secret,
                    'ec2': FLAGS.ec2_url,
                    's3': FLAGS.s3_url,
                    'nova': FLAGS.ca_file,
                    'cert': FLAGS.credential_cert_file,
                    'key': FLAGS.credential_key_file,
            }
        return rc

    def generate_key_pair(self, name):
        return self.manager.generate_key_pair(self.id, name)

    def generate_x509_cert(self):
        return self.manager.generate_x509_cert(self.id)

    def create_key_pair(self, name, public_key, fingerprint):
        return self.manager.create_key_pair(self.id,
                                            name,
                                            public_key,
                                            fingerprint)

    def get_key_pair(self, name):
        return self.manager.get_key_pair(self.id, name)

    def delete_key_pair(self, name):
        return self.manager.delete_key_pair(self.id, name)

    def get_key_pairs(self):
        return self.manager.get_key_pairs(self.id)
        
class KeyPair(object):
    def __init__(self, ldap_key_object):
        self.ldap_key_object = ldap_key_object

    @property
    def name(self):
        return self.ldap_key_object[1]['cn'][0]

    @property
    def public_key(self):
        return self.ldap_key_object[1]['sshPublicKey'][0]

    @property
    def fingerprint(self):
        return self.ldap_key_object[1]['keyFingerprint'][0]

class UserManager(object):
    def __init__(self):
        if FLAGS.fake_users:
            try:
                self.create_user('fake', 'fake', 'fake')
                self.create_user('user', 'user', 'user')
                self.create_user('admin', 'admin', 'admin', True)
            except:
                pass

    def authenticate(self, params, signature, verb='GET', server_string='127.0.0.1:8773', path='/'):
        # TODO: Check for valid timestamp
        access_key = params['AWSAccessKeyId']
        user = self.get_user_from_access_key(access_key)
        if user == None:
            return None
        expected_signature = signer.Signer(user.secret).generate(params, verb, server_string, path)
        _log.debug('user.secret: %s', user.secret)
        _log.debug('expected_signature: %s', expected_signature)
        _log.debug('signature: %s', signature)
        if signature == expected_signature:
            return user
        
    def get_user(self, name):
        with LDAPWrapper() as conn:
            ldap_user_object = conn.find_user(name)
        if ldap_user_object == None:
            return None
        return User(self, ldap_user_object)
    
    def get_user_from_access_key(self, access_key):
        with LDAPWrapper() as conn:
            ldap_user_object = conn.find_user_by_access_key(access_key)
        if ldap_user_object == None:
            return None
        return User(self, ldap_user_object)

    def get_users(self):
        with LDAPWrapper() as conn:
            ldap_user_objects = conn.find_users()
        if ldap_user_objects == None or ldap_user_objects == []:
            return None
        return [User(self, o) for o in ldap_user_objects]
    
    def create_user(self, uid, access=None, secret=None, admin=False):
        if access == None: access = str(uuid.uuid4())
        if secret == None: secret = str(uuid.uuid4())
        with LDAPWrapper() as conn:
            conn.create_user(uid, access, secret, admin)

    def delete_user(self, uid):
        with LDAPWrapper() as conn:
            conn.delete_user(uid)

    def generate_key_pair(self, uid, key_name):
        # generating key pair is slow so delay generation
        # until after check
        with LDAPWrapper() as conn:
            if not conn.user_exists(uid):
                raise UserError("User " + uid + " doesn't exist")
            if conn.key_pair_exists(uid, key_name):
                raise InvalidKeyPair("The keypair '" +
                            key_name +
                            "' already exists.",
                            "Duplicate")
        private_key, public_key = crypto.generate_keypair()
        #TODO(vish): calculate real fingerprint frome private key
        fingerprint = 'fixme'
        self.create_key_pair(uid, key_name, public_key, fingerprint)
        return private_key, fingerprint

    def create_key_pair(self, uid, key_name, public_key, fingerprint):
        with LDAPWrapper() as conn:
            conn.create_key_pair(uid, key_name, public_key, fingerprint)
    
    def get_key_pair(self, uid, key_name):
        with LDAPWrapper() as conn:
            ldap_key_object = conn.find_key_pair(uid, key_name)
        if ldap_key_object == None:
            return None
        return KeyPair(ldap_key_object)

    def get_key_pairs(self, uid):
        with LDAPWrapper() as conn:
            ldap_key_objects = conn.find_key_pairs(uid)
        if ldap_key_objects == None or ldap_key_objects == []:
            return []
        return [KeyPair(o) for o in ldap_key_objects]
    
    def delete_key_pair(self, uid, key_name):
        with LDAPWrapper() as conn:
            conn.delete_key_pair(uid, key_name)

    def generate_x509_cert(self, uid):
        (private_key, csr) = crypto.generate_x509_cert(self.cert_subject(uid))
        # TODO - This should be async call back to the cloud controller
        signed_cert = crypto.sign_csr(csr)
        _log.debug(signed_cert)
        return (private_key, signed_cert)

    def cert_subject(self, uid):
        return "/C=US/ST=California/L=NASA_Ames/O=NebulaDev/OU=NOVA/CN=%s-%s" % (uid, str(datetime.datetime.utcnow().isoformat()))

class LDAPWrapper(object):
    def __init__(self):
        self.user = FLAGS.user_dn
        self.passwd = FLAGS.ldap_password
        pass
    
    def __enter__(self):
        self.connect()
        return self
    
    def __exit__(self, type, value, traceback):
        self.conn.unbind_s()

    def connect(self):
        """ connect to ldap as admin user """
        if FLAGS.fake_users:
            self.conn = fakeldap.initialize(FLAGS.ldap_url)
        else:
            assert(ldap.__name__ != 'fakeldap')
            self.conn = ldap.initialize(FLAGS.ldap_url)
        self.conn.simple_bind_s(self.user, self.passwd)

    def find_object(self, dn, query = None):
        objects = self.find_objects(dn, query)
        if len(objects) == 0:
            return None
        return objects[0]
    
    def find_objects(self, dn, query = None):
        try:
            res = self.conn.search_s(dn, ldap.SCOPE_SUBTREE, query)
        except Exception:
            return []
        return res

    def find_users(self):
        return self.find_objects(FLAGS.ldap_subtree, '(objectclass=novaUser)')

    def find_key_pairs(self, uid):
        dn = 'uid=%s,%s' % (uid, FLAGS.ldap_subtree)
        return self.find_objects(dn, '(objectclass=novaKeyPair)')

    def find_user(self, name):
        dn = 'uid=%s,%s' % (name, FLAGS.ldap_subtree)
        return self.find_object(dn, '(objectclass=novaUser)')

    def user_exists(self, name):
        return self.find_user(name) != None
        
    def find_key_pair(self, uid, key_name):
        dn = 'cn=%s,uid=%s,%s' % (key_name,
                                   uid,
                                   FLAGS.ldap_subtree)
        return self.find_object(dn, '(objectclass=novaKeyPair)')

    def delete_key_pairs(self, uid):
        key_objects = self.find_key_pairs(uid)
        if key_objects != None:
            for key_object in key_objects:
                key_name = key_object[1]['cn'][0]
                self.delete_key_pair(uid, key_name)

    def key_pair_exists(self, uid, key_name):
        return self.find_key_pair(uid, key_name) != None
        
    def create_user(self, name, access_key, secret_key, is_admin):
        if self.user_exists(name):
            raise UserError("LDAP user " + name + " already exists")
        attr = [
            ('objectclass', ['person',
                             'organizationalPerson',
                             'inetOrgPerson',
                             'novaUser']),
            ('ou', FLAGS.user_unit),
            ('uid', name),
            ('sn', name),
            ('cn', name),
            ('secretKey', secret_key),
            ('accessKey', access_key),
            ('isAdmin', str(is_admin).upper()),
        ]
        self.conn.add_s('uid=%s,%s' % (name, FLAGS.ldap_subtree),
                        attr)

    def create_key_pair(self, uid, key_name, public_key, fingerprint):
        """create's a public key in the directory underneath the user"""
        # TODO(vish): possibly refactor this to store keys in their own ou
        #   and put dn reference in the user object
        attr = [
            ('objectclass', ['novaKeyPair']),
            ('cn', key_name),
            ('sshPublicKey', public_key),
            ('keyFingerprint', fingerprint),
        ]
        self.conn.add_s('cn=%s,uid=%s,%s' % (key_name,
                                             uid,
                                             FLAGS.ldap_subtree),
                                             attr)
    
    def find_user_by_access_key(self, access):
        query = '(' + 'accessKey' + '=' + access + ')'
        dn = FLAGS.ldap_subtree
        return self.find_object(dn, query)

    def delete_key_pair(self, uid, key_name):
        if not self.key_pair_exists(uid, key_name):
            raise UserError("Key Pair " +
                                    key_name +
                                    " doesn't exist for user " +
                                    uid)
        self.conn.delete_s('cn=%s,uid=%s,%s' % (key_name, uid,
                                          FLAGS.ldap_subtree))
        

    def delete_user(self, name):
        if not self.user_exists(name):
            raise UserError("User " +
                                    name +
                                    " doesn't exist")
        self.delete_key_pairs(name)
        self.conn.delete_s('uid=%s,%s' % (name,
                                          FLAGS.ldap_subtree))
