# vim: tabstop=4 shiftwidth=4 softtabstop=4
import unittest
import flags

FLAGS = flags.FLAGS

from tests.node_unittest import *
from tests.cloud_unittest import *
from tests.users_unittest import *
if FLAGS.fake_storage:
    from tests.storage_unittest import StorageFakeTestCase
else:
    from tests.storage_unittest import StorageRealTestCase
from tests.network_unittest import *

if __name__ == '__main__':
    unittest.main()
