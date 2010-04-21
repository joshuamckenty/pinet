# vim: tabstop=4 shiftwidth=4 softtabstop=4
import contrib
import unittest
import flags
import node
import storage
import cloud

FLAGS = flags.FLAGS

flags.DEFINE_bool('fake_tests', True, 'should we use everything for testing')

if FLAGS.fake_tests:
    from tests.fake_flags import *
else:
    from tests.real_flags import *
    
from tests.api_unittest import *
from tests.node_unittest import *
from tests.cloud_unittest import *
from tests.users_unittest import *
from tests.storage_unittest import *
from tests.network_unittest import *

if __name__ == '__main__':
    unittest.main()
