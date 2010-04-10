#!/usr/bin/env python
import logging
import ldap
import string
import os
import sys
import settings
from random import choice
from hashlib import sha256
import hmac
import urllib
import base64

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
      
  def authenticate(self, params):
    h = hmac.new(self.aws_secret_access_key, digestmod=sha256)
    signature1 = params['Signature']
    del params['Signature']
    keys = params.keys()
    keys.sort(cmp = lambda x, y: cmp(x.lower(), y.lower()))
    pairs = []
    for key in keys:
      h.update(key)
      val = self.get_utf8_value(params[key])
      h.update(val)
      pairs.append(key + '=' + urllib.quote(val))
    signature2 = base64.b64encode(h.digest())
    return signature1 == signature2

  def test(self, name):
    conn = self._ldap_bind()
    try:
      access, secret = self._get_ldap_user_keys(name, conn)
      print access
      secret = self._get_secret_from_access(access, conn)
      print "secret: %s" % (secret)
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

