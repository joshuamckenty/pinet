import contrib
import flags

FLAGS = flags.FLAGS

FLAGS.fake_libvirt = True
FLAGS.fake_storage = True
FLAGS.fake_rabbit = True
FLAGS.fake_network = True
FLAGS.fake_users = True
FLAGS.verbose = True