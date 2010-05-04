from gflags import *


if not FLAGS.has_key('fake_storage'):
    DEFINE_boolean('fake_storage', False, 'Should we make real storage volumes to attach?')