ami = '/root/pinet/images/ubuntu-karmic-x86_64.img'
aki = '/root/pinet/images/vmlinuz-karmic-x86-64'
ari = '/root/pinet/images/initrd.img-karmic-x86_64'

instances_path = '/root/pinet/instances'
bridge = 'virbr0'

CC_PORT = 8773

S3_PORT = 3333
S3_PATH = '/var/pinet/s3/'

try:
    from settings_local import *
except Exception, e:
    print >> sys.stderr, 'Warning:', e