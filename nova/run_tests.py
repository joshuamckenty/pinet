# vim: tabstop=4 shiftwidth=4 softtabstop=4
import contrib
import unittest
import flags
import nova.compute
import nova.volume
import nova.endpoint
import nova.auth

FLAGS = flags.FLAGS
FLAGS.verbose = True
flags.DEFINE_bool('fake_tests', False, 'should we use everything for testing')

if FLAGS.fake_tests:
    from tests.fake_flags import *
else:
    from tests.real_flags import *
    
from endpoint.tests.api_unittest import *
from compute.tests.node_unittest import *
from endpoint.tests.cloud_unittest import *
from auth.tests import *
from volume.tests.storage_unittest import *
from endpoint.tests.network_unittest import *
from objectstore.tests.objectstore_unittest import *

if __name__ == '__main__':
    unittest.main()
