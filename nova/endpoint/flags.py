import nova.contrib
from gflags import *

if not FLAGS.has_key('cloud_topic'):
    DEFINE_string('cloud_topic', 'cloud', 'the topic clouds listen on')