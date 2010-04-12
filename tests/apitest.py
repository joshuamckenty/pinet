import boto
from boto.ec2.regioninfo import RegionInfo

CLC_IP = '127.0.0.1'
CLC_PORT = 8773
REGION = 'test'

conn = boto.connect_ec2 (
    aws_access_key_id='fake',
    aws_secret_access_key='fake',
    is_secure=False,
    region=RegionInfo(None, REGION, CLC_IP),
    port=CLC_PORT,
    path='/services/Cloud',
    debug=99
)

print conn.get_all_images()
#print conn.get_all_key_pairs()
#print conn.create_key_pair
#print conn.create_security_group('name', 'description')

