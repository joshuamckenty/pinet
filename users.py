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

class LdapUserException(Exception):
    def __init__(self, message):
        self.message = message

    def __str__(self):
        return self.message

class UserManager:
    def __init__(self, config={}):
        self.config = {
            'password': 'changeme',
            'user': 'admin',
            'ldap_suffix': ',dc=example,dc=com',
            'ldap_url': 'ldap://localhost',
            'access_field': 'st',
            'secret_field': 'street',
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
            secret_key = user[self.config['secret_field']][0]
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
            return conn.get_secret_from_access(access_key)

    def create(self, name, access=None, secret=None):
        if access == None: access = str(uuid.uuid4())
        if secret == None: secret = str(uuid.uuid4())
        with LDAPWrapper(self.config) as conn:
            conn.create_user(name, access, secret)

    def delete(self, name):
        with LDAPWrapper(self.config) as conn:
            conn.delete_user(name)
        
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
        dn = "cn=%s%s" % (self.config['user'], self.config['ldap_suffix'])
        self.conn.simple_bind_s(dn, self.config['password'])

    def find_user_by_name(self, name):
        try:
            dn = 'uid=%s,ou=Users%s' % (name, self.config['ldap_suffix'])
            res = self.conn.search_s(dn, ldap.SCOPE_SUBTREE)
        except Exception:
            return None
        return res[0][1]  # return attribute list

    def user_exists(self, name):
        return self.find_user_by_name(name) != None
        
    def create_user(self, name, access_key, secret_key):
        if self.user_exists(name):
            raise LdapUserException("LDAP user " + name + " already exists")
        # sn is also required for organizationalPerson
        attr = [
            ('objectclass', ['person', 'organizationalperson', 'inetorgperson']),
            ('ou', 'Users'),
            ('uid', name),
            ('sn', name),
            ('cn', name),
            # HACK: using existing fields so we don't have to create a schema
            (self.config['secret_field'], secret_key),
            (self.config['access_field'], access_key),
        ]
        self.conn.add_s('uid=%s,ou=Users%s' % (name, self.config['ldap_suffix']), attr)

    def find_user_by_access_key(self, access):
        try:
            dn = 'ou=Users%s' % self.config['ldap_suffix']
            query = '(' + self.config['access_field'] + '=' + access + ')'
            res = self.conn.search_s(dn, ldap.SCOPE_SUBTREE, query)
        except Exception:
            return None
        if not res:
            return None
        return res[0][1] # return attribute list

    def get_user_keys(self, name):
        if not self.user_exists(name):
            raise LdapUserException("LDAP user " + name + " doesn't exist")

        attr = self.find_user_by_name(name)
        return (attr[self.config['access_field']][0],
                        attr[self.config['secret_field']][0])

    def delete_user(self, name):
        if not self.user_exists(name):
            raise LdapUserException("LDAP user " + name + " doesn't exist")
        self.conn.delete_s('cn=%s%s' % (name, self.config['ldap_suffix']))

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

