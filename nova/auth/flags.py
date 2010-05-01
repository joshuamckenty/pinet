import nova.contrib
from gflags import *

if not FLAGS.has_key('fake_users'):
    DEFINE_bool('fake_users', False, 'use fake users')