#!/usr/bin/env python
import logging

try:
    import ldap
except Exception, e:
    import fakeldap as ldap

import fakeldap

import os
import sys
import signer
import uuid

import flags

FLAGS = flags.FLAGS

flags.DEFINE_bool('fake_users', False, 'use fake users')
flags.DEFINE_string('ldap_url', 'ldap://localhost', 'Point this at your ldap server') 
flags.DEFINE_string('ldap_password',  'changeme', 'LDAP password')
flags.DEFINE_string('user_dn', 'cn=Manager,dc=example,dc=com', 'DN of admin user')
flags.DEFINE_string('user_unit', 'Users', 'OID for Users')
flags.DEFINE_string('ldap_subtree', 'ou=Users,dc=example,dc=com', 'OU for Users')


from M2Crypto import RSA, BIO

def _generate_key_pair(bits=1024):
    key = RSA.gen_key(bits, 65537)
    bio = BIO.MemoryBuffer()
    key.save_pub_key_bio(bio)
    return (key.as_pem(cipher=None), bio.read())

class LdapUserException(Exception):
    def __init__(self, message):
        self.message = message

    def __str__(self):
        return self.message

class User:
    def __init__(self, manager, ldap_user_object):
        self.manager = manager
        self.ldap_user_object = ldap_user_object

    @property
    def id(self):
        return self.ldap_user_object['uid'][0]

    @property
    def access(self):
        return self.ldap_user_object['accessKey'][0]

    @property
    def secret(self):
        return self.ldap_user_object['secretKey'][0]
    
    def create_key_pair(self, name):
        return self.manager.create_key_pair(self.id, name)

    def create_public_key(self, name, public_key):
        return self.manager.create_public_key(self.id, name, public_key)

    def get_public_key(self, name):
        return self.manager.get_public_key(self.id, name)

    def delete_public_key(self, name):
        return self.manager.delete_public_key(self.id, name)

class UserManager:
    def __init__(self):
        if FLAGS.fake_users:
            self.create_user('fake', 'fake', 'fake')

    def authenticate(self, params, signature, verb='GET', server_string='127.0.0.1:8773', path='/'):
        # TODO: Check for valid timestamp
        access_key = params['AWSAccessKeyId']
        user = self.get_user_from_access_key(access_key)
        if user == None:
            return None
        expected_signature = signer.Signer(user.secret).generate(params, verb, server_string, path)
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

    def create_user(self, uid, access=None, secret=None):
        if access == None: access = str(uuid.uuid4())
        if secret == None: secret = str(uuid.uuid4())
        with LDAPWrapper() as conn:
            conn.create_user(uid, access, secret)

    def delete_user(self, uid):
        with LDAPWrapper() as conn:
            conn.delete_user(uid)

    def create_key_pair(self, uid, key_name):
        private_key, public_key = _generate_key_pair()
        self.create_public_key(uid, key_name, public_key)
        return private_key
        

    def create_public_key(self, uid, key_name, public_key):
        with LDAPWrapper() as conn:
            conn.create_public_key(uid, key_name, public_key)

    def get_public_key(self, uid, key_name):
        with LDAPWrapper() as conn:
            return conn.get_public_key(uid, key_name)
    
    def delete_public_key(self, uid, key_name):
        with LDAPWrapper() as conn:
            conn.delete_public_key(uid, key_name)

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

    def find_object(self, dn, filter = None):
        objects = self.find_objects(dn, filter)
        if objects == None:
            return None
        return objects[0][1] # return attribute list
    
    def find_objects(self, dn, filter = None):
        try:
            res = self.conn.search_s(dn, ldap.SCOPE_SUBTREE, filter)
        except Exception:
            return None
        return res

    def find_user(self, name):
        dn = 'uid=%s,%s' % (name, FLAGS.ldap_subtree)
        return self.find_object(dn, '(objectclass=inetOrgPerson)')

    def user_exists(self, name):
        return self.find_user(name) != None
        
    def find_public_key(self, uid, key_name):
        dn = 'cn=%s,uid=%s,%s' % (key_name,
                                   uid,
                                   FLAGS.ldap_subtree)
        return self.find_object(dn, '(objectclass=pinetPublicKey)')

    def delete_public_keys(self, uid):
        dn = 'uid=%s,%s' % (uid, FLAGS.ldap_subtree)
        key_objects = self.find_objects(dn, '(objectclass=pinetPublicKey)')
        if key_objects != None:
            for key_object in key_objects:
                key_name = key_object[1]['cn'][0]
                self.delete_public_key(uid, key_name)

    def public_key_exists(self, uid, key_name):
        return self.find_public_key(uid, key_name) != None
        
    def create_user(self, name, access_key, secret_key):
        if self.user_exists(name):
            raise LdapUserException("LDAP user " + name + " already exists")
        attr = [
            ('objectclass', ['person',
                             'organizationalPerson',
                             'inetOrgPerson',
                             'pinetKeys']),
            ('ou', FLAGS.user_unit),
            ('uid', name),
            ('sn', name),
            ('cn', name),
            ('secretKey', secret_key),
            ('accessKey', access_key),
        ]
        self.conn.add_s('uid=%s,%s' % (name, FLAGS.ldap_subtree),
                        attr)

    def create_public_key(self, uid, key_name, public_key):
        """create's a public key in the directory underneath the user"""
        # TODO(vish): possibly refactor this to store keys in their own ou
        #   and put dn reference in the user object
        if not self.user_exists(uid):
            raise LdapUserException("User " + uid + " doesn't exist")
        if self.public_key_exists(uid, key_name):
            raise LdapUserException("Public Key " +
                                    key_name +
                                    " already exists for user " +
                                    uid)
        attr = [
            ('objectclass', ['pinetPublicKey']),
            ('cn', key_name),
            ('sshPublicKey', public_key),
        ]
        self.conn.add_s('cn=%s,uid=%s,%s' % (key_name,
                                             uid,
                                             FLAGS.ldap_subtree),
                                             attr)
    
    def find_user_by_access_key(self, access):
        try:
            dn = FLAGS.ldap_subtree
            query = '(' + 'accessKey' + '=' + access + ')'
            res = self.conn.search_s(dn, ldap.SCOPE_SUBTREE, query)
        except Exception, ex:
            return None
        if not res:
            return None
        return res[0][1] # return attribute list

    def get_public_key(self, uid, key_name):
        if not self.public_key_exists(uid, key_name):
            raise LdapUserException("Public Key " +
                                    key_name +
                                    " doesn't exist for user " +
                                    uid)

        attr = self.find_public_key(uid, key_name)
        return (attr['sshPublicKey'][0])

    def get_user_keys(self, name):
        if not self.user_exists(name):
            raise LdapUserException("User " + name + " doesn't exist")

        attr = self.find_user(name)
        return (attr['accessKey'][0],
                attr['secretKey'][0])

    def delete_public_key(self, uid, key_name):
        if not self.public_key_exists(uid, key_name):
            raise LdapUserException("Public Key " +
                                    key_name +
                                    " doesn't exist for user " +
                                    uid)
        self.conn.delete_s('cn=%s,uid=%s,%s' % (key_name, uid,
                                          FLAGS.ldap_subtree))
        

    def delete_user(self, name):
        if not self.user_exists(name):
            raise LdapUserException("User " +
                                    name +
                                    " doesn't exist")
        self.delete_public_keys(name)
        self.conn.delete_s('uid=%s,%s' % (name,
                                          FLAGS.ldap_subtree))

def usage():
    print 'usage: %s -c username (access_key) (secret_key) | -d username' % sys.argv[0]

if __name__ == "__main__":
    manager = UserManager()
    
    if len(sys.argv) > 2:
        if sys.argv[1] == '-c':
            access, secret = None, None
            if len(sys.argv) > 3:
                access = sys.argv[3]
            if len(sys.argv) > 4:
                secret = sys.argv[4] 
            manager.create(sys.argv[2], access, secret)
            print manager.keys(sys.argv[2])
        elif sys.argv[1] == '-d':
            manager.delete(sys.argv[2])
        elif sys.argv[1] == '-k':
            print manager.keys(sys.argv[2])
        else:
            usage()
            sys.exit(2)
        sys.exit(0)
    else:
        usage()
        sys.exit(2)

