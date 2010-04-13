#!/bin/bash

####################################
# BASE
####################################

# apt-get install -y unzip

####################################
# SVN / HTTP
####################################

# apt-get install -y apache2-dev apache2-mpm-prefork libapache2-svn subversion python-subversion subversion-tools python-ldap python-yaml
# 
# a2enmod authnz_ldap

# cat >/etc/apache2/conf.d/ldap-svn.conf <<HTTP_LDAP_EOF
# <Location />
#   AuthBasicProvider ldap
#   AuthType basic
#   AuthzLDAPAuthoritative off
#   AuthName "SVN Repo Access"
#   AuthLDAPURL "ldap://localhost/DC=localhost,DC=localdomain?cn?sub?(objectClass=person)" NONE
# </Location>
# HTTP_LDAP_EOF

/etc/init.d/apache2 restart

# LDAP SETUP - http://www.howtoforge.com/install-and-configure-openldap-on-ubuntu-karmic-koala

apt-get install -y slapd ldap-utils
ldapadd -Y EXTERNAL -H ldapi:/// -f /etc/ldap/schema/cosine.ldif
ldapadd -Y EXTERNAL -H ldapi:/// -f /etc/ldap/schema/inetorgperson.ldif
ldapadd -Y EXTERNAL -H ldapi:/// -f /etc/ldap/schema/nis.ldif

cat >/etc/ldap/db.ldif <<DB_LDIF_EOF
# Load dynamic backend modules
dn: cn=module{0},cn=config
objectClass: olcModuleList
cn: module
olcModulepath: /usr/lib/ldap
olcModuleload: {0}back_hdb

# Create the database
dn: olcDatabase={1}hdb,cn=config
objectClass: olcDatabaseConfig
objectClass: olcHdbConfig
olcDatabase: {1}hdb
olcDbDirectory: /var/lib/ldap
olcSuffix: dc=example,dc=com
olcRootDN: cn=admin,dc=example,dc=com
olcRootPW: changeme
olcDbConfig: {0}set_cachesize 0 2097152 0
olcDbConfig: {1}set_lk_max_objects 1500
olcDbConfig: {2}set_lk_max_locks 1500
olcDbConfig: {3}set_lk_max_lockers 1500
olcLastMod: TRUE
olcDbCheckpoint: 512 30
olcDbIndex: uid pres,eq
olcDbIndex: cn,sn,mail pres,eq,approx,sub
olcDbIndex: objectClass eq
DB_LDIF_EOF

ldapadd -Y EXTERNAL -H ldapi:/// -f /etc/ldap/db.ldif

cat >/etc/ldap/base.ldif <<BASE_LDIF_EOF
# Root 
dn: dc=example,dc=com
objectClass: dcObject
objectclass: organization
o: example.com
dc: example
description: LDAP Root

# Subtree for users
dn: ou=Users,dc=example,dc=com
ou: Users
description: Users
objectClass: organizationalUnit

# Subtree for groups
dn: ou=Groups,dc=example,dc=com
ou: Groups
description: Groups
objectClass: organizationalUnit

# Subtree for keys
dn: ou=Keys,dc=example,dc=com
ou: Groups
description: Keys
objectClass: organizationalUnit

dn: cn=admin,dc=example,dc=com
objectClass: simpleSecurityObject
objectClass: organizationalRole
cn: admin
userPassword: {MD5}TLnIqASP0CKUR3/LGkEZGg==
description: LDAP administrator
BASE_LDIF_EOF

ldapadd -Y EXTERNAL -H ldapi:/// -f /etc/ldap/base.ldif

cat >/etc/ldap/config.ldif <<CONFIG_LDIF_EOF
dn: cn=config
changetype: modify
delete: olcAuthzRegexp

dn: olcDatabase={-1}frontend,cn=config
changetype: modify
delete: olcAccess

dn: olcDatabase={0}config,cn=config
changetype: modify
delete: olcRootDN

dn: olcDatabase={0}config,cn=config
changetype: modify
add: olcRootDN
olcRootDN: cn=admin,cn=config

dn: olcDatabase={0}config,cn=config
changetype: modify
add: olcRootPW
olcRootPW: {MD5}TLnIqASP0CKUR3/LGkEZGg==

dn: olcDatabase={0}config,cn=config
changetype: modify
delete: olcAccess
CONFIG_LDIF_EOF

ldapadd -Y EXTERNAL -H ldapi:/// -f /etc/ldap/config.ldif

cat >/etc/ldap/acl.ldif <<ACL_LDIF_EOF
dn: olcDatabase={1}hdb,cn=config
add: olcAccess
olcAccess: to attrs=userPassword,shadowLastChange by dn="cn=admin,dc=example,dc=com" write by anonymous auth by self write by * none
olcAccess: to dn.base="" by * read
olcAccess: to * by dn="cn=admin,dc=example,dc=com" write by * read
ACL_LDIF_EOF

ldapmodify -x -D cn=admin,cn=config -W -f /etc/ldap/acl.ldif

####################
# FARMER
####################

apt-get install -y python-django python-psycopg2 postgresql erlang rabbitmq-server


