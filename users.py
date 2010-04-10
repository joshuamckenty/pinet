import ldap
import string
from random import choice

class LdapUserException(Exception):
  def __init__(self, message):
    self.message = message

  def __str__(self):
    return self.message

class LdapUserManager:

  def __init__(self, config={}):
    self.config = {
      'password': 'changeme',
      'user': 'admin',
      'ldap_suffix': ',dc=example,dc=com',
      'ldap_url': 'ldap://localhost',
      'key_length': 12,
    }
    self.config.update(config)
      
  def create(self, name, password):
    conn = self._ldap_bind()
    try:
      self._create_ldap_user(name, password,
                             self._random_string(self.config['key_length']),
                             self._random_string(self.config['key_length']),
                             conn)
      return True
    finally:
      conn.unbind_s()

  def keys(self, name):
    """
    Returns a tuple of (secret_key, access_key)
    """
    conn = self._ldap_bind()
    try:
      return self._get_ldap_user_keys(name, conn)
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

  def _find_object_in_ldap(self, name, conn):
    try:
      dn = 'cn=%s%s' % (name, self.config['ldap_suffix'])
      res = conn.search_s(dn, ldap.SCOPE_SUBTREE)
    except ldap.NO_SUCH_OBJECT:
      return None
    return res[0]

  def _user_exists(self, name, conn):
    return self._find_object_in_ldap(name, conn) != None

    
  def _create_ldap_user(self, name, password, secret_key, access_key, conn):
    if self._user_exists(name, conn):
      raise LdapUserException("LDAP user " + name + " already exists")
    # sn is also required for organizationalPerson
    attr = [
      ('objectclass', ['person', 'organizationalPerson']),
      ('cn', name),
      ('sn', name),
      ('street', secret_key), # HACK: using existing fields so we don't have to create a schema
      ('st', access_key),
      ('userPassword', password)
    ]
    conn.add_s('cn=%s%s' % (name, self.config['ldap_suffix']), attr)
    return True

  def _get_ldap_user_keys(self, name, conn):
    if not self._user_exists(name, conn):
      raise LdapUserException("LDAP user " + name + " doesn't exist")

    attr = self._find_object_in_ldap(name, conn)[1]
    return (attr['street'], attr['st']) # HACK: existing fields

  def _delete_ldap_user(self, name, conn):
    if not self._user_exists(name, conn):
      raise LdapUserException("LDAP user " + name + " doesn't exist")
    conn.delete_s('cn=%s%s' % (name, self.config['ldap_suffix']))
    return True

