from nova.exception import NotFound, NotAuthorized

import os
import nova.crypto

class Object(object):
    def __init__(self, bucket, key):
        """ wrapper class of an existing key """
        self.bucket = bucket
        self.key = key
        self.path = bucket._object_path(key)
        if not os.path.isfile(self.path):
            raise NotAuthorized

    def __repr__(self):
        return "<Object %s/%s>" % (self.bucket, self.key)

    @property
    def md5(self):
        """ computes the MD5 of the contents of file """
        with open(self.path, "r") as f:
            return nova.crypto.compute_md5(f)

    @property
    def mtime(self):
        """ mtime of file """
        return os.path.getmtime(self.path)
    
    def read(self):
        """ returns the contents of the key """
        return open(self.path, 'rb').read()
    
    def delete(self):
        """ deletes the file """
        os.unlink(self.path)