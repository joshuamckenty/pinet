import os
import contrib
import anyjson

import flags

FLAGS = flags.FLAGS

flags.DEFINE_string('datastore_path', '/root/pinet/keeper',
                    'where keys are stored on disk')

class keeper(object):
    def __init__(self, prefix="pinet-"):
        self.prefix = prefix
        self._path = FLAGS.datastore_path

    def _slugify(self, key):
        return key

    def __getattr__(self, item):
        # TODO - Memoize this
        item = self._slugify(item)
        path = "%s/%s%s" % (self._path, self.prefix, item)
        if os.path.isfile(path):
            return anyjson.deserialize(open(path, 'r').read())
        return None

    def __setattr__(self, item, value):
        item = self._slugify(item)
        path = "%s/%s%s" % (self._path, self.prefix, item)
        f = open(path, "w")
        f.write(anyjson.serialize(value))
        # TODO: Pop and return the old value?
        return value
