# vim: tabstop=4 shiftwidth=4
ami = '/root/pinet/images/ubuntu-karmic-x86_64.img'
aki = '/root/pinet/images/vmlinuz-karmic-x86-64'
ari = '/root/pinet/images/initrd.img-karmic-x86_64'

instances_path = '/root/pinet/instances'
bridge = 'virbr0'
aoe_eth_dev = 'eth0'

storage_dev = '/dev/sdb1'
volume_group = 'pinet-volumes'

LOG_PATH = '/var/pinet/logs'
PID_PATH = '/var/pinet/run'
S3_PATH = '/var/pinet/s3/'
S3_PORT = 3333
CC_PORT = 8773

try:
    from local_settings import *
except Exception, e:
    pass
