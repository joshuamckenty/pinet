#!/usr/bin/env python
import logging

try:
    import ldap
except Exception, e:
    import fakeldap as ldap

import fakeldap

import os
import sys
import settings
import signer
import uuid

_log = logging.getLogger()


import subprocess
import shlex

def _generate_key_pair():
    args = shlex.split('ssh-keygen -y -f')
    args.append(path)
    p = subprocess.Popen(args, stdout=subprocess.PIPE)
    stdout = p.communicate()[0]
    if p.returncode != 0:
        raise Exception("Error handling would be nice, eh?")
    return stdout.strip()


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
            user = conn.get_user_from_access(access_key)
        
        if user:
            secret_key = user['secretKey'][0]
            expected_signature = signer.Signer(secret_key).generate(params, verb, server_string, path)
            if signature == expected_signature:
                return user
        return False
        
    def keys(self, name):
        """ return access & secret for a username """
        with LDAPWrapper(self.config) as conn:
            return conn.get_user_keys(name)
    
    def get_secret_from_access(self, access_key):
        """ retreive the secret key for a given access key """
        with LDAPWrapper(self.config) as conn:
            user = conn.get_user_from_access(access_key)
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

    def create_key_pair(self, name):
        private_key, public_key = _generate_key_pair()
        with LDAPWrapper(self.config) as conn:
            conn.create_public_key(name, public_key)

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

    def find_object(self, name):
        try:
            dn = 'uid=%s,%s' % (name, self.config['ldap_subtree'])
            res = self.conn.search_s(dn, ldap.SCOPE_SUBTREE)
        except Exception:
            return None
        return res[0][1]  # return attribute list

    def object_exists(self, name):
        return self.find_object(name) != None
        
    def create_user(self, name, access_key, secret_key):
        if self.object_exists(name, self.config['user_unit']):
            raise LdapUserException("LDAP user " + name + " already exists")
        attr = [
            ('objectclass', ['person',
                             'organizationalperson',
                             'inetorgperson',
                             'pinetkeys',
                             'ldappublickey']),
            ('ou', self.config['user_unit']),
            ('uid', name),
            ('sn', name),
            ('cn', name),
            ('secretKey', secret_key),
            ('accessKey', access_key),
        ]
        self.conn.add_s('uid=%s,%s' % (name, self.config['ldap_subtree']),
                        attr)

    def create_public_key(self, name, public_key):
        if self.object_exists(name, self.config['key_unit']):
            raise LdapUserException("LDAP public key " + name + " already exists")
        attr = [
            ('objectclass', ['ldappublickey']),
            ('ou', self.config['key_unit']),
            ('uid', name),
        ]
        self.conn.add_s('uid=%s,ou=%s%s' % (name,
                                            self.config['key_unit'],
                                            self.config['ldap_subtree']),
                                            attr)
    
    def find_user_by_access_key(self, access):
        try:
            dn = 'ou=%s%s' % (self.config['user_unit'], self.config['ldap_subtree'])
            query = '(' + 'accessKey' + '=' + access + ')'
            res = self.conn.search_s(dn, ldap.SCOPE_SUBTREE, query)
        except Exception:
            return None
        if not res:
            return None
        return res[0][1] # return attribute list

    def get_user_keys(self, name):
        if not self.object_exists(name, self.config['user_unit']):
            raise LdapUserException("LDAP user " + name + " doesn't exist")

        attr = self.find_object(name, self.config['user_unit'])
        print attr
        return (attr['accessKey'][0],
                        attr['secretKey'][0])

    def delete_public_key(self, name):
        pass

    def delete_user(self, name):
        if not self.object_exists(name):
            raise LdapUserException("User " +
                                    name +
                                    " doesn't exist")
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
    um = UserManager()
    try:
        um.create('jesse')
    except Exception:
        um.delete('jesse')
    print um.keys('jesse')
    um.delete('jesse')
    sys.exit(0)

    logging.basicConfig(level=logging.DEBUG,
    filename=os.path.join(settings.LOG_PATH, 'users.log'), filemode='a')
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

