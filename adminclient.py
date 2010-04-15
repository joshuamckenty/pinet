"""
Pinet administration API client library.
"""

import urllib2
import re
from random import choice
import boto
from boto.ec2.regioninfo import RegionInfo

class UserInfo(object):
    def __init__(self, connection=None, username=None, endpoint=None):
        self.connection = connection
        self.username = username
        self.endpoint = endpoint

    def __repr__(self):
        return 'UserInfo:%s' % self.username

    def startElement(self, name, attrs, connection):
        return None

    def endElement(self, name, value, connection):
        if name == 'username':
            self.username = str(value)
        elif name == 'code':
            self.code = str(value)
        elif name == 'accesskey':
            self.accesskey = str(value)
        elif name == 'secretkey':
            self.secretkey = str(value)

class PinetAdminClient(object):
    def __init__(self, clc_ip='127.0.0.1', region='test', access_key='fake', secret_key='fake', **kwargs):
        self.clc_ip = clc_ip
        self.region = region
        self.access = access_key
        self.secret = secret_key
        self.apiconn = boto.connect_ec2(aws_access_key_id=access_key,
                                        aws_secret_access_key=secret_key,
                                        is_secure=False,
                                        region=RegionInfo(None, self.region, self.clc_ip),
                                        port=8773,
                                        path='/services/Admin',
                                        **kwargs)
        self.apiconn.APIVersion = 'pinet'

        
    def connection_for(self, username, **kwargs):
        """
        Returns a boto ec2 connection for the given username.
        """
        user = self.get_user(username)
        return boto.connect_ec2 (
            aws_access_key_id=user.accesskey,
            aws_secret_access_key=user.secretkey,
            is_secure=False,
            region=RegionInfo(None, self.region, self.clc_ip),
            port=8773,
            path='/services/Cloud',
            **kwargs
        )
    
    def get_user(self, username):
        # TODO: Cache for 2 minutes
        return self.apiconn.get_object('DescribeUser', {'Name': username}, UserInfo)

    def has_user(self, username):
        return self.get_user(username) != None

    def create_user(self, username):
        return self.apiconn.get_object('RegisterUser', {'Name': username}, UserInfo)

    def delete_user(self, username):
        return self.apiconn.get_object('DeregisterUser', {'Name': username}, UserInfo)
    
    def download_url(self, username):
        """
        Returns the url to download a zip file containing pinetrc and access credentials.
        """        
        user = self.get_user(username)
        return "https://%s:8443/getX509?user=%s&code=%s" % (self.clc_ip, user.username, user.code)

    '''
    def get_signed_zip(self, username):
        return urllib2.urlopen('http://%s:81/getcert/%s' % (self.clc_ip, username)).read()
    '''

if __name__ == '__main__':
    admin = PinetAdminClient()
    
    print admin.get_user('fake')
    print admin.create_user('test1')
    print admin.get_user('test1')
    print admin.download_url('test1')
    print admin.delete_user('test1')


