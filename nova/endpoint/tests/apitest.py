import unittest

import boto
from boto.ec2.regioninfo import RegionInfo

ACCESS_KEY = 'fake'
SECRET_KEY = 'fake'
CLC_IP = '127.0.0.1'
CLC_PORT = 8773
REGION = 'test'

def get_connection():
    return boto.connect_ec2 (
        aws_access_key_id=ACCESS_KEY,
        aws_secret_access_key=SECRET_KEY,
        is_secure=False,
        region=RegionInfo(None, REGION, CLC_IP),
        port=CLC_PORT,
        path='/services/Cloud',
        debug=99
    )
    
class APIIntegrationTests(unittest.TestCase):
    def test_001_get_all_images(self):
        conn = get_connection()
        res = conn.get_all_images()
        print res
        
        
if __name__ == '__main__':
    unittest.main()

#print conn.get_all_key_pairs()
#print conn.create_key_pair
#print conn.create_security_group('name', 'description')

