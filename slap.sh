#!/usr/bin/env bash
apt-get install slapd ldap-utils

cat >/etc/ldap/schema/openssh-lpk_openldap.schema <<LPK_SCHEMA_EOF
#
# LDAP Public Key Patch schema for use with openssh-ldappubkey
# Author: Eric AUGE <eau@phear.org>
# 
# Based on the proposal of : Mark Ruijter
#


# octetString SYNTAX
attributetype ( 1.3.6.1.4.1.24552.500.1.1.1.13 NAME 'sshPublicKey' 
	DESC 'MANDATORY: OpenSSH Public key' 
	EQUALITY octetStringMatch
	SYNTAX 1.3.6.1.4.1.1466.115.121.1.40 )

# printableString SYNTAX yes|no
objectclass ( 1.3.6.1.4.1.24552.500.1.1.2.0 NAME 'ldapPublicKey' SUP top AUXILIARY
	DESC 'MANDATORY: OpenSSH LPK objectclass'
	MAY ( sshPublicKey $ uid ) 
	)
LPK_SCHEMA_EOF

cat >/etc/ldap/schema/pinet.schema <<PINET_SCHEMA_EOF
#
# Person object for Pinet
# inetorgperson with extra attributes
# Author: Vishvananda Ishaya <vishvananda@yahoo.com>
# 
#

# using internet experimental oid arc as per BP64 3.1
objectidentifier pinetSchema 1.3.6.1.3.1.666.666
objectidentifier pinetAttrs pinetSchema:3
objectidentifier pinetOCs pinetSchema:4

attributetype (
    pinetAttrs:1
	NAME 'accessKey'
	DESC 'Key for accessing data'
	EQUALITY caseIgnoreMatch
	SUBSTR caseIgnoreSubstringsMatch
	SYNTAX 1.3.6.1.4.1.1466.115.121.1.15
	SINGLE-VALUE
    )

attributetype (
    pinetAttrs:2
	NAME 'secretKey'
	DESC ''
	EQUALITY caseIgnoreMatch
	SUBSTR caseIgnoreSubstringsMatch
	SYNTAX 1.3.6.1.4.1.1466.115.121.1.15
	SINGLE-VALUE
    )

attributetype (
    pinetAttrs:3
	NAME 'keyFingerprint'
	DESC 'Fingerprint of private key'
	EQUALITY caseIgnoreMatch
	SUBSTR caseIgnoreSubstringsMatch
	SYNTAX 1.3.6.1.4.1.1466.115.121.1.15
	SINGLE-VALUE
    )

objectClass (
    pinetOCs:1
    NAME 'pinetUser'
    DESC 'access and secret keys'
    AUXILIARY
    MUST ( uid )
    MAY  ( accessKey $ secretKey )
    )

objectClass (
    pinetOCs:2
    NAME 'pinetKeyPair'
    DESC 'Key pair for User'
    SUP top
    STRUCTURAL
    MUST ( cn $ sshPublicKey $ keyFingerprint )
    )
PINET_SCHEMA_EOF

mv /etc/ldap/slapd.conf /etc/ldap/slapd.conf.orig
cat >/etc/ldap/slapd.conf <<SLAPD_CONF_EOF
# slapd.conf - Configuration file for LDAP SLAPD
##########
# Basics #
##########
include /etc/ldap/schema/core.schema
include /etc/ldap/schema/cosine.schema
include /etc/ldap/schema/inetorgperson.schema
include /etc/ldap/schema/openssh-lpk_openldap.schema
include /etc/ldap/schema/pinet.schema
pidfile /var/run/slapd/slapd.pid
argsfile /var/run/slapd/slapd.args
loglevel none
modulepath /usr/lib/ldap
# modulepath /usr/local/libexec/openldap
moduleload back_hdb
##########################
# Database Configuration #
##########################
database hdb
suffix "dc=example,dc=com"
rootdn "cn=Manager,dc=example,dc=com"
rootpw changeme
directory /var/lib/ldap
# directory /usr/local/var/openldap-data
index objectClass,cn eq
########
# ACLs #
########
access to attrs=userPassword
       by anonymous auth
       by self write
       by * none
access to *
       by self write
       by * none
SLAPD_CONF_EOF

mv /etc/ldap/ldap.conf /etc/ldap/ldap.conf.orig

cat >/etc/ldap/ldap.conf <<LDAP_CONF_EOF
# LDAP Client Settings
URI ldap://localhost
BASE dc=example,dc=com
BINDDN cn=Manager,dc=example,dc=com
SIZELIMIT  0
TIMELIMIT  0
LDAP_CONF_EOF

cat >/etc/ldap/base.ldif <<BASE_LDIF_EOF
# This is the root of the directory tree
dn: dc=example,dc=com
description: Example.Com, your trusted non-existent corporation.
dc: example
o: Example.Com
objectClass: top
objectClass: dcObject
objectClass: organization

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

# Subtree for system accounts
dn: ou=System,dc=example,dc=com
ou: System
description: Special accounts used by software applications.
objectClass: organizationalUnit

# Special Account for Authentication:
dn: uid=authenticate,ou=System,dc=example,dc=com
uid: authenticate
ou: System
description: Special account for authenticating users
userPassword: {MD5}TLnIqASP0CKUR3/LGkEZGg==
objectClass: account
objectClass: simpleSecurityObject
BASE_LDIF_EOF

/etc/init.d/slapd stop
rm -rf /var/lib/ldap/*
rm -rf /etc/ldap/slapd.d/*
slaptest -f /etc/ldap/slapd.conf -F /etc/ldap/slapd.d
cp /usr/share/slapd/DB_CONFIG /var/lib/ldap/DB_CONFIG
slapadd -v -l /etc/ldap/base.ldif
chown -R openldap:openldap /etc/ldap/slapd.d
chown -R openldap:openldap /var/lib/ldap
/etc/init.d/slapd start
