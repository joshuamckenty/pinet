import nova.contrib
from gflags import *
from nova.utils import abspath

if not FLAGS.has_key('s3_port'):
    DEFINE_integer('s3_port', 3333, 's3 port')
    DEFINE_integer('s3_internal_port', 3334, 's3 port')
    DEFINE_string('s3_host', '172.24.226.1', 's3 host')
    DEFINE_string('buckets_path', abspath('../buckets'), 'path to s3 buckets')
    DEFINE_string('images_path', abspath('../images'), 'path to decrypted images')