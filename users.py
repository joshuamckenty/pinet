#!/usr/bin/env python
import logging
import ldap
import string
import os
import sys
import settings
from random import choice

from hashlib import sha1 as sha
from hashlib import sha256
import hmac
import urllib
import base64

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
            'key_length': 12,
            'access_field': 'st',
            'secret_field': 'street',
        }
        self.config.update(config)

    def authenticate(self, params, signature, verb='GET', server_string='127.0.0.1:8873', path='/'):
        # TODO: Check for valid timestamp
        access_key = params['AWSAccessKeyId']
        if(access_key[:3] == 'foo'):
            secret_key = access_key
        else:
            conn = self._ldap_bind()
            try:
                secret_key = self._get_secret_from_access(access_key, conn)
            finally:
                conn.unbind_s()
        
        self.hmac = hmac.new(secret_key, digestmod=sha)
        if sha256:
            self.hmac_256 = hmac.new(secret_key, digestmod=sha256)
        qs, match_signature = self._get_signature(params, verb, server_string, path)
        return signature == match_signature
        
    def keys(self, name):
        conn = self._ldap_bind()
        try:
            return self._get_ldap_user_keys(name, conn)
        finally:
            conn.unbind_s()

    def create(self, name):
        conn = self._ldap_bind()
        try:
            self._create_ldap_user(name,
                                 self._random_string(self.config['key_length']),
                                 self._random_string(self.config['key_length']),
                                 conn)
            return True
        finally:
            conn.unbind_s()


    def delete(self, name):
        conn = self._ldap_bind()
        try:
            self._delete_ldap_user(name, conn)
            return True
        finally:
            conn.unbind_s()

    ######## END OF PUBLIC INTERFACE

# BEGIN hacked up code from boto/connection.py
    def _get_utf8_value(self, value):
        if not isinstance(value, str) and not isinstance(value, unicode):
            value = str(value)
        if isinstance(value, unicode):
            return value.encode('utf-8')
        else:
            return value

    def _calc_signature_0(self, params):
        # boto.log.debug('using _calc_signature_0')
        hmac = self.hmac.copy()
        s = params['Action'] + params['Timestamp']
        hmac.update(s)
        keys = params.keys()
        keys.sort(cmp = lambda x, y: cmp(x.lower(), y.lower()))
        pairs = []
        for key in keys:
            val = self._get_utf8_value(params[key])
            pairs.append(key + '=' + urllib.quote(val))
        qs = '&'.join(pairs)
        return (qs, base64.b64encode(hmac.digest()))

    def _calc_signature_1(self, params):
        # boto.log.debug('using _calc_signature_1')
        hmac = self.hmac.copy()
        keys = params.keys()
        keys.sort(cmp = lambda x, y: cmp(x.lower(), y.lower()))
        pairs = []
        for key in keys:
            hmac.update(key)
            val = self._get_utf8_value(params[key])
            hmac.update(val)
            pairs.append(key + '=' + urllib.quote(val))
        qs = '&'.join(pairs)
        return (qs, base64.b64encode(hmac.digest()))

    def _calc_signature_2(self, params, verb, server_string, path):
        _log.debug('using _calc_signature_2')
        string_to_sign = '%s\n%s\n%s\n' % (verb, server_string, path)
        if self.hmac_256:
            hmac = self.hmac_256.copy()
            params['SignatureMethod'] = 'HmacSHA256'
        else:
            hmac = self.hmac.copy()
            params['SignatureMethod'] = 'HmacSHA1'
        keys = params.keys()
        keys.sort()
        pairs = []
        for key in keys:
            val = self._get_utf8_value(params[key])
            pairs.append(urllib.quote(key, safe='') + '=' + urllib.quote(val, safe='-_~'))
        qs = '&'.join(pairs)
        _log.debug('query string: %s' % qs)
        string_to_sign += qs
        _log.debug('string_to_sign: %s' % string_to_sign)
        hmac.update(string_to_sign)
        b64 = base64.b64encode(hmac.digest())
        _log.debug('len(b64)=%d' % len(b64))
        _log.debug('base64 encoded digest: %s' % b64)
        return (qs, b64)

    def _get_signature(self, params, verb, server_string, path):
        if params['SignatureVersion'] == '0':
            t = self._calc_signature_0(params)
        elif params['SignatureVersion'] == '1':
            t = self._calc_signature_1(params)
        elif params['SignatureVersion'] == '2':
            t = self._calc_signature_2(params, verb, server_string, path)
        else:
            raise LdapUserException('Unknown Signature Version: %s' % self.SignatureVersion)
        return t

#end copied code

    def _random_string(self, length=8, chars=string.letters + string.digits):
        return ''.join([choice(chars) for i in range(length)])

    def _ldap_bind(self):
        # open() is deprecated, use initialize
        l = ldap.initialize(self.config['ldap_url'])
        # operate synchronously to raise exceptions
        # as admin
        dn = "cn=%s%s" % (self.config['user'], self.config['ldap_suffix'])
        l.simple_bind_s(dn, self.config['password'])
        # as guest
        # l.simple_bind_s() # l.simple_bind('', '')
        return l

    def _find_user_by_name(self, name, conn):
        try:
            dn = 'cn=%s%s' % (name, self.config['ldap_suffix'])
            res = conn.search_s(dn, ldap.SCOPE_SUBTREE)
        except ldap.NO_SUCH_OBJECT:
            return None
        return res[0]

    def _user_exists(self, name, conn):
        return self._find_user_by_name(name, conn) != None
        
    def _create_ldap_user(self, name, secret_key, access_key, conn):
        if self._user_exists(name, conn):
            raise LdapUserException("LDAP user " + name + " already exists")
        # sn is also required for organizationalPerson
        attr = [
            ('objectclass', ['person', 'organizationalperson']),
            ('cn', name),
            ('sn', name),
            (self.config['secret_field'], secret_key), # HACK: using existing fields so we don't have to create a schema
            (self.config['access_field'], access_key),
        ]
        conn.add_s('cn=%s%s' % (name, self.config['ldap_suffix']), attr)
        return True

    def _get_secret_from_access(self, access, conn):
        try:
            dn = self.config['ldap_suffix'][1:]
            filter = '(' + self.config['access_field'] + '=' + access + ')'
            print filter
            res = conn.search_s(dn, ldap.SCOPE_SUBTREE, filter, [self.config['secret_field']])
        except ldap.NO_SUCH_OBJECT:
            return None
        if not res:
            return None
        return res[0][1][self.config['secret_field']][0]

    def _get_ldap_user_keys(self, name, conn):
        if not self._user_exists(name, conn):
            raise LdapUserException("LDAP user " + name + " doesn't exist")

        attr = self._find_user_by_name(name, conn)[1]
        return (attr[self.config['access_field']][0],
                        attr[self.config['secret_field']][0])

    def _delete_ldap_user(self, name, conn):
        if not self._user_exists(name, conn):
            raise LdapUserException("LDAP user " + name + " doesn't exist")
        conn.delete_s('cn=%s%s' % (name, self.config['ldap_suffix']))
        return True

def usage():
    print 'usage: %s -c username | -d username' % sys.argv[0]

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG,
    filename=os.path.join(settings.LOG_PATH, 'users.log'), filemode='a')
    manager = UserManager()
    
    if len(sys.argv) == 3:
        if sys.argv[1] == '-c':
            manager.create(sys.argv[2])
            print manager.keys(sys.argv[2])
        elif sys.argv[1] == '-d':
            manager.delete(sys.argv[2])
        elif sys.argv[1] == '-t':
            manager.test(sys.argv[2])
        else:
            usage()
            sys.exit(2)
        sys.exit(0)
    else:
        usage()
        sys.exit(2)

