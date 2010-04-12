# vim: tabstop=4 shiftwidth=4
import logging

logging.warning('DEPRECATED: settings.py is deprecated, use flags.py instead')

IMAGES_PATH = '/root/pinet/images'
ami = '%s/ubuntu-karmic-x86_64.img' % (IMAGES_PATH)
aki = '/root/pinet/images/vmlinuz-karmic-x86-64'
ari = '/root/pinet/images/initrd.img-karmic-x86_64'


instances_path = '/root/pinet/instances'
bridge = 'virbr0'
aoe_eth_dev = 'br0'

storage_dev = '/dev/sdb1'
volume_group = 'pinet-volumes'
volume_mountpoint = '/var/pinet/volumes'

LOG_PATH = '/var/pinet/logs'
PID_PATH = '/var/pinet/run'
S3_PATH = '/var/pinet/s3/'
S3_PORT = 3333
CC_PORT = 8773

RABBIT_PORT = 5672
RABBIT_HOST = "localhost"
RABBIT_USER = "guest"
RABBIT_PASS = "guest"
RABBIT_VHOST = "/"

CONTROL_EXCHANGE = "pinet"

STORAGE_INTERVAL = 5 * 1000
NODE_INTERVAL = 5 * 1000

try:
    from local_settings import *
except Exception, e:
    pass
