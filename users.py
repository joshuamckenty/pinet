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

class UserManager:
    def __init__(self, config={}):
        self.config = {
            'password': 'changeme',
            'user_dn': 'cn=Manager,dc=example,dc=com',
            'user_unit': 'Users',
            'ldap_subtree': 'ou=Users,dc=example,dc=com',
            'ldap_url': 'ldap://localhost',
        }
        self.config.update(config)
        if self.config.has_key('use_fake') and self.config['use_fake']:
            self.create('fake', 'fake', 'fake')

    def authenticate(self, params, signature, verb='GET', server_string='127.0.0.1:8773', path='/'):
        # TODO: Check for valid timestamp
        access_key = params['AWSAccessKeyId']
        with LDAPWrapper(self.config) as conn:
            user = conn.find_user_by_access_key(access_key)
        
        if user == None:
            return None
        secret_key = user['secretKey'][0]
        expected_signature = signer.Signer(secret_key).generate(params, verb, server_string, path)
        if signature == expected_signature:
            return user
        
    def keys(self, name):
        """ return access & secret for a username """
        with LDAPWrapper(self.config) as conn:
            return conn.get_user_keys(name)
    
    def get_secret_from_access(self, access_key):
        """ retreive the secret key for a given access key """
        with LDAPWrapper(self.config) as conn:
            user = conn.find_user_by_access_key(access_key)
            if user:
                return user['secretKey'][0]
            return False

    def create(self, name, access=None, secret=None):
        if access == None: access = str(uuid.uuid4())
        if secret == None: secret = str(uuid.uuid4())
        with LDAPWrapper(self.config) as conn:
            conn.create_user(name, access, secret)

    def delete(self, name):
        with LDAPWrapper(self.config) as conn:
            conn.delete_user(name)

    def create_key_pair(self, access_key, key_name):
        with LDAPWrapper(self.config) as conn:
            user = conn.find_user_by_access_key(access_key)
        
        if user == None:
            return None
        user_name = user['uid'][0]
        private_key, public_key = _generate_key_pair()
        with LDAPWrapper(self.config) as conn:
            conn.create_public_key(user_name, key_name, public_key)
        return private_key

class LDAPWrapper(object):
    def __init__(self, config):
        self.config = config
    
    def __enter__(self):
        self.connect()
        return self
    
    def __exit__(self, type, value, traceback):
        self.conn.unbind_s()

    def connect(self):
        """ connect to ldap as admin user """
        if self.config.has_key('use_fake') and self.config['use_fake']:
            self.conn = fakeldap.initialize(self.config['ldap_url'])
        else:
            assert(ldap.__name__ != 'fakeldap')
            self.conn = ldap.initialize(self.config['ldap_url'])
        self.conn.simple_bind_s(self.config['user_dn'], self.config['password'])

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
        dn = 'uid=%s,%s' % (name, self.config['ldap_subtree'])
        return self.find_object(dn, '(objectclass=inetOrgPerson)')

    def user_exists(self, name):
        return self.find_user(name) != None
        
    def find_public_key(self, user_name, key_name):
        dn = 'cn=%s,uid=%s,%s' % (key_name,
                                   user_name,
                                   self.config['ldap_subtree'])
        return self.find_object(dn, '(objectclass=pinetPublicKey)')

    def delete_public_keys(self, user_name):
        dn = 'uid=%s,%s' % (user_name, self.config['ldap_subtree'])
        key_objects = self.find_objects(dn, '(objectclass=pinetPublicKey)')
        if key_objects != None:
            for key_object in key_objects:
                key_name = key_object[1]['cn'][0]
                self.delete_public_key(user_name, key_name)

    def public_key_exists(self, user_name, key_name):
        return self.find_public_key(user_name, key_name) != None
        
    def create_user(self, name, access_key, secret_key):
        if self.user_exists(name):
            raise LdapUserException("LDAP user " + name + " already exists")
        attr = [
            ('objectclass', ['person',
                             'organizationalPerson',
                             'inetOrgPerson',
                             'pinetKeys']),
            ('ou', self.config['user_unit']),
            ('uid', name),
            ('sn', name),
            ('cn', name),
            ('secretKey', secret_key),
            ('accessKey', access_key),
        ]
        self.conn.add_s('uid=%s,%s' % (name, self.config['ldap_subtree']),
                        attr)

    def create_public_key(self, user_name, key_name, public_key):
        """create's a public key in the directory underneath the user"""
        # TODO(vish): possibly refactor this to store keys in their own ou
        #   and put dn reference in the user object
        if not self.user_exists(user_name):
            raise LdapUserException("User" + user_name + " doesn't exist")
        if self.public_key_exists(user_name, key_name):
            raise LdapUserException("Public Key " +
                                    key_name +
                                    " already exists for user " +
                                    user_name)
        attr = [
            ('objectclass', ['pinetPublicKey']),
            ('cn', key_name),
            ('sshPublicKey', public_key),
        ]
        self.conn.add_s('cn=%s,uid=%s,%s' % (key_name,
                                             user_name,
                                             self.config['ldap_subtree']),
                                             attr)
    
    def find_user_by_access_key(self, access):
        try:
            dn = self.config['ldap_subtree']
            query = '(' + 'accessKey' + '=' + access + ')'
            res = self.conn.search_s(dn, ldap.SCOPE_SUBTREE, query)
        except Exception:
            return None
        if not res:
            return None
        print res
        return res[0][1] # return attribute list

    def get_user_keys(self, name):
        if not self.user_exists(name):
            raise LdapUserException("User " + name + " doesn't exist")

        attr = self.find_user(name)
        return (attr['accessKey'][0],
                attr['secretKey'][0])

    def delete_public_key(self, user_name, key_name):
        if not self.public_key_exists(user_name, key_name):
            raise LdapUserException("Public Key " +
                                    key_name +
                                    " doesn't exist for user " +
                                    user_name)
        self.conn.delete_s('cn=%s,uid=%s,%s' % (key_name, user_name,
                                          self.config['ldap_subtree']))
        

    def delete_user(self, name):
        if not self.user_exists(name):
            raise LdapUserException("User " +
                                    name +
                                    " doesn't exist")
        self.delete_public_keys(name)
        self.conn.delete_s('uid=%s,%s' % (name,
                                          self.config['ldap_subtree']))

def usage():
    print 'usage: %s -c username (access_key) (secret_key) | -d username' % sys.argv[0]

if __name__ == "__main__":
    # um = UserManager({'use_fake': True})
    # um.create('jesse')
    # access, actual_secret = um.keys('jesse')
    # secret = um.get_secret_from_access(access)
    # assert(secret == actual_secret)
    # assert(None == um.get_secret_from_access('asdf'))
    # um.delete('jesse')
    # print 'works!'
    # # assert(um.user_exists('jesse'))
    # # um.delete('jesse')
    # 
    # 
    # sys.exit(0)
    
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

